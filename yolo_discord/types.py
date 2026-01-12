import dataclasses
import datetime
import enum
import moneyed


class TransactionType(enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class OrderType(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclasses.dataclass
class TransactionInsert:
    user_id: str
    type: TransactionType
    amount: moneyed.Money
    comment: str


@dataclasses.dataclass
class Transaction:
    id: int
    created_at: datetime.datetime
    user_id: str
    type: TransactionType
    amount: moneyed.Money
    comment: str


@dataclasses.dataclass
class OrderInsert:
    user_id: str
    transaction_id: int
    type: OrderType
    security_name: str
    security_price: moneyed.Money
    quantity: int


@dataclasses.dataclass
class CreateOrderRequest:
    user_id: str
    security_name: str
    quantity: int


@dataclasses.dataclass
class Order:
    id: int
    created_at: datetime.datetime
    user_id: str
    transaction_id: int
    type: OrderType
    security_name: str
    security_price: moneyed.Money
    quantity: int
