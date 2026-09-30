#!/usr/bin/env python3
from __future__ import annotations

from openpyxl.utils import get_column_letter

from office_result import OfficeArgumentParser, Result, run_command
from sheet_definitions import READ_ROW_LIMIT
from workbook_access import cell_rows, formula_text, json_value, open_workbook, parse_range, resolve_sheet


def main() -> Result:
    arguments = parse_arguments()
    formulas_workbook = open_workbook(arguments.workbook_path)
    values_workbook = open_workbook(arguments.workbook_path, data_only=True)
    worksheet = resolve_sheet(formulas_workbook, arguments.sheet, "--sheet")
    bounds = requested_bounds(worksheet, arguments.range)
    shown_bounds, truncated = limited_bounds(bounds, arguments.limit)
    details = {
        "sheets": [describe_sheet(sheet) for sheet in formulas_workbook.worksheets],
        "definedNames": describe_defined_names(formulas_workbook),
        "range": describe_range(worksheet, values_workbook[worksheet.title], shown_bounds, truncated, arguments.where),
    }
    return Result(summary=f"read {details['range']['range']} of {worksheet.title} from {arguments.workbook_path}", output_path=arguments.workbook_path, details=details)


def requested_bounds(worksheet, range_text: str | None) -> tuple[int, int, int, int]:
    if range_text:
        return parse_range(range_text, "--range")
    return 1, 1, max(worksheet.max_row, 1), max(worksheet.max_column, 1)


def limited_bounds(bounds: tuple[int, int, int, int], limit: int) -> tuple[tuple[int, int, int, int], bool]:
    min_row, min_column, max_row, max_column = bounds
    last_row = min(max_row, min_row + limit - 1)
    return (min_row, min_column, last_row, max_column), last_row < max_row


def describe_sheet(worksheet) -> dict:
    return {
        "name": worksheet.title,
        "visible": worksheet.sheet_state == "visible",
        "dimensions": worksheet.dimensions,
        "rows": worksheet.max_row,
        "columns": worksheet.max_column,
        "frozenPanes": worksheet.freeze_panes,
        "autoFilter": worksheet.auto_filter.ref or None,
        "tables": [{"name": table.name, "range": table.ref} for table in worksheet.tables.values()],
        "charts": len(worksheet._charts),
        "mergedCells": [str(merged) for merged in worksheet.merged_cells.ranges],
    }


def describe_defined_names(workbook) -> list[dict]:
    names = [{"name": name, "value": defined.attr_text, "scope": None} for name, defined in workbook.defined_names.items()]
    for worksheet in workbook.worksheets:
        names.extend({"name": name, "value": defined.attr_text, "scope": worksheet.title} for name, defined in worksheet.defined_names.items())
    return names


def describe_range(worksheet, values_worksheet, bounds: tuple[int, int, int, int], truncated: bool, where: str | None) -> dict:
    min_row, min_column, max_row, max_column = bounds
    description = {
        "sheet": worksheet.title,
        "range": f"{get_column_letter(min_column)}{min_row}:{get_column_letter(max_column)}{max_row}",
        "truncated": truncated,
    }
    if where == "formula":
        description["cells"] = formula_cells_in(worksheet, values_worksheet, bounds)
        return description
    description["values"] = [[json_value(cell.value) for cell in row] for row in cell_rows(values_worksheet, bounds)]
    description["formulas"] = [[formula_text(cell) for cell in row] for row in cell_rows(worksheet, bounds)]
    return description


def formula_cells_in(worksheet, values_worksheet, bounds: tuple[int, int, int, int]) -> list[dict]:
    return [
        {"cell": cell.coordinate, "formula": formula_text(cell), "value": json_value(values_worksheet[cell.coordinate].value)}
        for row in cell_rows(worksheet, bounds)
        for cell in row
        if cell.data_type == "f"
    ]


def parse_arguments():
    parser = OfficeArgumentParser(description="Read a workbook: every sheet's dimensions, frozen panes, filter, tables, charts, merged cells and the defined names, and one range's values and formulas side by side.")
    parser.add_argument("workbook_path")
    parser.add_argument("--sheet", metavar="NAME", help="sheet to read the range from, default the first sheet")
    parser.add_argument("--range", metavar="RANGE", help="range such as A1:F40, default the whole sheet")
    parser.add_argument("--where", choices=("formula",), help="formula lists only the cells that hold a formula, with their cached values")
    parser.add_argument("--limit", type=int, default=READ_ROW_LIMIT, help=f"most rows to show, default {READ_ROW_LIMIT}")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
