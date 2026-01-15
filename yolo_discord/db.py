import asyncio
from abc import ABC, abstractmethod
from aiosqlite import connect, Connection, Row
from contextlib import asynccontextmanager
from datetime import datetime
from json import dumps, loads
from moneyed import Money
from typing import AsyncIterator

from yolo_discord.dto import (
    Transaction,
    TransactionInsert,
    Order,
    OrderInsert,
    OwnedSecurity,
    PortfolioEntry,
    PortfolioSnapshot,
)
from yolo_discord.util import from_cents, PortfolioEntryDecoder, PortfolioEntryEncoder


class Tx(ABC):
    @abstractmethod
    async def create_user(self, user_id: str) -> bool: ...

    @abstractmethod
    async def create_transaction(self, request: TransactionInsert) -> Transaction: ...

    @abstractmethod
    async def get_user_balance(self, user_id: str) -> Money: ...

    @abstractmethod
    async def create_order(self, request: OrderInsert) -> Order: ...

    @abstractmethod
    async def get_owned_securities(self, user_id: str) -> list[OwnedSecurity]: ...

    @abstractmethod
    async def create_allowance(self, user_id: str) -> None: ...

    @abstractmethod
    async def get_eligible_users_for_allowance(self) -> list[str]: ...

    @abstractmethod
    async def get_user_security_quantity(
        self, user_id: str, security_name: str
    ) -> int: ...

    @abstractmethod
    async def create_portfolio_snapshot(
        self, user_id: str, portfolio: list[PortfolioEntry]
    ) -> None: ...

    @abstractmethod
    async def get_user_portfolio_snapshots(
        self, user_id: str
    ) -> list[PortfolioSnapshot]: ...

    @abstractmethod
    async def get_all_users(self) -> list[str]: ...


class Database(ABC):
    @abstractmethod
    @asynccontextmanager
    async def tx(self) -> AsyncIterator[Tx]:
        raise NotImplementedError()
        yield


class DatabaseImpl(Database):
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.connection.row_factory = Row
        self.transaction_lock = asyncio.Lock()

    @staticmethod
    async def create(url: str) -> "DatabaseImpl":
        return DatabaseImpl(await connect(url))

    @asynccontextmanager
    async def tx(self) -> AsyncIterator[Tx]:
        await self.transaction_lock.acquire()
        try:
            await self.connection.execute("BEGIN IMMEDIATE")
            yield TxImpl(self.connection)
            await self.connection.commit()
        except:
            await self.connection.rollback()
            raise
        finally:
            self.transaction_lock.release()


class TxImpl(Tx):
    connection: Connection

    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.connection.row_factory = Row

    async def create_user(self, user_id: str) -> bool:
        cursor = await self.connection.execute(
            "INSERT OR IGNORE INTO discord_users (user_id) VALUES (:user_id)",
            {"user_id": user_id},
        )
        return cursor.rowcount > 0

    async def create_transaction(self, request: TransactionInsert) -> Transaction:
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
        return Transaction(
            id=cursor.lastrowid,
            created_at=datetime.now(),
            user_id=request.user_id,
            type=request.type,
            amount=request.amount,
            comment=request.comment,
        )

    async def get_user_balance(self, user_id: str) -> Money:
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

    async def create_order(self, request: OrderInsert) -> Order:
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
        return Order(
            id=cursor.lastrowid,
            created_at=datetime.now(),
            user_id=request.user_id,
            transaction_id=request.transaction_id,
            type=request.type,
            security_name=request.security_name,
            security_price=request.security_price,
            quantity=request.quantity,
        )

    async def get_owned_securities(self, user_id: str) -> list[OwnedSecurity]:
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
            OwnedSecurity(
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
        self, user_id: str, portfolio: list[PortfolioEntry]
    ) -> None:
        data = dumps(
            portfolio,
            cls=PortfolioEntryEncoder,
            separators=(",", ":"),
        )
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

    async def get_user_portfolio_snapshots(
        self, user_id: str
    ) -> list[PortfolioSnapshot]:
        rows = await self.connection.execute_fetchall(
            """
            SELECT created_at, data
            FROM portfolio_snapshots
            WHERE user_id = :user_id
            ORDER BY created_at ASC
            """,
            {"user_id": user_id},
        )
        return [
            PortfolioSnapshot(
                created_at=datetime.strptime(row["created_at"], "%Y-%m-%d"),
                entries=loads(row["data"], cls=PortfolioEntryDecoder),
            )
            for row in rows
        ]
