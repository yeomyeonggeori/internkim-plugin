from __future__ import annotations

from openpyxl.chart import AreaChart, BarChart, DoughnutChart, LineChart, PieChart, RadarChart, Reference, ScatterChart, Series
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.legend import Legend
from openpyxl.chart.marker import DataPoint, Marker
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.utils import get_column_letter

from office_operations import OPERATION_NOT_APPLICABLE, Change
from office_result import MISSING_FIELD, OfficeFailure
from workbook_access import parse_cell, parse_range, sheet_of


DEFAULT_ANCHOR_GAP = 2
SERIES_PALETTE = ("2563EB", "F59E0B", "10B981", "EF4444", "8B5CF6", "14B8A6", "EC4899", "64748B")
LINE_WIDTH_EMU = 28575
DEFAULT_WIDTH = 16
DEFAULT_HEIGHT = 8
DEFAULT_LEGEND = "bottom"
SECONDARY_AXIS_ID = 200
BAR_GAP_WIDTH = 80
DOUGHNUT_HOLE = 55
LEGEND_POSITIONS = {"bottom": "b", "right": "r", "top": "t"}
ROUND_CHARTS = ("pie", "doughnut")
GENERAL = "General"


def require_block(bounds: tuple[int, int, int, int], chart_type: str, location: str) -> None:
    min_row, min_column, max_row, max_column = bounds
    if max_row <= min_row or max_column <= min_column:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}.range: a chart needs a header row, a category column and at least one row and one series column", f"{location}.range"))
    if chart_type == "combo" and max_column - min_column < 2:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}.range: a combo chart needs two series columns or more, bars first and the line last", f"{location}.range"))


def build_chart(worksheet, operation: dict, location: str):
    bounds = parse_range(operation["range"], f"{location}.range")
    require_block(bounds, operation["type"], location)
    if operation["type"] == "scatter":
        chart = scatter_chart(worksheet, bounds)
    elif operation["type"] == "combo":
        chart = combo_chart(worksheet, bounds, operation)
    else:
        chart = category_chart(worksheet, bounds, operation)
    chart.width = operation.get("width", DEFAULT_WIDTH)
    chart.height = operation.get("height", DEFAULT_HEIGHT)
    apply_labels(chart, {"legend": DEFAULT_LEGEND, **operation})
    format_value_axes(chart, worksheet, bounds)
    show_axes(chart)
    return chart


def series_reference(worksheet, bounds, first_column: int, last_column: int) -> Reference:
    return Reference(worksheet, min_col=first_column, max_col=last_column, min_row=bounds[0], max_row=bounds[2])


def categories(worksheet, bounds) -> Reference:
    return Reference(worksheet, min_col=bounds[1], min_row=bounds[0] + 1, max_row=bounds[2])


def new_chart(chart_type: str, operation: dict):
    if chart_type == "bar":
        chart = BarChart()
        chart.type = "bar" if operation.get("horizontal") else "col"
        chart.gapWidth = BAR_GAP_WIDTH
    elif chart_type == "line":
        chart = LineChart()
    elif chart_type == "area":
        chart = AreaChart()
    elif chart_type == "radar":
        chart = RadarChart()
        chart.type = "marker"
    elif chart_type == "doughnut":
        chart = DoughnutChart()
        chart.holeSize = DOUGHNUT_HOLE
    else:
        chart = PieChart()
    if operation.get("stacked") and chart_type in ("bar", "line", "area"):
        chart.grouping = "stacked"
        if chart_type == "bar":
            chart.overlap = 100
    return chart


def category_chart(worksheet, bounds, operation: dict):
    chart_type = operation["type"]
    chart = new_chart(chart_type, operation)
    last_column = bounds[1] + 1 if chart_type in ROUND_CHARTS else bounds[3]
    chart.add_data(series_reference(worksheet, bounds, bounds[1] + 1, last_column), titles_from_data=True)
    chart.set_categories(categories(worksheet, bounds))
    color_series(chart, chart_type, bounds[2] - bounds[0])
    return chart


def combo_chart(worksheet, bounds, operation: dict):
    line_count = min(operation.get("lineSeries", 1), bounds[3] - bounds[1] - 1)
    first_line_column = bounds[3] - line_count + 1
    bars = new_chart("bar", operation)
    bars.add_data(series_reference(worksheet, bounds, bounds[1] + 1, first_line_column - 1), titles_from_data=True)
    bars.set_categories(categories(worksheet, bounds))
    color_series(bars, "bar", 0)
    line = LineChart()
    line.add_data(series_reference(worksheet, bounds, first_line_column, bounds[3]), titles_from_data=True)
    line.set_categories(categories(worksheet, bounds))
    for offset, series in enumerate(line.series):
        style_line(series, palette_color(len(bars.series) + offset))
    if operation.get("secondaryAxis", True):
        line.y_axis.axId = SECONDARY_AXIS_ID
        line.y_axis.crosses = "max"
        line.y_axis.majorGridlines = None
    bars += line
    return bars


def scatter_chart(worksheet, bounds):
    chart = ScatterChart()
    x_values = Reference(worksheet, min_col=bounds[1], min_row=bounds[0] + 1, max_row=bounds[2])
    for index, column in enumerate(range(bounds[1] + 1, bounds[3] + 1)):
        values = Reference(worksheet, min_col=column, min_row=bounds[0], max_row=bounds[2])
        series = Series(values, x_values, title_from_data=True)
        series.marker = Marker(symbol="circle", size=7)
        series.marker.graphicalProperties = solid(palette_color(index))
        series.graphicalProperties.line.noFill = True
        chart.series.append(series)
    return chart


def solid(color: str) -> GraphicalProperties:
    properties = GraphicalProperties(solidFill=color)
    properties.line.solidFill = color
    return properties


def palette_color(index: int) -> str:
    return SERIES_PALETTE[index % len(SERIES_PALETTE)]


def style_line(series, color: str) -> None:
    series.graphicalProperties.line.solidFill = color
    series.graphicalProperties.line.width = LINE_WIDTH_EMU
    series.smooth = False
    series.marker = Marker(symbol="circle", size=6)
    series.marker.graphicalProperties = solid(color)


def color_series(chart, chart_type: str, category_count: int) -> None:
    for index, series in enumerate(chart.series):
        if chart_type in ROUND_CHARTS:
            series.dPt = [point_with_color(point, palette_color(point)) for point in range(category_count)]
        elif chart_type in ("line", "radar"):
            style_line(series, palette_color(index))
        else:
            series.graphicalProperties.solidFill = palette_color(index)
            series.graphicalProperties.line.solidFill = palette_color(index)


def point_with_color(index: int, color: str) -> DataPoint:
    point = DataPoint(idx=index)
    point.graphicalProperties.solidFill = color
    return point


def format_value_axes(chart, worksheet, bounds) -> None:
    for sub_chart in chart._charts:
        y_axis = getattr(sub_chart, "y_axis", None)
        if y_axis is None:
            continue
        column = bounds[3] if sub_chart is not chart else bounds[1] + 1
        number_format = worksheet.cell(row=bounds[0] + 1, column=column).number_format
        if number_format != GENERAL:
            y_axis.number_format = number_format
            y_axis.numFmt.sourceLinked = False


def apply_labels(chart, operation: dict) -> None:
    if operation.get("title") is not None:
        chart.title = operation["title"] or None
    if operation.get("xTitle") is not None and hasattr(chart, "x_axis"):
        chart.x_axis.title = operation["xTitle"] or None
    if operation.get("yTitle") is not None and hasattr(chart, "y_axis"):
        chart.y_axis.title = operation["yTitle"] or None
    if operation.get("legend") == "none":
        chart.legend = None
    elif operation.get("legend") is not None:
        chart.legend = chart.legend or Legend()
        chart.legend.position = LEGEND_POSITIONS[operation["legend"]]
    if operation.get("dataLabels") is not None:
        chart.dataLabels = value_labels() if operation["dataLabels"] else None


def value_labels() -> DataLabelList:
    return DataLabelList(showVal=True, showLegendKey=False, showCatName=False, showSerName=False, showPercent=False, showBubbleSize=False)


def show_axes(chart) -> None:
    for sub_chart in chart._charts:
        for axis_name in ("x_axis", "y_axis"):
            axis = getattr(sub_chart, axis_name, None)
            if axis is not None:
                axis.delete = False


def chart_anchor(operation: dict, location: str) -> str:
    if operation.get("anchor"):
        row, column = parse_cell(operation["anchor"], f"{location}.anchor")
        return f"{get_column_letter(column)}{row}"
    min_row, _, _, max_column = parse_range(operation["range"], f"{location}.range")
    return f"{get_column_letter(max_column + DEFAULT_ANCHOR_GAP)}{min_row}"


def plan_add_chart(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    chart = build_chart(worksheet, operation, location)
    anchor = chart_anchor(operation, location)

    def change() -> str:
        worksheet.add_chart(chart, anchor)
        return f"added a {operation['type']} chart of {worksheet.title}!{operation['range'].upper()} at {anchor}"
    return change


def existing_chart(worksheet, operation: dict, location: str):
    charts = worksheet._charts
    if operation["chart"] >= len(charts):
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}.chart: {worksheet.title} has {len(charts)} charts, numbered from 0", f"{location}.chart"))
    return charts[operation["chart"]]


def anchor_cell(chart) -> str:
    if isinstance(chart.anchor, str):
        return chart.anchor
    marker = chart.anchor._from
    return f"{get_column_letter(marker.col + 1)}{marker.row + 1}"


def plan_edit_chart(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    chart = existing_chart(worksheet, operation, location)
    if operation.get("type") and not operation.get("range"):
        raise OfficeFailure(MISSING_FIELD.issue(f"{location}.range: changing the chart type needs the data range", f"{location}.range"))
    replacement = build_chart(worksheet, {"type": "bar", **operation}, location) if operation.get("range") else None

    def change() -> str:
        index = operation["chart"]
        anchor = chart_anchor(operation, location) if operation.get("anchor") else anchor_cell(chart)
        if replacement is not None:
            if operation.get("title") is None and chart.title is not None:
                replacement.title = chart.title
            replacement.anchor = anchor
            worksheet._charts[index] = replacement
            return f"rebuilt chart {index} of {worksheet.title}"
        apply_labels(chart, operation)
        if operation.get("anchor") or "width" in operation or "height" in operation:
            chart.width = operation.get("width", chart.width)
            chart.height = operation.get("height", chart.height)
            chart.anchor = anchor
        return f"edited chart {index} of {worksheet.title}"
    return change


def plan_delete_chart(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    existing_chart(worksheet, operation, location)

    def change() -> str:
        del worksheet._charts[operation["chart"]]
        return f"deleted chart {operation['chart']} of {worksheet.title}"
    return change
