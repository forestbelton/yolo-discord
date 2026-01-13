from decimal import Decimal
from moneyed import Money
from typing import Callable


def from_cents(cents: int) -> Money:
    amount = Decimal(cents) / 100
    return Money(amount, "USD")


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
