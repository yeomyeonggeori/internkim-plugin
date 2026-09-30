from __future__ import annotations

from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.chart.marker import DataPoint
from openpyxl.utils import get_column_letter

from office_operations import OPERATION_NOT_APPLICABLE
from office_result import OfficeFailure
from workbook_access import parse_cell, parse_range


CHART_CLASSES = {"bar": BarChart, "line": LineChart, "pie": PieChart}
DEFAULT_ANCHOR_GAP = 2
SERIES_PALETTE = ("2563EB", "F59E0B", "10B981", "EF4444", "8B5CF6", "14B8A6", "EC4899", "64748B")
LINE_WIDTH_EMU = 28575


def build_chart(worksheet, operation: dict, location: str):
    min_row, min_column, max_row, max_column = parse_range(operation["range"], f"{location}.range")
    if max_row <= min_row or max_column <= min_column:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}.range: a chart needs a header row, a category column and at least one row and one series column", f"{location}.range"))
    chart = CHART_CLASSES[operation["type"]]()
    data_last_column = min_column + 1 if operation["type"] == "pie" else max_column
    chart.add_data(Reference(worksheet, min_col=min_column + 1, max_col=data_last_column, min_row=min_row, max_row=max_row), titles_from_data=True)
    chart.set_categories(Reference(worksheet, min_col=min_column, min_row=min_row + 1, max_row=max_row))
    if operation.get("title"):
        chart.title = operation["title"]
    show_axes(chart)
    color_series(chart, operation["type"], max_row - min_row)
    return chart


def palette_color(index: int) -> str:
    return SERIES_PALETTE[index % len(SERIES_PALETTE)]


def color_series(chart, chart_type: str, category_count: int) -> None:
    for index, series in enumerate(chart.series):
        if chart_type == "pie":
            series.dPt = [point_with_color(point, palette_color(point)) for point in range(category_count)]
        elif chart_type == "line":
            series.graphicalProperties.line.solidFill = palette_color(index)
            series.graphicalProperties.line.width = LINE_WIDTH_EMU
            series.smooth = False
        else:
            series.graphicalProperties.solidFill = palette_color(index)
            series.graphicalProperties.line.solidFill = palette_color(index)


def point_with_color(index: int, color: str) -> DataPoint:
    point = DataPoint(idx=index)
    point.graphicalProperties.solidFill = color
    return point


def show_axes(chart) -> None:
    for axis_name in ("x_axis", "y_axis"):
        axis = getattr(chart, axis_name, None)
        if axis is not None:
            axis.delete = False


def chart_anchor(operation: dict, location: str) -> str:
    if operation.get("anchor"):
        row, column = parse_cell(operation["anchor"], f"{location}.anchor")
        return f"{get_column_letter(column)}{row}"
    min_row, _, _, max_column = parse_range(operation["range"], f"{location}.range")
    return f"{get_column_letter(max_column + DEFAULT_ANCHOR_GAP)}{min_row}"
