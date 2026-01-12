import abc
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


class YoloService(abc.ABC):
    async def get_balance(self, user_id: str) -> Money: ...
    async def buy(self, request: CreateOrderRequest) -> Order: ...
    async def get_portfolio(self, user_id: str) -> list[PortfolioEntry]: ...


class YoloServiceImpl(YoloService):
    database: Database
    security_service: SecurityService

    def __init__(self, database: Database, security_service: SecurityService) -> None:
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
                raise Exception("not enough money for order")
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

    async def create_user(self, user_id: str) -> None:
        try:
            is_new_user = await self.database.create_user(user_id)
            if is_new_user:
                config = get_config()
                await self.database.create_transaction(
                    TransactionInsert(
                        user_id=user_id,
                        type=TransactionType.CREDIT,
                        amount=config.starting_balance,
                        comment="Initial credit",
                    )
                )
                await self.database.commit()
        except:
            await self.database.rollback()
            raise

    async def get_portfolio(self, user_id: str) -> list[PortfolioEntry]:
        await self.database.create_user(user_id)
        owned_securities = await self.database.get_owned_securities(user_id)
        current_prices = await self.security_service.get_security_prices(
            [security.name for security in owned_securities]
        )
        if current_prices is None:
            raise Exception("could not look up security prices")
        return [
            PortfolioEntry(
                security_name=security.name,
                quantity=security.quantity,
                return_rate=calculate_return_rate(
                    security, current_prices[security.name]
                ),
            )
            for security in owned_securities
        ]


def calculate_return_rate(security: OwnedSecurity, current_price: Money) -> float:
    total_price_paid = security.total_price_paid.get_amount_in_sub_unit()
    current_total_price = (security.quantity * current_price).get_amount_in_sub_unit()
    if total_price_paid < current_total_price:
        rate = 1 - current_total_price / total_price_paid
    else:
        rate = -(1 - total_price_paid / current_total_price)
    return round(rate * 100, 2)
