import abc
import aiosqlite
import datetime
import json
import moneyed

from yolo_discord import types
from yolo_discord.util import from_cents, PortfolioEntryEncoder


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
    async def get_owned_securities(self, user_id: str) -> list[types.OwnedSecurity]: ...

    @abc.abstractmethod
    async def create_allowance(self, user_id: str) -> None: ...

    @abc.abstractmethod
    async def get_eligible_users_for_allowance(self) -> list[str]: ...

    @abc.abstractmethod
    async def get_user_security_quantity(
        self, user_id: str, security_name: str
    ) -> int: ...

    @abc.abstractmethod
    async def create_portfolio_snapshot(
        self, user_id: str, portfolio: list[types.PortfolioEntry]
    ) -> None: ...

    @abc.abstractmethod
    async def get_all_users(self) -> list[str]: ...

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

    async def get_owned_securities(self, user_id: str) -> list[types.OwnedSecurity]:
        rows = list(
            await self.connection.execute_fetchall(
                """
                SELECT *
                FROM (
                    SELECT
                        security_name,
                        SUM(
                            quantity * (
                                CASE WHEN type = 'BUY' THEN 1
                                ELSE -1 END
                            )
                        ) AS quantity,
                        SUM(
                            security_price_cents * quantity * (
                                CASE WHEN type = 'BUY' THEN 1
                                ELSE -1 END
                            )
                        ) AS total_price_paid
                    FROM orders
                    WHERE user_id = :user_id
                    GROUP BY security_name
                )
                WHERE quantity > 0
                """,
                {"user_id": user_id},
            )
        )
        return [
            types.OwnedSecurity(
                name=row["security_name"],
                quantity=row["quantity"],
                total_price_paid=from_cents(row["total_price_paid"]),
            )
            for row in rows
        ]

    async def create_allowance(self, user_id: str) -> None:
        await self.connection.execute(
            "INSERT INTO allowances (user_id) VALUES (:user_id)",
            {"user_id": user_id},
        )

    async def get_eligible_users_for_allowance(self) -> list[str]:
        rows = await self.connection.execute_fetchall(
            """
            SELECT du.user_id
            FROM discord_users du
            LEFT JOIN allowances a 
                ON du.user_id = a.user_id 
                AND a.created_at > date('now', '-7 days')
            WHERE a.user_id IS NULL;
            """
        )
        return [row["user_id"] for row in rows]

    async def get_user_security_quantity(self, user_id: str, security_name: str) -> int:
        cursor = await self.connection.execute(
            """
            SELECT SUM(
                quantity * (
                    CASE WHEN type = 'BUY' THEN 1
                    ELSE -1 END
                )
            ) AS quantity
            FROM orders
            WHERE user_id = :user_id
            AND security_name = :security_name
            """,
            {"user_id": user_id, "security_name": security_name},
        )
        row = await cursor.fetchone()
        if row is None:
            raise Exception("could not get user security quantity")
        return row["quantity"]

    async def create_portfolio_snapshot(
        self, user_id: str, portfolio: list[types.PortfolioEntry]
    ) -> None:
        data = json.dumps(portfolio, cls=PortfolioEntryEncoder)
        await self.connection.execute(
            """
            INSERT INTO portfolio_snapshots (
                user_id,
                data
            ) VALUES (
                :user_id,
                :data
            )
            """,
            {"user_id": user_id, "data": data},
        )

    async def get_all_users(self) -> list[str]:
        rows = await self.connection.execute_fetchall(
            "SELECT user_id FROM discord_users"
        )
        return [row["user_id"] for row in rows]

    async def commit(self) -> None:
        await self.connection.commit()

    async def rollback(self) -> None:
        await self.connection.rollback()
