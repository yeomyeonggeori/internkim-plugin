from __future__ import annotations

from openpyxl.utils.cell import range_boundaries

from office_result import Issue
from sheet_charts import anchor_cell
from text_values import holds_number
from sheet_definitions import CHART_REFERENCE_BROKEN


def chart_type(chart) -> str:
    return "+".join(part.tagname.removesuffix("Chart").removesuffix("3D") for part in chart._charts)


def chart_title(chart) -> str | None:
    if chart.title is None or chart.title.tx is None or chart.title.tx.rich is None:
        return None
    return "".join(run.t or "" for paragraph in chart.title.tx.rich.p for run in (paragraph.r or [])) or None


def data_source_formula(source) -> str | None:
    if source is None:
        return None
    reference = source.numRef or source.strRef
    return reference.f if reference is not None else None


def series_formulas(chart) -> list[str]:
    return [formula for formula, _ in series_sources(chart)]


def series_sources(chart) -> list[tuple[str, bool]]:
    sources = []
    for part in chart._charts:
        for series in part.series:
            for source, holds_values in ((series.val, True), (series.cat, False), (series.xVal, False), (series.yVal, True)):
                formula = data_source_formula(source)
                if formula:
                    sources.append((formula, holds_values))
    return sources


def describe_charts(worksheet) -> list[dict]:
    return [
        {"chart": index, "type": chart_type(chart), "title": chart_title(chart), "anchor": anchor_cell(chart), "data": series_formulas(chart)}
        for index, chart in enumerate(worksheet._charts)
    ]


def split_formula(formula: str) -> tuple[str, str]:
    sheet, _, cells = formula.rpartition("!")
    if sheet.startswith("'") and sheet.endswith("'"):
        sheet = sheet[1:-1].replace("''", "'")
    return sheet, cells.replace("$", "")


def range_cells(worksheet, cells: str) -> list:
    min_column, min_row, max_column, max_row = range_boundaries(cells)
    return [cell for row in worksheet.iter_rows(min_row=min_row, max_row=max_row, min_col=min_column, max_col=max_column) for cell in row]


def reference_problem(workbook, formula: str, holds_values: bool) -> str | None:
    sheet, cells = split_formula(formula)
    if sheet and sheet not in workbook.sheetnames:
        return f"reads sheet {sheet!r}, which the workbook does not have"
    try:
        range_boundaries(cells)
    except ValueError:
        return f"reads {formula}, which is not a cell range"
    if not sheet:
        return None
    found = range_cells(workbook[sheet], cells)
    if not any(cell.value not in (None, "") for cell in found):
        return f"reads {formula}, which holds no values"
    if holds_values and not any(holds_number(cell) for cell in found):
        return f"reads {formula}, which holds text and no number, so its series draws nothing"
    return None


def chart_reference_issues(workbook) -> list[Issue]:
    issues = []
    for worksheet in workbook.worksheets:
        for index, chart in enumerate(worksheet._charts):
            location = f"{worksheet.title} chart {index}"
            problems = dict.fromkeys(problem for problem in (reference_problem(workbook, formula, holds_values) for formula, holds_values in series_sources(chart)) if problem)
            issues.extend(CHART_REFERENCE_BROKEN.issue(f"{location} {problem}", location) for problem in problems)
    return issues
