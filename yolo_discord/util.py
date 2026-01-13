import json
from dataclasses import dataclass
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


@dataclass
class Table[T]:
    column_headers: list[str]
    column_lengths: list[int]
    column_data: dict[str, list[str]]
    data_length: int

    def __init__(
        self,
        column_headers: list[str],
        formatters: dict[str, Callable[[T], str]],
        data: list[T],
    ) -> None:
        self.column_headers = column_headers
        self.column_lengths = [len(header) for header in column_headers]
        self.column_data = {header: [] for header in column_headers}
        for datum in data:
            for i, header in enumerate(column_headers):
                item = formatters[header](datum)
                self.column_lengths[i] = max(self.column_lengths[i], len(item))
                self.column_data[header].append(item)
        self.data_length = len(data)

    def format(self, include_header: bool = True) -> str:
        header_column = "│"
        divider_column = "├"
        bottom_divider_column = "└"
        for i, header in enumerate(self.column_headers):
            header_len = self.column_lengths[i]
            header_column += f" {header.rjust(header_len, ' ')} │"
            divider_column += f"─{'─' * header_len}─"
            bottom_divider_column += f"─{'─' * header_len}─"
            if i < len(self.column_headers) - 1:
                divider_column += "┼"
                bottom_divider_column += "┴"
            else:
                divider_column += "┤"
                bottom_divider_column += "┘"
        data_columns: list[str] = []
        for i in range(self.data_length):
            data_column = "│"
            for j, header in enumerate(self.column_headers):
                column_len = self.column_lengths[j]
                data_column += (
                    f" {self.column_data[header][i].rjust(column_len, ' ')} │"
                )
            data_columns.append(data_column)
        rows: list[str] = []
        if include_header:
            rows.append(header_column)
            rows.append(divider_column)
        rows.extend(data_columns)
        rows.append(bottom_divider_column)
        return "\n".join(rows)

    def width(self) -> int:
        return 1 + sum(self.column_lengths) + 3 * len(self.column_lengths)


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
