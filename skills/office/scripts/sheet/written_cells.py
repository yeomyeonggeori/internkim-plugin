from __future__ import annotations

from sheet.cell_values import argument_row
from sheet.formula_grammar import formula_problem
from core.office_result import INVALID_VALUE, OfficeFailure
from sheet.sheet_definitions import FORMULA_SYNTAX
from core.excel_limits import CELL_TEXT_LIMIT, FORMULA_LENGTH_LIMIT


QUOTED_COMMA_EXAMPLE = "--row 'Item,\"1,500\"'"


def is_formula(value: object) -> bool:
    return isinstance(value, str) and value.startswith("=") and len(value) > 1


def require_writable(value: object, location: str, keeps_text: bool = False) -> None:
    if not isinstance(value, str):
        return
    if len(value) > CELL_TEXT_LIMIT:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: the text is {len(value)} characters and an Excel cell holds at most {CELL_TEXT_LIMIT}", location, "split the text over several cells or shorten it"))
    if keeps_text or not is_formula(value):
        return
    if len(value) > FORMULA_LENGTH_LIMIT:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: the formula is {len(value)} characters and Excel allows at most {FORMULA_LENGTH_LIMIT}", location, "split the calculation over helper cells"))
    problem = formula_problem(value)
    if problem is not None:
        raise OfficeFailure(FORMULA_SYNTAX.issue(f"{location}: the formula {value} {problem}", location))


def require_writable_rows(rows: list, location: str) -> None:
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            require_writable(value, f"{location}[{row_index}][{column_index}]")


def argument_rows(texts: list[str], header_width: int | None) -> list[list]:
    rows = [argument_row(text) for text in texts]
    width = header_width or (len(rows[0]) if rows else 0)
    for number, (text, row) in enumerate(zip(texts, rows), start=1):
        if len(row) > width:
            raise OfficeFailure(INVALID_VALUE.issue(
                f"--row {number} ({text}) has {len(row)} cells and the header has {width}",
                "--row",
                f"a comma inside a value splits it into two cells: quote that value, such as {QUOTED_COMMA_EXAMPLE}, or pass the rows as a JSON file",
            ))
    require_writable_rows(rows, "--row")
    return rows
