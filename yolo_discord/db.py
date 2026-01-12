import abc
import aiosqlite
import datetime
import moneyed

from yolo_discord import types
from yolo_discord.util import from_cents


class Database(abc.ABC):
    @abc.abstractmethod
    async def create_user(self, user_id: str) -> bool: ...

    @abc.abstractmethod
    async def create_transaction(
        self, request: types.TransactionInsert
    ) -> types.Transaction: ...

    @abc.abstractmethod
    async def get_user_balance(self, user_id: str) -> moneyed.Money: ...

    @abc.abstractmethod
    async def create_order(self, request: types.OrderInsert) -> types.Order: ...

    @abc.abstractmethod
    async def commit(self) -> None: ...

    @abc.abstractmethod
    async def rollback(self) -> None: ...


class DatabaseImpl(Database):
    connection: aiosqlite.Connection

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.connection = connection
        self.connection.row_factory = aiosqlite.Row

    @staticmethod
    async def create(url: str) -> "DatabaseImpl":
        return DatabaseImpl(await aiosqlite.connect(url))

    async def create_user(self, user_id: str) -> bool:
        cursor = await self.connection.execute(
            "INSERT OR IGNORE INTO discord_users (user_id) VALUES (:user_id)",
            {"user_id": user_id},
        )
        return cursor.rowcount > 0

    async def create_transaction(
        self, request: types.TransactionInsert
    ) -> types.Transaction:
        cursor = await self.connection.execute(
            """
            INSERT INTO transactions (
                user_id,
                type,
                amount_cents,
                comment
            ) VALUES (
                :user_id,
                :type,
                :amount_cents,
                :comment
            )
            """,
            {
                "user_id": request.user_id,
                "type": request.type.value,
                "amount_cents": request.amount.get_amount_in_sub_unit(),
                "comment": request.comment,
            },
        )
        if cursor.lastrowid is None:
            raise Exception("could not insert transaction")
        return types.Transaction(
            id=cursor.lastrowid,
            created_at=datetime.datetime.now(),
            user_id=request.user_id,
            type=request.type,
            amount=request.amount,
            comment=request.comment,
        )

    async def get_user_balance(self, user_id: str) -> moneyed.Money:
        cursor = await self.connection.execute(
            """
            SELECT COALESCE(
                SUM(
                    CASE WHEN type = 'DEBIT' THEN -amount_cents
                    ELSE amount_cents
                    END
                ),
                0
            ) AS balance_cents
            FROM transactions
            WHERE user_id = :user_id
            """,
            {"user_id": user_id},
        )
        row = await cursor.fetchone()
        if row is None:
            raise Exception("could not get user balance")
        return from_cents(row["balance_cents"])

    async def create_order(self, request: types.OrderInsert) -> types.Order:
        cursor = await self.connection.execute(
            """
            INSERT INTO orders (
                user_id,
                transaction_id,
                type,
                security_name,
                security_price_cents,
                quantity
            ) VALUES (
                :user_id,
                :transaction_id,
                :type,
                :security_name,
                :security_price_cents,
                :quantity
            )
            """,
            {
                "user_id": request.user_id,
                "transaction_id": request.transaction_id,
                "type": request.type.value,
                "security_name": request.security_name,
                "security_price_cents": request.security_price.get_amount_in_sub_unit(),
                "quantity": request.quantity,
            },
        )
        if cursor.lastrowid is None:
            raise Exception("could not create order")
        return types.Order(
            id=cursor.lastrowid,
            created_at=datetime.datetime.now(),
            user_id=request.user_id,
            transaction_id=request.transaction_id,
            type=request.type,
            security_name=request.security_name,
            security_price=request.security_price,
            quantity=request.quantity,
        )

    async def commit(self) -> None:
        await self.connection.commit()

    async def rollback(self) -> None:
        await self.connection.rollback()
