#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
from pathlib import Path

from skill_runtime import ensure_requirements


def require_text(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def optional_text(value, field_name):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value.strip()


def load_specification(specification_path):
    with open(specification_path, "r", encoding="utf-8") as specification_file:
        specification = json.load(specification_file)
    if not isinstance(specification, dict):
        raise ValueError("workbook specification must be an object")
    return specification


def create_workbook(specification):
    if not ensure_requirements("xlsx"):
        raise RuntimeError("xlsx dependencies are unavailable after bootstrap")

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)
    workbook_title = optional_text(specification.get("title"), "title")
    if workbook_title:
        workbook.properties.title = workbook_title

    sheets = specification.get("sheets", [])
    if not isinstance(sheets, list) or not sheets:
        raise ValueError("sheets must be a non-empty array")
    sheets = include_visible_workbook_title(sheets, workbook_title)

    for sheet_specification in sheets:
        worksheet = add_sheet(workbook, sheet_specification, get_column_letter)
        apply_default_formatting(worksheet, sheet_specification, Alignment, Border, Font, PatternFill, Side, get_column_letter)

    return workbook


def add_sheet(workbook, sheet_specification, get_column_letter):
    if not isinstance(sheet_specification, dict):
        raise ValueError("each sheet must be an object")
    title = require_text(sheet_specification.get("title"), "sheet.title")
    worksheet = workbook.create_sheet(title=title[:31])
    rows = read_rows(sheet_specification)
    heading = optional_text(sheet_specification.get("heading"), "sheet.heading")
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
    if sheet_specification.get("repairRowFormulas", True):
        repair_row_formulas(worksheet, header_row)
    return worksheet


def include_visible_workbook_title(sheets, workbook_title):
    if not workbook_title or sheets_contain_text(sheets, workbook_title):
        return sheets
    copied_sheets = [dict(sheet) if isinstance(sheet, dict) else sheet for sheet in sheets]
    first_sheet = copied_sheets[0]
    if not isinstance(first_sheet, dict):
        return sheets
    heading = optional_text(first_sheet.get("heading"), "sheet.heading")
    first_sheet["heading"] = f"{workbook_title} - {heading}" if heading else workbook_title
    return copied_sheets


def sheets_contain_text(sheets, text):
    for sheet in sheets:
        if not isinstance(sheet, dict):
            continue
        if text in optional_text(sheet.get("heading"), "sheet.heading"):
            return True
        for row in sheet.get("rows", []):
            if isinstance(row, list) and any(text in str(value) for value in row if value is not None):
                return True
    return False


def header_row_index(sheet_specification):
    return 2 if optional_text(sheet_specification.get("heading"), "sheet.heading") else 1


def auto_filter_reference(worksheet, header_row, get_column_letter):
    if worksheet.max_row < header_row:
        return worksheet.dimensions
    return f"A{header_row}:{get_column_letter(worksheet.max_column)}{worksheet.max_row}"


def repair_row_formulas(worksheet, header_row):
    for row in worksheet.iter_rows(min_row=header_row + 1):
        for cell in row:
            if not isinstance(cell.value, str) or not cell.value.startswith("="):
                continue
            if should_skip_row_formula_repair(cell.value):
                continue
            cell.value = rewrite_formula_to_cell_row(cell.value, cell.row)


def should_skip_row_formula_repair(formula):
    upper_formula = formula.upper()
    if "!" in upper_formula:
        return True
    return any(function_name in upper_formula for function_name in ["SUM(", "AVERAGE(", "COUNT(", "MIN(", "MAX("])


def rewrite_formula_to_cell_row(formula, row_number):
    def replace_reference(match):
        return f"{match.group(1)}{row_number}"

    return re.sub(r"(?<![A-Z])(\$?[A-Z]{1,3})\$?[0-9]+", replace_reference, formula)


def read_rows(sheet_specification):
    if "csvPath" in sheet_specification:
        return read_delimited_rows(sheet_specification)
    rows = sheet_specification.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("sheet rows must be an array")
    for row in rows:
        if not isinstance(row, list):
            raise ValueError("each row must be an array")
    return rows


def read_delimited_rows(sheet_specification):
    csv_path = require_text(sheet_specification.get("csvPath"), "csvPath")
    delimiter = sheet_specification.get("delimiter", ",")
    if delimiter == "\\t":
        delimiter = "\t"
    with open(csv_path, newline="", encoding="utf-8-sig") as delimited_file:
        return list(csv.reader(delimited_file, delimiter=delimiter))


def apply_default_formatting(worksheet, sheet_specification, alignment_class, border_class, font_class, fill_class, side_class, get_column_letter):
    if worksheet.max_row == 0:
        return
    thin_border = create_thin_border(border_class, side_class)
    header_fill = fill_class("solid", fgColor="DCEAF7")
    heading = optional_text(sheet_specification.get("heading"), "sheet.heading")
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
        content_width = max(len(str(cell.value or "")) for cell in column_cells)
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
    column_widths = sheet_specification.get("columnWidths", {})
    if not isinstance(column_widths, dict):
        return
    for column_letter, width in column_widths.items():
        if isinstance(column_letter, str) and isinstance(width, (int, float)):
            worksheet.column_dimensions[column_letter.upper()].width = max(float(width), 4.0)


def apply_column_number_formats(worksheet, sheet_specification):
    number_formats = sheet_specification.get("numberFormats", {})
    if not isinstance(number_formats, dict):
        return
    for column_letter, number_format in number_formats.items():
        if not isinstance(column_letter, str) or not isinstance(number_format, str):
            continue
        for cell in worksheet[column_letter.upper()]:
            cell.number_format = number_format


def parse_row(row_string):
    return [cell.strip() for cell in row_string.split(",")]


def build_specification(arguments):
    sheet_name = arguments.sheet or arguments.title or "Sheet1"
    rows = [parse_row(row_string) for row_string in arguments.row]
    sheet_specification = {"title": sheet_name, "rows": rows}
    return {"title": arguments.title or "", "sheets": [sheet_specification]}


def parse_arguments():
    parser = argparse.ArgumentParser(description="Create an XLSX workbook from arguments or a JSON spec.")
    parser.add_argument("output_path", help="Path to the output .xlsx file")
    parser.add_argument("--title", metavar="TEXT", default="", help="Workbook title (also used as sheet name when --sheet is absent)")
    parser.add_argument("--sheet", metavar="NAME", default=None, help="Sheet name (default: title or Sheet1)")
    parser.add_argument("--row", action="append", default=[], metavar="CELLS", help="Add one row; comma-separated cell values (repeatable)")
    parser.add_argument("--spec", metavar="JSON_PATH", help="Full workbook spec JSON for rich workbooks (multiple sheets, formulas, formats, charts)")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    has_inline_content = arguments.title or arguments.row
    if not arguments.spec and not has_inline_content:
        raise ValueError("provide at least --title or --row, or pass --spec <file>")
    specification = load_specification(arguments.spec) if arguments.spec else build_specification(arguments)
    workbook = create_workbook(specification)
    output_path = Path(os.path.expanduser(arguments.output_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    print(output_path)


if __name__ == "__main__":
    main()
