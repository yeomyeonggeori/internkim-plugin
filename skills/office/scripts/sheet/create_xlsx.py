#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
from pathlib import Path

from cell_values import typed_cell_value
from display_width import display_width
from formula_cache import cache_formula_values
from office_result import INVALID_ARGUMENTS, OfficeArgumentParser, OfficeFailure, Result, read_json_file, run_command
from office_schema import require_valid
from sheet_definitions import WORKBOOK_SPECIFICATION


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
    return specification


def create_workbook(specification):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)
    workbook_title = optional_text(specification.get("title"))
    if workbook_title:
        workbook.properties.title = workbook_title

    for sheet_specification in specification["sheets"]:
        worksheet = add_sheet(workbook, sheet_specification, get_column_letter)
        apply_default_formatting(worksheet, sheet_specification, Alignment, Border, Font, PatternFill, Side, get_column_letter)

    return workbook


def add_sheet(workbook, sheet_specification, get_column_letter):
    title = sheet_specification["title"].strip()
    worksheet = workbook.create_sheet(title=title[:31])
    rows = read_rows(sheet_specification)
    heading = optional_text(sheet_specification.get("heading"))
    if heading:
        worksheet.append([heading])
    for row in rows:
        worksheet.append(["" if value is None else value for value in row])
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
    with open(csv_path, newline="", encoding="utf-8-sig") as delimited_file:
        return [[typed_cell_value(text) for text in row] for row in csv.reader(delimited_file, delimiter=delimiter)]


def apply_default_formatting(worksheet, sheet_specification, alignment_class, border_class, font_class, fill_class, side_class, get_column_letter):
    if worksheet.max_row == 0:
        return
    thin_border = create_thin_border(border_class, side_class)
    header_fill = fill_class("solid", fgColor="DCEAF7")
    heading = optional_text(sheet_specification.get("heading"))
    header_row = header_row_index(sheet_specification)
    if heading:
        for cell in worksheet[1]:
            cell.font = font_class(bold=True, size=14)
            cell.fill = fill_class("solid", fgColor="EAF3F8")
    for cell in worksheet[header_row]:
        cell.font = font_class(bold=True)
        cell.fill = header_fill
    for row in worksheet.iter_rows():
        for cell in row:
            cell.alignment = alignment_class(vertical="top", wrap_text=True)
            cell.border = thin_border
            apply_number_format(cell)
    for column_cells in worksheet.columns:
        content_width = max(display_width(cell.value) for cell in column_cells)
        column_letter = get_column_letter(column_cells[0].column)
        worksheet.column_dimensions[column_letter].width = min(max(content_width + 2, 10), 48)
    apply_column_widths(worksheet, sheet_specification)
    apply_column_number_formats(worksheet, sheet_specification)


def create_thin_border(border_class, side_class):
    side = side_class(style="thin", color="CBD5E1")
    return border_class(left=side, right=side, top=side, bottom=side)


def apply_number_format(cell):
    if isinstance(cell.value, bool):
        return
    if isinstance(cell.value, int):
        cell.number_format = "#,##0"
    if isinstance(cell.value, float):
        cell.number_format = "#,##0.00"


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
    workbook.save(output_path)
    issues = cache_formula_values(str(output_path))
    return Result(summary=f"created {output_path}", output_path=str(output_path), issues=tuple(issues))


if __name__ == "__main__":
    raise SystemExit(run_command(main))
