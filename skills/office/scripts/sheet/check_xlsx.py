#!/usr/bin/env python3
from __future__ import annotations

import math
from collections import defaultdict

from formula_cache import not_evaluated_issues
from formula_references import formula_references, referenced_sheet_names
from number_display import displayed_number_width
from office_inputs import office_file
from office_result import Issue, OfficeArgumentParser, Result, run_command
from sheet_chart_references import chart_reference_issues
from stale_values import stale_cached_value_issues
from sheet_definitions import BROKEN_DEFINED_NAME, FORMULA_ERROR, MISSING_SHEET_REFERENCE, NUMBER_TOO_WIDE
from text_checks import PLACEHOLDER_LEFT, PLACEHOLDER_PATTERN
from workbook_access import formula_text, open_workbook
from workbook_values import evaluate_workbook


DEFAULT_COLUMN_WIDTH = 8.43
LISTED_CELL_LIMIT = 20
WIDTH_MARGIN = 2


def main() -> Result:
    arguments = parse_arguments()
    workbook = open_workbook(arguments.workbook_path)
    evaluation = evaluate_workbook(arguments.workbook_path)
    missing_references = missing_sheet_references(workbook)
    issues = (
        stale_cached_value_issues(arguments.workbook_path, evaluation)
        + missing_reference_issues(missing_references)
        + formula_error_issues(evaluation, set(missing_references))
        + defined_name_issues(workbook)
        + number_width_issues(workbook, evaluation)
        + chart_reference_issues(workbook)
        + placeholder_issues(workbook)
        + not_evaluated_issues(evaluation)
    )
    return Result(summary=f"checked {arguments.workbook_path}: {len(issues)} issues", output_path=arguments.workbook_path, issues=tuple(issues))


def cell_label(sheet: str, coordinate: str) -> str:
    return f"{sheet}!{coordinate}"


def listed(labels: list[str]) -> str:
    hidden = len(labels) - LISTED_CELL_LIMIT
    return ", ".join(labels[:LISTED_CELL_LIMIT]) + (f" and {hidden} more" if hidden > 0 else "")


def sheet_is_missing(workbook, name: str) -> bool:
    return name.casefold() not in {title.casefold() for title in workbook.sheetnames}


def missing_sheet_references(workbook) -> dict:
    missing = {}
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                formula = formula_text(cell)
                names = [name for reference in formula_references(formula or "") for name in referenced_sheet_names(reference) if sheet_is_missing(workbook, name)]
                if names:
                    missing[(worksheet.title, cell.coordinate)] = names[0]
    return missing


def missing_reference_issues(missing: dict) -> list[Issue]:
    return [
        MISSING_SHEET_REFERENCE.issue(f"{cell_label(sheet, coordinate)} reads sheet {name!r}, which the workbook does not have", cell_label(sheet, coordinate))
        for (sheet, coordinate), name in sorted(missing.items())
    ]


def formula_error_issues(evaluation, already_reported: set) -> list[Issue]:
    by_error = defaultdict(list)
    for (sheet, coordinate), value in evaluation.values.items():
        if value.is_error and (sheet, coordinate) not in already_reported:
            by_error[(sheet, value.text)].append(cell_label(sheet, coordinate))
    return [
        FORMULA_ERROR.issue(f"{len(labels)} formula cells on {sheet} compute {code}: {listed(sorted(labels))}", sorted(labels)[0])
        for (sheet, code), labels in sorted(by_error.items())
    ]


def defined_name_issues(workbook) -> list[Issue]:
    scoped = [(name, defined, "") for name, defined in workbook.defined_names.items()]
    for worksheet in workbook.worksheets:
        scoped.extend((name, defined, worksheet.title) for name, defined in worksheet.defined_names.items())
    return [
        BROKEN_DEFINED_NAME.issue(f"defined name {name} points at {defined.attr_text}", name)
        for name, defined, _ in scoped
        if defined_name_is_broken(workbook, defined.attr_text or "")
    ]


def defined_name_is_broken(workbook, reference_text: str) -> bool:
    references = formula_references("=" + reference_text)
    if "#REF!" in reference_text:
        return True
    return any(sheet_is_missing(workbook, name) for reference in references for name in referenced_sheet_names(reference))


def column_width(worksheet, column: int) -> float:
    for dimension in worksheet.column_dimensions.values():
        if (dimension.min or 1) <= column <= (dimension.max or dimension.min or 1) and dimension.width:
            return dimension.width
    return worksheet.sheet_format.defaultColWidth or DEFAULT_COLUMN_WIDTH


def is_hidden_column(worksheet, column: int) -> bool:
    return any(dimension.hidden and (dimension.min or 1) <= column <= (dimension.max or dimension.min or 1) for dimension in worksheet.column_dimensions.values())


def number_width_issues(workbook, evaluation) -> list[Issue]:
    issues = []
    for worksheet in workbook.worksheets:
        widest = widest_number_per_column(worksheet, evaluation)
        for column, (needed, coordinate) in sorted(widest.items()):
            issues.append(too_wide_issue(worksheet, column, needed, coordinate))
    return issues


def widest_number_per_column(worksheet, evaluation) -> dict:
    merged = {coordinate for merged_range in worksheet.merged_cells.ranges for row in worksheet[merged_range.coord] for coordinate in (cell.coordinate for cell in row)}
    widest = {}
    for row in worksheet.iter_rows():
        for cell in row:
            number = number_shown_in(cell, worksheet.title, evaluation)
            if number is None or cell.coordinate in merged or is_hidden_column(worksheet, cell.column):
                continue
            needed = displayed_number_width(number, cell.number_format)
            if needed > column_width(worksheet, cell.column) and needed > widest.get(cell.column, (0, ""))[0]:
                widest[cell.column] = (needed, cell.coordinate)
    return widest


def number_shown_in(cell, sheet: str, evaluation) -> float | None:
    if cell.data_type == "f":
        value = evaluation.values.get((sheet, cell.coordinate))
        return float(value.text) if value is not None and value.cell_type == "n" else None
    if isinstance(cell.value, bool) or not isinstance(cell.value, (int, float)):
        return None
    return cell.value


def too_wide_issue(worksheet, column: int, needed: int, coordinate: str) -> Issue:
    letter = coordinate.rstrip("0123456789")
    width = math.ceil(needed) + WIDTH_MARGIN
    location = cell_label(worksheet.title, coordinate)
    suggestion = {"op": "set_column_width", "sheet": worksheet.title, "column": letter, "width": width}
    return NUMBER_TOO_WIDE.issue(f"{location} needs about {needed} characters but column {letter} holds {column_width(worksheet, column):g}", location, suggestion)


def placeholder_issues(workbook) -> list[Issue]:
    issues = []
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.data_type == "s" and isinstance(cell.value, str):
                    issues.extend(PLACEHOLDER_LEFT.issue(f"{cell_label(worksheet.title, cell.coordinate)} still holds {placeholder}", cell_label(worksheet.title, cell.coordinate)) for placeholder in PLACEHOLDER_PATTERN.findall(cell.value))
    return issues


def parse_arguments():
    parser = OfficeArgumentParser(description="Find stored formula values that differ from the computed ones, computed formula errors, missing sheets, broken names, numbers too wide for their column, charts reading missing or empty ranges and template placeholders in an .xlsx.")
    parser.add_argument("workbook_path", type=office_file("xlsx"))
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
