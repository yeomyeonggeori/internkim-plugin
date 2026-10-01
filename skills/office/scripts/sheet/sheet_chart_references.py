from __future__ import annotations

from openpyxl.utils.cell import range_boundaries

from office_result import Issue
from sheet_charts import anchor_cell
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
    formulas = []
    for part in chart._charts:
        for series in part.series:
            sources = (series.val, series.cat, series.xVal, series.yVal)
            formulas.extend(formula for formula in map(data_source_formula, sources) if formula)
    return formulas


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


def holds_values(worksheet, cells: str) -> bool:
    min_column, min_row, max_column, max_row = range_boundaries(cells)
    rows = worksheet.iter_rows(min_row=min_row, max_row=max_row, min_col=min_column, max_col=max_column, values_only=True)
    return any(value not in (None, "") for row in rows for value in row)


def reference_problem(workbook, formula: str) -> str | None:
    sheet, cells = split_formula(formula)
    if sheet and sheet not in workbook.sheetnames:
        return f"reads sheet {sheet!r}, which the workbook does not have"
    try:
        range_boundaries(cells)
    except ValueError:
        return f"reads {formula}, which is not a cell range"
    if sheet and not holds_values(workbook[sheet], cells):
        return f"reads {formula}, which holds no values"
    return None


def chart_reference_issues(workbook) -> list[Issue]:
    issues = []
    for worksheet in workbook.worksheets:
        for index, chart in enumerate(worksheet._charts):
            location = f"{worksheet.title} chart {index}"
            problems = dict.fromkeys(problem for problem in (reference_problem(workbook, formula) for formula in series_formulas(chart)) if problem)
            issues.extend(CHART_REFERENCE_BROKEN.issue(f"{location} {problem}", location) for problem in problems)
    return issues
