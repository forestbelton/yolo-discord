import json
from decimal import Decimal
from moneyed import Money
from typing import Any, Iterable
from yolo_discord.types import PortfolioEntry


def from_cents(cents: int) -> Money:
    amount = Decimal(cents) / 100
    return Money(amount, "USD")


def format_return_rate(return_rate: float) -> str:
    if abs(return_rate - 0) < 0.001:
        return_rate = 0
    sign = ""
    if return_rate >= 0:
        sign = "+"
    return f"{sign}{return_rate:.2f}%"


def calculate_return_rate(paid_price: Money, current_price: Money) -> float:
    paid = paid_price.get_amount_in_sub_unit()
    if paid <= 0:
        return 0
    current = current_price.get_amount_in_sub_unit()
    rate = (current - paid) / paid
    return round(rate * 100, 2)


def sum_money(moneys: Iterable[Money]) -> Money:
    total = Money(0, "USD")
    for money in moneys:
        total += money
    return total


class PortfolioEntryEncoder(json.JSONEncoder):
    """Custom JSON encoder for PortfolioEntry dataclass."""

    def default(self, o: Any) -> Any:
        if isinstance(o, PortfolioEntry):
            return {
                "security_name": o.security_name,
                "balance": o.balance.get_amount_in_sub_unit(),
                "quantity": o.quantity,
                "total_price_paid": o.total_price_paid.get_amount_in_sub_unit(),
                "return_rate": o.return_rate,
            }
        return super().default(o)


class PortfolioEntryDecoder(json.JSONDecoder):
    """Custom JSON decoder for PortfolioEntry dataclass."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(object_hook=self.__object_hook, *args, **kwargs)

    @staticmethod
    def __object_hook(obj: dict[str, Any]) -> Any:
        # Check if this dict has the keys for a PortfolioEntry
        if all(
            key in obj
            for key in [
                "security_name",
                "balance",
                "quantity",
                "total_price_paid",
                "return_rate",
            ]
        ):
            return PortfolioEntry(
                security_name=obj["security_name"],
                balance=from_cents(obj["balance"]),
                quantity=obj["quantity"],
                total_price_paid=from_cents(obj["total_price_paid"]),
                return_rate=obj["return_rate"],
            )
        return obj
