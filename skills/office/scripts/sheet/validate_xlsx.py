#!/usr/bin/env python3
from __future__ import annotations

from openpyxl import load_workbook

from office_result import Issue, OfficeArgumentParser, Result, run_command
from sheet_definitions import AUTO_FILTER_MISSING, BLANK_HEADER_CELLS, HEADER_NOT_FROZEN


FORMULA_CELL_LIMIT = 50


def main() -> Result:
    arguments = parse_arguments()
    workbook = load_workbook(arguments.workbook_path, data_only=False)
    sheet_summaries = [summarize_sheet(worksheet) for worksheet in workbook.worksheets]
    issues = [issue for summary in sheet_summaries for issue in sheet_issues(summary)]
    formula_cells = [
        f"{worksheet.title}!{cell.coordinate}"
        for worksheet in workbook.worksheets
        for row in worksheet.iter_rows()
        for cell in row
        if is_formula(cell.value)
    ]
    details = {
        "sheetCount": len(workbook.worksheets),
        "sheets": sheet_summaries,
        "formulaCells": formula_cells[:FORMULA_CELL_LIMIT],
        "formulaCellCount": len(formula_cells),
    }
    return Result(summary=f"checked {arguments.workbook_path}: {len(issues)} issues", output_path=arguments.workbook_path, issues=tuple(issues), details=details)


def summarize_sheet(worksheet) -> dict:
    header_row = header_row_index(worksheet)
    header_values = [cell.value for cell in worksheet[header_row]] if worksheet.max_row >= header_row else []
    return {
        "title": worksheet.title,
        "rows": worksheet.max_row,
        "columns": worksheet.max_column,
        "freezePanes": str(worksheet.freeze_panes) if worksheet.freeze_panes else None,
        "autoFilter": bool(worksheet.auto_filter.ref),
        "blankHeaderCount": sum(1 for value in header_values if value is None or str(value).strip() == ""),
    }


def header_row_index(worksheet) -> int:
    if worksheet.max_row < 2:
        return 1
    first_row_values = [cell.value for cell in worksheet[1]]
    second_row_values = [cell.value for cell in worksheet[2]]
    if non_blank_count(first_row_values) == 1 and non_blank_count(second_row_values) > 1:
        return 2
    return 1


def non_blank_count(values: list) -> int:
    return sum(1 for value in values if value is not None and str(value).strip())


def is_formula(value: object) -> bool:
    return isinstance(value, str) and value.startswith("=")


def sheet_issues(summary: dict) -> list[Issue]:
    title = summary["title"]
    issues = []
    if not summary["freezePanes"]:
        issues.append(HEADER_NOT_FROZEN.issue(f"{title}: header row is not frozen", title))
    if not summary["autoFilter"]:
        issues.append(AUTO_FILTER_MISSING.issue(f"{title}: auto filter is missing", title))
    if summary["blankHeaderCount"] > 0:
        issues.append(BLANK_HEADER_CELLS.issue(f"{title}: {summary['blankHeaderCount']} blank header cells", title))
    return issues


def parse_arguments():
    parser = OfficeArgumentParser(description="Validate and summarize an XLSX workbook.")
    parser.add_argument("workbook_path")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
