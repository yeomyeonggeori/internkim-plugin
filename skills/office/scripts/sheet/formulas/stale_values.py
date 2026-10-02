from __future__ import annotations

import datetime
import math
from collections import defaultdict

from openpyxl.utils.datetime import to_excel

from core.office_result import Issue
from sheet.sheet_definitions import STALE_CACHED_VALUE
from sheet.workbook.access import open_workbook
from sheet.formulas.evaluation import BOOLEAN, NUMBER, ERROR, TEXT, CachedValue, Evaluation


LISTED_CELL_LIMIT = 20
EXAMPLE_LIMIT = 3
RELATIVE_TOLERANCE = 1e-9
ABSOLUTE_TOLERANCE = 1e-9


def stale_cached_value_issues(path: str, evaluation: Evaluation) -> list[Issue]:
    stored = open_workbook(path, data_only=True)
    by_sheet = defaultdict(list)
    for (sheet, coordinate), computed in sorted(evaluation.values.items()):
        value = stored[sheet][coordinate].value
        if value is not None and not agrees(value, computed):
            by_sheet[sheet].append((f"{sheet}!{coordinate}", value, computed))
    return [stale_issue(sheet, cells) for sheet, cells in by_sheet.items()]


def agrees(stored: object, computed: CachedValue) -> bool:
    if computed.cell_type == NUMBER:
        return is_number(stored) and math.isclose(serial_number(stored), float(computed.text), rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE)
    if computed.cell_type == BOOLEAN:
        return isinstance(stored, bool) and stored == (computed.text == "1")
    if computed.cell_type in (TEXT, ERROR):
        return isinstance(stored, str) and stored == computed.text
    return True


def is_number(value: object) -> bool:
    return isinstance(value, (int, float, datetime.date, datetime.datetime)) and not isinstance(value, bool)


def serial_number(value: object) -> float:
    return float(to_excel(value)) if isinstance(value, (datetime.date, datetime.datetime)) else float(value)


def shown(value: object) -> str:
    return value.text if isinstance(value, CachedValue) else str(value)


def stale_issue(sheet: str, cells: list) -> Issue:
    examples = ", ".join(f"{label} stores {shown(stored)} but computes {shown(computed)}" for label, stored, computed in cells[:EXAMPLE_LIMIT])
    labels = [label for label, _, _ in cells]
    hidden = len(labels) - LISTED_CELL_LIMIT
    listed = ", ".join(labels[:LISTED_CELL_LIMIT]) + (f" and {hidden} more" if hidden > 0 else "")
    return STALE_CACHED_VALUE.issue(f"{len(cells)} formula cells on {sheet} store a value that differs from the computed one ({examples}): {listed}", labels[0], fix=[{"op": "recalculate"}])
