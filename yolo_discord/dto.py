from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from moneyed import Money


class TransactionType(Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class TransactionInsert:
    user_id: str
    type: TransactionType
    amount: Money
    comment: str


@dataclass
class Transaction:
    id: int
    created_at: datetime
    user_id: str
    type: TransactionType
    amount: Money
    comment: str


@dataclass
class OrderInsert:
    user_id: str
    transaction_id: int
    type: OrderType
    security_name: str
    security_price: Money
    quantity: int


@dataclass
class Order:
    id: int
    created_at: datetime
    user_id: str
    transaction_id: int
    type: OrderType
    security_name: str
    security_price: Money
    quantity: int


@dataclass
class OwnedSecurity:
    name: str
    quantity: int
    total_price_paid: Money


@dataclass
class PortfolioEntry:
    security_name: str
    balance: Money
    quantity: int
    total_price_paid: Money
    return_rate: float


@dataclass
class PortfolioSnapshot:
    created_at: datetime
    entries: list[PortfolioEntry]
