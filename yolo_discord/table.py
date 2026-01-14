from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Table:
    column_headers: list[str]
    column_lengths: list[int]
    column_data: dict[str, list[str]]
    include_header: bool
    data_length: int

    def __init__[T](
        self,
        column_headers: list[str],
        formatters: dict[str, Callable[[T], str]],
        data: list[T],
        include_header: bool = True,
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
        self.include_header = include_header

    def width(self) -> int:
        return 1 + sum(self.column_lengths) + 3 * len(self.column_lengths)


def format_tables(*tables: Table) -> str:
    output: list[str] = []
    for table_index, table in enumerate(tables):
        next_table: Optional[Table] = None
        if table_index < len(tables) - 1:
            next_table = tables[table_index + 1]
        bottom_divider_column = format_bottom_divider_column(table, next_table)
        header_column = "│"
        divider_column = "├"
        for i, header in enumerate(table.column_headers):
            header_len = table.column_lengths[i]
            header_column += f" {header.rjust(header_len, ' ')} │"
            divider_column += f"─{'─' * header_len}─"
            if i < len(table.column_headers) - 1:
                divider_column += "┼"
            else:
                divider_column += "┤"
        data_columns: list[str] = []
        for i in range(table.data_length):
            data_column = "│"
            for j, header in enumerate(table.column_headers):
                column_len = table.column_lengths[j]
                data_column += (
                    f" {table.column_data[header][i].rjust(column_len, ' ')} │"
                )
            data_columns.append(data_column)
        if table_index == 0:
            output.append(format_top_divider_column(table))
        if table.include_header:
            output.append(header_column)
            output.append(divider_column)
        output.extend(data_columns)
        output.append(bottom_divider_column)
    return "\n".join(output)


def format_divider_column(
    table: Table, left_char: str, middle_char: str, right_char: str
) -> str:
    column = left_char
    for i in range(len(table.column_headers)):
        column_len = table.column_lengths[i]
        column += f"─{'─' * column_len}─"
        if i < len(table.column_headers) - 1:
            column += middle_char
    column += right_char
    return column


def format_top_divider_column(table: Table) -> str:
    return format_divider_column(table, "┌", "┬", "┐")


def format_bottom_divider_column(table: Table, next_table: Optional[Table]) -> str:
    if next_table is None:
        return format_divider_column(table, "└", "┴", "┘")
    assert table.width() == next_table.width()
    bottom_divider_column = "├"
    top_connections: set[int] = set()
    bottom_connections: set[int] = set()
    i = 1
    for length in table.column_lengths:
        top_connections.add(i + length + 2)
        i += length + 3
    i = 1
    for length in next_table.column_lengths:
        bottom_connections.add(i + length + 2)
        i += length + 3
    for i in range(1, table.width() - 1):
        c = "─"
        if i in top_connections and i in bottom_connections:
            c = "┼"
        elif i in top_connections:
            c = "┴"
        elif i in bottom_connections:
            c = "┬"
        bottom_divider_column += c
    bottom_divider_column += "┤"
    return bottom_divider_column
