import abc
from logging import Logger
from moneyed import Money
from yolo_discord.types import (
    CreateOrderRequest,
    Order,
    OrderInsert,
    OrderType,
    OwnedSecurity,
    PortfolioEntry,
    TransactionInsert,
    TransactionType,
)
from yolo_discord.config import get_config
from yolo_discord.db import Database
from yolo_discord.service.security import SecurityService
from yolo_discord import types


class YoloService(abc.ABC):
    async def get_balance(self, user_id: str) -> Money: ...
    async def buy(self, request: CreateOrderRequest) -> Order: ...
    async def sell(self, request: CreateOrderRequest) -> Order: ...
    async def get_portfolio(self, user_id: str) -> list[PortfolioEntry]: ...
    async def update_allowances(self) -> None: ...
    async def take_portfolio_snapshots(self) -> None: ...
    async def add_allowance(self, user_id: str) -> None: ...


class NotEnoughMoneyException(Exception): ...


class NotEnoughQuantityException(Exception): ...


class YoloServiceImpl(YoloService):
    logger: Logger
    database: Database
    security_service: SecurityService

    def __init__(
        self, logger: Logger, database: Database, security_service: SecurityService
    ) -> None:
        self.logger = logger
        self.database = database
        self.security_service = security_service

    async def get_balance(self, user_id: str) -> Money:
        await self.create_user(user_id)
        return await self.database.get_user_balance(user_id)

    async def buy(self, request: CreateOrderRequest) -> Order:
        await self.create_user(request.user_id)
        try:
            balance = await self.database.get_user_balance(request.user_id)
            security_price = await self.security_service.get_security_price(
                request.security_name
            )
            if security_price is None:
                raise Exception(
                    f"Could not fetch price of security ${request.security_name}"
                )
            debit_amount = security_price * request.quantity
            if debit_amount > balance:
                raise NotEnoughMoneyException()
            debit = await self.database.create_transaction(
                TransactionInsert(
                    user_id=request.user_id,
                    type=TransactionType.DEBIT,
                    amount=debit_amount,
                    comment=f"Buy for {request.quantity} of ${request.security_name}",
                )
            )
            order = await self.database.create_order(
                OrderInsert(
                    user_id=request.user_id,
                    transaction_id=debit.id,
                    type=OrderType.BUY,
                    security_name=request.security_name,
                    security_price=security_price,
                    quantity=request.quantity,
                )
            )
            await self.database.commit()
            return order
        except:
            await self.database.rollback()
            raise

    async def sell(self, request: CreateOrderRequest) -> Order:
        await self.create_user(request.user_id)
        try:
            quantity = await self.database.get_user_security_quantity(
                request.user_id, request.security_name
            )
            if quantity < request.quantity:
                raise NotEnoughQuantityException()
            security_price = await self.security_service.get_security_price(
                request.security_name
            )
            if security_price is None:
                raise Exception(
                    f"Could not fetch price of security ${request.security_name}"
                )
            credit_amount = security_price * request.quantity
            credit = await self.database.create_transaction(
                TransactionInsert(
                    user_id=request.user_id,
                    type=TransactionType.CREDIT,
                    amount=credit_amount,
                    comment=f"Sell for {request.quantity} of ${request.security_name}",
                )
            )
            order = await self.database.create_order(
                OrderInsert(
                    user_id=request.user_id,
                    transaction_id=credit.id,
                    type=OrderType.SELL,
                    security_name=request.security_name,
                    security_price=security_price,
                    quantity=request.quantity,
                )
            )
            await self.database.commit()
            return order
        except:
            await self.database.rollback()
            raise

    async def create_user(self, user_id: str):
        try:
            is_new_user = await self.database.create_user(user_id)
            if is_new_user:
                config = get_config()
                self.logger.info(
                    f"New user <@{user_id}> created, granting starting balance of {config.starting_balance}"
                )
                await self.database.create_allowance(user_id)
                await self.database.create_transaction(
                    TransactionInsert(
                        user_id=user_id,
                        type=TransactionType.CREDIT,
                        amount=config.starting_balance,
                        comment="Initial credit",
                    )
                )
                await self.database.commit()
        except Exception as exc:
            self.logger.error("Could not create user", exc_info=exc)
            await self.database.rollback()
            raise

    async def get_portfolio(
        self, user_id: str, create_user: bool = True
    ) -> list[PortfolioEntry]:
        if create_user:
            await self.create_user(user_id)
        owned_securities = await self.database.get_owned_securities(user_id)
        current_prices = await self.security_service.get_security_prices(
            [security.name for security in owned_securities]
        )
        if current_prices is None:
            raise Exception("Could not look up security prices")
        return [
            PortfolioEntry(
                security_name=security.name,
                balance=security.quantity * current_prices[security.name],
                quantity=security.quantity,
                return_rate=calculate_return_rate(
                    security, current_prices[security.name]
                ),
            )
            for security in owned_securities
        ]

    async def update_allowances(self) -> None:
        self.logger.info("Granting user allowances")
        try:
            user_ids = await self.database.get_eligible_users_for_allowance()
            for user_id in user_ids:
                await self.add_allowance(user_id)
            await self.database.commit()
        except Exception as exc:
            self.logger.error("Could not process allowances", exc_info=exc)
            await self.database.rollback()
            raise

    async def take_portfolio_snapshots(self) -> None:
        self.logger.info("Taking portfolio snapshots")
        try:
            user_ids = await self.database.get_all_users()
            for user_id in user_ids:
                portfolio = await self.get_portfolio(user_id, create_user=False)
                await self.database.create_portfolio_snapshot(user_id, portfolio)
            await self.database.commit()
        except Exception as exc:
            self.logger.error("Could not process portfolio snapshots", exc_info=exc)
            await self.database.rollback()
            raise

    async def add_allowance(self, user_id: str) -> None:
        config = get_config()
        await self.database.create_allowance(user_id)
        await self.database.create_transaction(
            TransactionInsert(
                user_id=user_id,
                type=TransactionType.CREDIT,
                amount=config.weekly_allowance,
                comment="Weekly allowance",
            )
        )


def calculate_return_rate(security: OwnedSecurity, current_price: Money) -> float:
    total_price_paid = security.total_price_paid.get_amount_in_sub_unit()
    current_total_price = (security.quantity * current_price).get_amount_in_sub_unit()
    if total_price_paid < current_total_price:
        rate = 1 - current_total_price / total_price_paid
    else:
        rate = -(1 - total_price_paid / current_total_price)
    return round(rate * 100, 2)
