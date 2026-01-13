import json
from decimal import Decimal
from moneyed import Money
from typing import Any, Callable
from yolo_discord.types import PortfolioEntry


def from_cents(cents: int) -> Money:
    amount = Decimal(cents) / 100
    return Money(amount, "USD")


def format_return_rate(entry: PortfolioEntry) -> str:
    return_rate = entry.return_rate
    if abs(return_rate - 0) < 0.001:
        return_rate = 0
    sign = ""
    if entry.return_rate >= 0:
        sign = "+"
    return f"{sign}{return_rate:.2f}%"


def format_table[T](
    column_headers: list[str],
    formatters: dict[str, Callable[[T], str]],
    data: list[T],
) -> str:
    column_lengths: list[int] = [len(header) for header in column_headers]
    column_data: dict[str, list[str]] = {header: [] for header in column_headers}
    for datum in data:
        for i, header in enumerate(column_headers):
            item = formatters[header](datum)
            column_lengths[i] = max(column_lengths[i], len(item))
            column_data[header].append(item)

    header_column = "|"
    divider_column = "|"
    for i, header in enumerate(column_headers):
        header_len = column_lengths[i]
        header_column += f" {header.rjust(header_len, ' ')} |"
        divider_column += f"-{'-' * header_len}-|"

    data_columns: list[str] = []
    for i, datum in enumerate(data):
        data_column = "|"
        for j, header in enumerate(column_headers):
            column_len = column_lengths[j]
            data_column += f" {column_data[header][i].rjust(column_len, ' ')} |"
        data_columns.append(data_column)

    return "\n".join(
        [
            header_column,
            divider_column,
            "\n".join(data_columns),
            divider_column,
        ]
    )


class PortfolioEntryEncoder(json.JSONEncoder):
    """Custom JSON encoder for PortfolioEntry dataclass."""

    def default(self, o: Any) -> Any:
        if isinstance(o, PortfolioEntry):
            return {
                "security_name": o.security_name,
                "balance": o.balance.get_amount_in_sub_unit(),
                "quantity": o.quantity,
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
                "return_rate",
            ]
        ):
            return PortfolioEntry(
                security_name=obj["security_name"],
                balance=from_cents(obj["balance"]),
                quantity=obj["quantity"],
                return_rate=obj["return_rate"],
            )
        return obj
