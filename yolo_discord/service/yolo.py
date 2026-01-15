from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from moneyed import Money
from yolo_discord.dto import (
    Order,
    OrderInsert,
    OrderType,
    PortfolioEntry,
    PortfolioSnapshot,
    TransactionInsert,
    TransactionType,
)
from yolo_discord.config import get_config
from yolo_discord.db import Database, Tx
from yolo_discord.service.security import SecurityService
from yolo_discord.util import calculate_return_rate


@dataclass
class CreateOrderRequest:
    user_id: str
    security_name: str
    quantity: int


class YoloService(ABC):
    @abstractmethod
    async def get_balance(self, user_id: str) -> Money: ...

    @abstractmethod
    async def buy(self, request: CreateOrderRequest) -> Order: ...

    @abstractmethod
    async def sell(self, request: CreateOrderRequest) -> Order: ...

    @abstractmethod
    async def get_portfolio(self, user_id: str) -> list[PortfolioEntry]: ...

    @abstractmethod
    async def update_allowances(self) -> None: ...

    @abstractmethod
    async def take_portfolio_snapshots(self) -> None: ...

    @abstractmethod
    async def get_portfolio_snapshots(
        self, user_id: str
    ) -> list[PortfolioSnapshot]: ...

    @abstractmethod
    async def send_gift(
        self, from_user_id: str, to_user_id: str, amount: Money
    ) -> None: ...


class NotEnoughMoneyException(Exception):
    available_funds: Money
    required_funds: Money

    def __init__(self, available_funds: Money, required_funds: Money) -> None:
        super().__init__()
        self.available_funds = available_funds
        self.required_funds = required_funds


class NotEnoughQuantityException(Exception):
    available_quantity: int

    def __init__(self, available_quantity: int) -> None:
        super().__init__()
        self.available_quantity = available_quantity


class YoloServiceImpl(YoloService):
    logger: Logger
    database: Database
    security_service: SecurityService

    def __init__(
        self,
        logger: Logger,
        database: Database,
        security_service: SecurityService,
    ) -> None:
        self.logger = logger
        self.database = database
        self.security_service = security_service

    async def get_balance(self, user_id: str) -> Money:
        await self.create_user(user_id)
        async with self.database.tx() as database:
            return await database.get_user_balance(user_id)

    async def buy(self, request: CreateOrderRequest) -> Order:
        await self.create_user(request.user_id)
        async with self.database.tx() as tx:
            balance = await tx.get_user_balance(request.user_id)
            security_price = await self.security_service.get_security_price(
                request.security_name
            )
            if security_price is None:
                raise Exception(
                    f"Could not fetch price of security ${request.security_name}"
                )
            debit_amount = security_price * request.quantity
            if debit_amount > balance:
                raise NotEnoughMoneyException(
                    available_funds=balance,
                    required_funds=debit_amount,
                )
            debit = await tx.create_transaction(
                TransactionInsert(
                    user_id=request.user_id,
                    type=TransactionType.DEBIT,
                    amount=debit_amount,
                    comment=f"Buy for {request.quantity} of ${request.security_name}",
                )
            )
            order = await tx.create_order(
                OrderInsert(
                    user_id=request.user_id,
                    transaction_id=debit.id,
                    type=OrderType.BUY,
                    security_name=request.security_name,
                    security_price=security_price,
                    quantity=request.quantity,
                )
            )
            return order

    async def sell(self, request: CreateOrderRequest) -> Order:
        await self.create_user(request.user_id)
        async with self.database.tx() as tx:
            quantity = await tx.get_user_security_quantity(
                request.user_id, request.security_name
            )
            if quantity < request.quantity:
                raise NotEnoughQuantityException(available_quantity=quantity)
            security_price = await self.security_service.get_security_price(
                request.security_name
            )
            if security_price is None:
                raise Exception(
                    f"Could not fetch price of security ${request.security_name}"
                )
            credit_amount = security_price * request.quantity
            credit = await tx.create_transaction(
                TransactionInsert(
                    user_id=request.user_id,
                    type=TransactionType.CREDIT,
                    amount=credit_amount,
                    comment=f"Sell for {request.quantity} of ${request.security_name}",
                )
            )
            order = await tx.create_order(
                OrderInsert(
                    user_id=request.user_id,
                    transaction_id=credit.id,
                    type=OrderType.SELL,
                    security_name=request.security_name,
                    security_price=security_price,
                    quantity=request.quantity,
                )
            )
            return order

    async def create_user(self, user_id: str):
        async with self.database.tx() as tx:
            is_new_user = await tx.create_user(user_id)
            if is_new_user:
                config = get_config()
                self.logger.info(
                    f"New user <@{user_id}> created, granting starting balance of {config.starting_balance}"
                )
                await tx.create_allowance(user_id)
                await tx.create_transaction(
                    TransactionInsert(
                        user_id=user_id,
                        type=TransactionType.CREDIT,
                        amount=config.starting_balance,
                        comment="Initial credit",
                    )
                )

    async def get_portfolio(
        self, user_id: str, create_user: bool = True, tx: Tx | None = None
    ) -> list[PortfolioEntry]:
        if create_user:
            await self.create_user(user_id)
        if tx is not None:
            owned_securities = await tx.get_owned_securities(user_id)
        else:
            async with self.database.tx() as tx:
                owned_securities = await tx.get_owned_securities(user_id)
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
                total_price_paid=security.total_price_paid,
                return_rate=calculate_return_rate(
                    security.total_price_paid,
                    security.quantity * current_prices[security.name],
                ),
            )
            for security in owned_securities
        ]

    async def update_allowances(self) -> None:
        self.logger.info("Granting user allowances")
        config = get_config()
        async with self.database.tx() as tx:
            user_ids = await tx.get_eligible_users_for_allowance()
            for user_id in user_ids:
                await tx.create_allowance(user_id)
                await tx.create_transaction(
                    TransactionInsert(
                        user_id=user_id,
                        type=TransactionType.CREDIT,
                        amount=config.weekly_allowance,
                        comment="Weekly allowance",
                    )
                )

    async def take_portfolio_snapshots(self) -> None:
        self.logger.info("Taking portfolio snapshots")
        async with self.database.tx() as tx:
            user_ids = await tx.get_all_users()
            for user_id in user_ids:
                portfolio = await self.get_portfolio(user_id, create_user=False, tx=tx)
                await tx.create_portfolio_snapshot(user_id, portfolio)

    async def get_portfolio_snapshots(self, user_id: str) -> list[PortfolioSnapshot]:
        latest_portfolio = await self.get_portfolio(user_id)
        async with self.database.tx() as tx:
            portfolio_snapshots = await tx.get_user_portfolio_snapshots(user_id)
        portfolio_snapshots.append(
            PortfolioSnapshot(
                created_at=datetime.now(),
                entries=latest_portfolio,
            )
        )
        return portfolio_snapshots

    async def send_gift(
        self, from_user_id: str, to_user_id: str, amount: Money
    ) -> None:
        # Ensure both users exist before starting transaction
        await self.create_user(from_user_id)
        await self.create_user(to_user_id)

        async with self.database.tx() as tx:
            from_user_balance = await tx.get_user_balance(from_user_id)
            if from_user_balance < amount:
                raise NotEnoughMoneyException(
                    available_funds=from_user_balance, required_funds=amount
                )
            await tx.create_transaction(
                TransactionInsert(
                    user_id=from_user_id,
                    type=TransactionType.DEBIT,
                    amount=amount,
                    comment=f"Gift to @{to_user_id}",
                )
            )
            await tx.create_transaction(
                TransactionInsert(
                    user_id=to_user_id,
                    type=TransactionType.CREDIT,
                    amount=amount,
                    comment=f"Gift from @{from_user_id}",
                )
            )
