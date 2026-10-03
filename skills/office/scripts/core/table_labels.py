from __future__ import annotations

from core.office_operations import TARGET_NOT_FOUND
from core.office_result import INVALID_VALUE, OfficeFailure
from core.office_schema import Field, Number, Text, closest_name


LISTED_LABELS_LIMIT = 12
INDEX = Number(minimum=0, integer=True)
ROW_FIELD = Field("row", INDEX, "row index from 0; give row or rowLabel")
ROW_LABEL_FIELD = Field("rowLabel", Text(non_empty=True), "exact text of a cell in the row, such as a total row's label or an item's number, as office read shows it; it must be in exactly one row")
COLUMN_FIELD = Field("column", INDEX, "column index from 0; give column or columnLabel")
COLUMN_LABEL_FIELD = Field("columnLabel", Text(non_empty=True), "exact text of a cell in the column, such as its header, as office read shows it; it must be in exactly one column")
CELL_ADDRESS_FIELDS = (ROW_FIELD, ROW_LABEL_FIELD, COLUMN_FIELD, COLUMN_LABEL_FIELD)


def resolve_cell_address(rows: list[list[str]], operation: dict, location: str) -> tuple[int, int]:
    return resolve_table_axis(rows, operation, "row", location), resolve_table_axis(transposed(rows), operation, "column", location)


def resolve_table_axis(lines: list[list[str]], operation: dict, axis: str, location: str) -> int:
    index, label = operation.get(axis), operation.get(f"{axis}Label")
    if (index is None) == (label is None):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: give exactly one of {axis} and {axis}Label", location, suggestion=f"name the {axis} by its index or by the exact text of a cell in it, as office read shows them"))
    if label is None:
        return index
    return line_holding(lines, label, axis, f"{location}.{axis}Label")


def line_holding(lines: list[list[str]], label: str, axis: str, location: str) -> int:
    wanted = label.strip()
    matches = [index for index, cells in enumerate(lines) if wanted in (cell.strip() for cell in cells)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}: {label!r} is in {axis}s {spoken_list(matches)}, so it names no single {axis}", location, suggestion=f"give the {axis} index of the one you mean"))
    raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}: no {axis} has a cell reading {label!r}", location, suggestion=labels_suggestion(label, lines)))


def labels_suggestion(written: str, lines: list[list[str]]) -> str:
    labels = list(dict.fromkeys(label for label in (first_text(cells) for cells in lines) if label))
    if not labels:
        return "the table has no text to name it by; give the index"
    match = closest_name(written, labels)
    guess = f"did you mean {match!r}? " if match else ""
    return f"{guess}use the exact text office read shows, such as {abridged(labels)}"


def first_text(cells: list[str]) -> str:
    return next((cell.strip() for cell in cells if cell.strip()), "")


def abridged(labels: list[str]) -> str:
    quoted = [repr(label) for label in labels]
    if len(quoted) <= LISTED_LABELS_LIMIT:
        return ", ".join(quoted)
    half = LISTED_LABELS_LIMIT // 2
    return ", ".join(quoted[:half]) + ", …, " + ", ".join(quoted[-half:])


def spoken_list(indexes: list[int]) -> str:
    if len(indexes) == 2:
        return f"{indexes[0]} and {indexes[1]}"
    return ", ".join(str(index) for index in indexes[:-1]) + f" and {indexes[-1]}"


def transposed(rows: list[list[str]]) -> list[list[str]]:
    width = max((len(row) for row in rows), default=0)
    return [[row[column] for row in rows if column < len(row)] for column in range(width)]
