from __future__ import annotations

import datetime
import os
from typing import Iterable

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string, range_boundaries
from openpyxl.utils.exceptions import CellCoordinatesException

from office_operations import TARGET_NOT_FOUND
from office_result import INVALID_VALUE, OfficeFailure
from office_schema import closest_suggestion, did_you_mean


def is_macro_workbook(path: str) -> bool:
    return path.lower().endswith(".xlsm")


def open_workbook(path: str, data_only: bool = False):
    if not os.path.exists(path):
        raise FileNotFoundError(2, "No such file or directory", path)
    return load_workbook(path, data_only=data_only, keep_vba=is_macro_workbook(path))


def resolve_sheet(workbook, sheet_name: str | None, location: str):
    if sheet_name is None:
        return workbook.worksheets[0]
    match = next((worksheet for worksheet in workbook.worksheets if worksheet.title == sheet_name), None)
    if match is None:
        names = ", ".join(workbook.sheetnames)
        message = f"{location}: the workbook has no sheet named {sheet_name!r}{did_you_mean(sheet_name, workbook.sheetnames)}; it has {names}"
        raise OfficeFailure(TARGET_NOT_FOUND.issue(message, location, closest_suggestion(sheet_name, workbook.sheetnames, 'use "sheet": "{match}"')))
    return match


MAXIMUM_COLUMN = 16384


def sheet_of(workbook, operation: dict, location: str):
    return resolve_sheet(workbook, operation.get("sheet"), f"{location}.sheet")


def column_index(text: str, location: str) -> int:
    letters = text.strip().upper()
    if not letters.isalpha() or not letters.isascii() or len(letters) > 3 or column_index_from_string(letters) > MAXIMUM_COLUMN:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: {text!r} is not a column letter such as C", location))
    return column_index_from_string(letters)


def parse_cell(text: str, location: str) -> tuple[int, int]:
    try:
        column_letters, row = coordinate_from_string(text.replace("$", ""))
    except CellCoordinatesException as error:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: {text!r} is not a cell address such as B7", location)) from error
    bounds = range_boundaries(f"{column_letters}{row}")
    return bounds[1], bounds[0]


def parse_range(text: str, location: str) -> tuple[int, int, int, int]:
    try:
        min_column, min_row, max_column, max_row = range_boundaries(text.replace("$", "").upper())
    except (ValueError, TypeError) as error:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: {text!r} is not a range such as A1:D10", location)) from error
    if None in (min_column, min_row, max_column, max_row):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: {text!r} must name both corners, such as A1:D10", location))
    return min_row, min_column, max_row, max_column


def json_value(value):
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def formula_text(cell) -> str | None:
    if cell.data_type != "f":
        return None
    return cell.value if isinstance(cell.value, str) else "{array formula}"


def cell_rows(worksheet, bounds: tuple[int, int, int, int]) -> Iterable:
    min_row, min_column, max_row, max_column = bounds
    return worksheet.iter_rows(min_row=min_row, min_col=min_column, max_row=max_row, max_col=max_column)
