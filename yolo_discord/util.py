from decimal import Decimal
from moneyed import Money


def from_cents(cents: int) -> Money:
    amount = Decimal(cents) / 100
    return Money(amount, "USD")
