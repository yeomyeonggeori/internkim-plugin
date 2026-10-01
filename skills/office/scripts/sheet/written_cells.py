from __future__ import annotations

from formula_grammar import formula_problem
from office_result import INVALID_VALUE, OfficeFailure
from sheet_definitions import FORMULA_SYNTAX


# Excel specifications and limits: a cell holds at most 32,767 characters and a formula at most 8,192
CELL_TEXT_LIMIT = 32767
FORMULA_LENGTH_LIMIT = 8192


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
