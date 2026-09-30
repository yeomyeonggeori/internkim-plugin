from __future__ import annotations

import re

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.worksheet.filters import AutoFilter

from formula_cache import save_workbook_with_values
from formula_references import COLUMN_AXIS, ROW_AXIS, Shift
from office_operations import Change, OperationSet
from office_result import INVALID_VALUE, OfficeFailure
from sheet_charts import build_chart, chart_anchor
from sheet_definitions import OPERATIONS
from sheet_styling import data_bounds, style_written_cells
from workbook_access import cell_rows, open_workbook, parse_cell, parse_range, resolve_sheet
from workbook_structure import isolate_column, rename_sheet_references, shift_workbook


MAXIMUM_SHEET_NAME_LENGTH = 31
FORBIDDEN_SHEET_NAME_CHARACTERS = set("[]:*?/\\")
COLOR_PATTERN = re.compile(r"^[0-9A-Fa-f]{6}$")
MAXIMUM_COLUMN = 16384


def load_editing(path: str):
    return open_workbook(path)


def save_editing(workbook, path: str):
    return save_workbook_with_values(workbook, path)


def sheet_of(workbook, operation: dict, location: str):
    return resolve_sheet(workbook, operation.get("sheet"), f"{location}.sheet")


def column_index(text: str, location: str) -> int:
    letters = text.strip().upper()
    if not letters.isalpha() or not letters.isascii() or len(letters) > 3 or column_index_from_string(letters) > MAXIMUM_COLUMN:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: {text!r} is not a column letter such as C", location))
    return column_index_from_string(letters)


def validate_sheet_name(workbook, name: str, location: str, renaming: str | None = None) -> None:
    if len(name) > MAXIMUM_SHEET_NAME_LENGTH:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: sheet names hold at most {MAXIMUM_SHEET_NAME_LENGTH} characters, {name!r} has {len(name)}", location))
    if FORBIDDEN_SHEET_NAME_CHARACTERS & set(name) or name.startswith("'") or name.endswith("'"):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: a sheet name cannot hold any of [ ] : * ? / \\ or start or end with an apostrophe", location))
    taken = [title for title in workbook.sheetnames if title.casefold() == name.casefold() and title != renaming]
    if taken:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: the workbook already has a sheet named {taken[0]!r}", location))


def store_value(cell, value, value_type) -> None:
    cell.value = value
    if value_type == "text" and isinstance(value, str) and value.startswith("="):
        cell.data_type = "s"
        cell.quotePrefix = True


def plan_set_cell(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    row, column = parse_cell(operation["cell"], f"{location}.cell")

    def change() -> str:
        existing = data_bounds(worksheet)
        cell = worksheet.cell(row=row, column=column)
        store_value(cell, operation.get("value"), operation.get("type"))
        style_written_cells(worksheet, [cell], existing)
        return f"set {worksheet.title}!{operation['cell'].upper()}"
    return change


def plan_set_range(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    first_row, first_column = parse_cell(operation["cell"], f"{location}.cell")

    def change() -> str:
        existing = data_bounds(worksheet)
        written = []
        for row_offset, values in enumerate(operation["values"]):
            for column_offset, value in enumerate(values):
                cell = worksheet.cell(row=first_row + row_offset, column=first_column + column_offset)
                store_value(cell, value, operation.get("type"))
                written.append(cell)
        style_written_cells(worksheet, written, existing)
        rows = len(operation["values"])
        return f"wrote {rows} rows from {worksheet.title}!{operation['cell'].upper()}"
    return change


def require_color(operation: dict, name: str, location: str) -> None:
    if name in operation and not COLOR_PATTERN.match(operation[name]):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.{name}: {operation[name]!r} is not six hex digits such as DCEAF7", f"{location}.{name}"))


def plan_format_range(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    bounds = parse_range(operation["range"], f"{location}.range")
    require_color(operation, "fill", location)
    require_color(operation, "fontColor", location)

    def change() -> str:
        cells = [cell for row in cell_rows(worksheet, bounds) for cell in row]
        for cell in cells:
            apply_format(cell, operation)
        return f"formatted {len(cells)} cells in {worksheet.title}!{operation['range'].upper()}"
    return change


def apply_format(cell, operation: dict) -> None:
    if "numberFormat" in operation:
        cell.number_format = operation["numberFormat"]
    if "bold" in operation or "fontColor" in operation:
        cell.font = changed_font(cell.font, operation)
    if "fill" in operation:
        cell.fill = PatternFill("solid", fgColor=operation["fill"].upper())
    if "alignment" in operation or "wrapText" in operation:
        cell.alignment = changed_alignment(cell.alignment, operation)


def changed_font(font, operation: dict) -> Font:
    updated = Font(name=font.name, size=font.sz, bold=font.b, italic=font.i, underline=font.u, strike=font.strike, color=font.color, vertAlign=font.vertAlign, family=font.family, charset=font.charset, scheme=font.scheme)
    if "bold" in operation:
        updated.b = operation["bold"]
    if "fontColor" in operation:
        updated.color = operation["fontColor"].upper()
    return updated


def changed_alignment(alignment, operation: dict) -> Alignment:
    return Alignment(
        horizontal=operation.get("alignment", alignment.horizontal),
        vertical=alignment.vertical,
        wrap_text=operation.get("wrapText", alignment.wrap_text),
        shrink_to_fit=alignment.shrink_to_fit,
        indent=alignment.indent,
        text_rotation=alignment.text_rotation,
    )


def plan_set_column_width(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    index = column_index(operation["column"], f"{location}.column")

    def change() -> str:
        dimension = isolate_column(worksheet, index) if has_group_over(worksheet, index) else worksheet.column_dimensions[get_column_letter(index)]
        dimension.width = operation["width"]
        return f"set column {get_column_letter(index)} of {worksheet.title} to width {operation['width']}"
    return change


def has_group_over(worksheet, index: int) -> bool:
    return any((dimension.min or 1) <= index <= (dimension.max or dimension.min or 1) for dimension in worksheet.column_dimensions.values())


def plan_freeze_panes(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    cell = (operation.get("cell") or "").strip()
    if cell:
        parse_cell(cell, f"{location}.cell")

    def change() -> str:
        worksheet.freeze_panes = cell.replace("$", "").upper() or None
        return f"froze panes at {cell.upper()} on {worksheet.title}" if cell else f"unfroze panes on {worksheet.title}"
    return change


def plan_set_auto_filter(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    range_text = (operation.get("range") or "").strip()
    if range_text:
        parse_range(range_text, f"{location}.range")

    def change() -> str:
        worksheet.auto_filter = AutoFilter(ref=range_text.replace("$", "").upper() or None)
        return f"set the filter of {worksheet.title} to {range_text.upper()}" if range_text else f"removed the filter of {worksheet.title}"
    return change


def plan_add_sheet(workbook, operation: dict, location: str) -> Change:
    validate_sheet_name(workbook, operation["name"], f"{location}.name")

    def change() -> str:
        workbook.create_sheet(title=operation["name"], index=operation.get("index"))
        return f"added sheet {operation['name']}"
    return change


def plan_rename_sheet(workbook, operation: dict, location: str) -> Change:
    worksheet = resolve_sheet(workbook, operation["sheet"], f"{location}.sheet")
    validate_sheet_name(workbook, operation["name"], f"{location}.name", renaming=worksheet.title)

    def change() -> str:
        old_name = worksheet.title
        rewritten = rename_sheet_references(workbook, old_name, operation["name"])
        worksheet.title = operation["name"]
        return f"renamed sheet {old_name} to {operation['name']}; rewrote {rewritten} formulas"
    return change


def plan_structure(axis: str, sign: int, noun: str, verb: str):
    def plan(workbook, operation: dict, location: str) -> Change:
        worksheet = sheet_of(workbook, operation, location)
        at = operation["at"] if axis == ROW_AXIS else column_index(operation["at"], f"{location}.at")
        count = operation.get("count", 1)
        shift = Shift(worksheet.title, axis, at, sign * count)

        def change() -> str:
            rewritten = shift_workbook(workbook, worksheet, shift)
            return f"{verb} {count} {noun} {'before' if sign > 0 else 'from'} {axis} {operation['at']} of {worksheet.title}; rewrote {rewritten} formulas"
        return change
    return plan


def plan_recalculate(workbook, operation: dict, location: str) -> Change:
    def change() -> str:
        return "stored freshly computed values for every formula the workbook can compute"
    return change


def plan_add_chart(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    chart = build_chart(worksheet, operation, location)
    anchor = chart_anchor(operation, location)

    def change() -> str:
        worksheet.add_chart(chart, anchor)
        return f"added a {operation['type']} chart of {worksheet.title}!{operation['range'].upper()} at {anchor}"
    return change


SHEET_OPERATIONS = OperationSet(OPERATIONS, {
    "set_cell": plan_set_cell,
    "set_range": plan_set_range,
    "format_range": plan_format_range,
    "set_column_width": plan_set_column_width,
    "freeze_panes": plan_freeze_panes,
    "set_auto_filter": plan_set_auto_filter,
    "add_sheet": plan_add_sheet,
    "rename_sheet": plan_rename_sheet,
    "insert_rows": plan_structure(ROW_AXIS, 1, "rows", "inserted"),
    "delete_rows": plan_structure(ROW_AXIS, -1, "rows", "deleted"),
    "insert_columns": plan_structure(COLUMN_AXIS, 1, "columns", "inserted"),
    "delete_columns": plan_structure(COLUMN_AXIS, -1, "columns", "deleted"),
    "recalculate": plan_recalculate,
    "add_chart": plan_add_chart,
}, sequential=True)
