#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from types import SimpleNamespace

from cell_values import typed_cell_value
from excel_functions import written_value
from office_inputs import read_text_input
from office_operations import apply_batch, save_atomically
from office_result import INVALID_ARGUMENTS, OfficeArgumentParser, OfficeFailure, Result, read_json_file, run_command
from office_schema import require_valid
from sheet_definitions import WORKBOOK_SPECIFICATION
from sheet_operations import SHEET_OPERATIONS, SheetEditing, save_editing
from sheet_styling import style_table
from sheet_workbook import validate_sheet_name
from written_cells import require_writable_rows


def optional_text(value):
    return (value or "").strip()


def read_specification(arguments):
    if arguments.spec:
        specification = read_json_file(arguments.spec)
        location = "spec"
    elif arguments.title or arguments.row:
        specification = build_specification(arguments)
        location = "arguments"
    else:
        raise OfficeFailure(INVALID_ARGUMENTS.issue("provide at least --title or --row, or pass --spec <file>"))
    require_valid(WORKBOOK_SPECIFICATION, specification, location)
    require_sheet_titles(specification, location)
    return specification


def require_sheet_titles(specification, location):
    taken = SimpleNamespace(sheetnames=[])
    for index, sheet_specification in enumerate(specification["sheets"]):
        title = sheet_specification["title"].strip()
        validate_sheet_name(taken, title, f"{location}.sheets[{index}].title")
        taken.sheetnames.append(title)


def create_workbook(specification):
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)
    workbook_title = optional_text(specification.get("title"))
    if workbook_title:
        workbook.properties.title = workbook_title

    for index, sheet_specification in enumerate(specification["sheets"]):
        worksheet = add_sheet(workbook, sheet_specification, get_column_letter, f"spec.sheets[{index}]")
        apply_default_formatting(worksheet, sheet_specification)

    return workbook


def add_sheet(workbook, sheet_specification, get_column_letter, location):
    title = sheet_specification["title"].strip()
    worksheet = workbook.create_sheet(title=title[:31])
    rows = read_rows(sheet_specification)
    require_writable_rows(rows, sheet_specification["csvPath"].strip() if sheet_specification.get("csvPath") else f"{location}.rows")
    heading = optional_text(sheet_specification.get("heading"))
    if heading:
        worksheet.append([heading])
    for row in rows:
        worksheet.append([written_value(value) for value in row])
    default_freeze_panes = "A3" if heading else "A2"
    freeze_panes = sheet_specification.get("freezePanes", default_freeze_panes)
    header_row = header_row_index(sheet_specification)
    if isinstance(freeze_panes, str) and freeze_panes.strip() and worksheet.max_row >= header_row:
        worksheet.freeze_panes = freeze_panes.strip()
    if sheet_specification.get("autoFilter", True) and worksheet.max_row > 0 and worksheet.max_column > 0:
        worksheet.auto_filter.ref = auto_filter_reference(worksheet, header_row, get_column_letter)
    return worksheet


def header_row_index(sheet_specification):
    return 2 if optional_text(sheet_specification.get("heading")) else 1


def auto_filter_reference(worksheet, header_row, get_column_letter):
    if worksheet.max_row < header_row:
        return worksheet.dimensions
    return f"A{header_row}:{get_column_letter(worksheet.max_column)}{worksheet.max_row}"


def read_rows(sheet_specification):
    if sheet_specification.get("csvPath"):
        return read_delimited_rows(sheet_specification)
    return sheet_specification.get("rows") or []


def read_delimited_rows(sheet_specification):
    csv_path = sheet_specification["csvPath"].strip()
    delimiter = sheet_specification.get("delimiter") or ","
    if delimiter == "\\t":
        delimiter = "\t"
    return [[typed_cell_value(text) for text in row] for row in csv.reader(io.StringIO(read_text_input(csv_path), newline=""), delimiter=delimiter)]


def apply_default_formatting(worksheet, sheet_specification):
    if worksheet.max_row == 0:
        return
    style_table(worksheet, bool(optional_text(sheet_specification.get("heading"))))
    apply_column_widths(worksheet, sheet_specification)
    apply_column_number_formats(worksheet, sheet_specification)


def apply_column_widths(worksheet, sheet_specification):
    for column_letter, width in (sheet_specification.get("columnWidths") or {}).items():
        worksheet.column_dimensions[column_letter.upper()].width = max(float(width), 4.0)


def apply_column_number_formats(worksheet, sheet_specification):
    for column_letter, number_format in (sheet_specification.get("numberFormats") or {}).items():
        for cell in worksheet[column_letter.upper()]:
            cell.number_format = number_format


def parse_row(row_string):
    return [typed_cell_value(cell.strip()) for cell in row_string.split(",")]


def build_specification(arguments):
    sheet_name = arguments.sheet or arguments.title or "Sheet1"
    rows = [parse_row(row_string) for row_string in arguments.row]
    sheet_specification = {"title": sheet_name, "rows": rows}
    return {"title": arguments.title or "", "sheets": [sheet_specification]}


def parse_arguments():
    parser = OfficeArgumentParser(description="Create an XLSX workbook from arguments or a JSON spec; office guide sheet describes the spec.")
    parser.add_argument("output_path", help="Path to the output .xlsx file")
    parser.add_argument("--title", metavar="TEXT", default="", help="Workbook title (also used as sheet name when --sheet is absent)")
    parser.add_argument("--sheet", metavar="NAME", default=None, help="Sheet name (default: title or Sheet1)")
    parser.add_argument("--row", action="append", default=[], metavar="CELLS", help="Add one row; comma-separated cell values (repeatable)")
    parser.add_argument("--spec", metavar="JSON_PATH", help="Full workbook spec JSON for rich workbooks (multiple sheets, formulas, formats)")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    specification = read_specification(arguments)
    workbook = create_workbook(specification)
    output_path = Path(os.path.expanduser(arguments.output_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    editing = SheetEditing(workbook, None)
    changes = apply_batch(SHEET_OPERATIONS, editing, specification.get("operations") or [])
    issues = save_atomically(lambda temporary_path: save_editing(editing, temporary_path), str(output_path))
    details = {"changes": changes} if changes else None
    return Result(summary=f"created {output_path}", output_path=str(output_path), issues=tuple(issues), details=details)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
