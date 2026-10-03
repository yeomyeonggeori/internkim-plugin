from __future__ import annotations

import copy
from dataclasses import dataclass
import math

from pptx.chart.data import CategoryChartData
from pptx.oxml import parse_xml as parse_chart_xml

from charts.kinds import office_chart_type


CHART_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/chart"
SECONDARY_AXIS_RATIO = 0.1
SECONDARY_AXIS_IDENTIFIERS = ("50010", "50020")
AXIS_INTERVALS = 4
ROUND_STEP_MULTIPLES = (1, 2, 5, 10)

ComboSeries = tuple[str, tuple[float, ...], bool]


def category_chart_data(categories: tuple[str, ...], series: list[ComboSeries], number_format: str = "General") -> CategoryChartData:
    data = CategoryChartData(number_format=number_format)
    data.categories = list(categories)
    for name, values, _ in series:
        data.add_series(name, list(values))
    return data


def lines_need_own_axis(series: list[ComboSeries]) -> bool:
    lines = [abs(value) for _, values, is_line in series if is_line for value in values]
    columns = [abs(value) for _, values, is_line in series if not is_line for value in values]
    if not lines or not columns or max(lines) == 0 or max(columns) == 0:
        return False
    ratio = max(lines) / max(columns)
    return ratio < SECONDARY_AXIS_RATIO or ratio > 1 / SECONDARY_AXIS_RATIO


@dataclass(frozen=True)
class AxisRange:
    minimum: float
    maximum: float
    step: float


def zero_aligned_ranges(groups: list[list[float]]) -> list[AxisRange]:
    steps = [round_step(max(0.0, *values) - min(0.0, *values)) for values in groups]
    below = max(steps_beyond(-min(0.0, *values), step) for values, step in zip(groups, steps))
    above = max(steps_beyond(max(0.0, *values), step) for values, step in zip(groups, steps)) or (0 if below else 1)
    return [AxisRange(tidy(-below * step), tidy(above * step), step) for step in steps]


def round_step(span: float) -> float:
    interval = span / AXIS_INTERVALS if span > 0 else 1.0
    magnitude = 10 ** math.floor(math.log10(interval))
    return next(multiple * magnitude for multiple in ROUND_STEP_MULTIPLES if interval / magnitude <= multiple)


def steps_beyond(extent: float, step: float) -> int:
    return math.floor(extent / step) + 1 if extent > 0 else 0


def tidy(value: float) -> float:
    return round(value, 10) + 0.0


def combo_chart_space(categories: tuple[str, ...], series: list[ComboSeries], secondary_axis: bool):
    root = parse_chart_xml(category_chart_data(categories, series).xml_bytes(office_chart_type("column")))
    bar_chart = root.find(f".//{{{CHART_NAMESPACE}}}barChart")
    line_source = parse_chart_xml(category_chart_data(categories, series).xml_bytes(office_chart_type("line")))
    line_chart = line_source.find(f".//{{{CHART_NAMESPACE}}}lineChart")
    for bar_series_element, line_series_element, (_, _, is_line) in zip(bar_chart.findall(f"{{{CHART_NAMESPACE}}}ser"), line_chart.findall(f"{{{CHART_NAMESPACE}}}ser"), series):
        (bar_chart if is_line else line_chart).remove(bar_series_element if is_line else line_series_element)
    for axis_identifier in line_chart.findall(f"{{{CHART_NAMESPACE}}}axId"):
        line_chart.remove(axis_identifier)
    for axis_identifier in bar_chart.findall(f"{{{CHART_NAMESPACE}}}axId"):
        line_chart.append(copy.deepcopy(axis_identifier))
    bar_chart.addnext(line_chart)
    if secondary_axis:
        add_secondary_axes(root, line_chart)
        align_axis_zeros(root, series)
    return root


def add_secondary_axes(root, line_chart) -> None:
    category_axis = root.find(f".//{{{CHART_NAMESPACE}}}catAx")
    value_axis = root.find(f".//{{{CHART_NAMESPACE}}}valAx")
    category_identifier, value_identifier = SECONDARY_AXIS_IDENTIFIERS
    for axis_identifier, new_identifier in zip(line_chart.findall(f"{{{CHART_NAMESPACE}}}axId"), SECONDARY_AXIS_IDENTIFIERS):
        axis_identifier.set("val", new_identifier)
    hidden_category = copy.deepcopy(category_axis)
    set_child(hidden_category, "axId", category_identifier)
    set_child(hidden_category, "delete", "1")
    set_child(hidden_category, "crossAx", value_identifier)
    right_values = copy.deepcopy(value_axis)
    set_child(right_values, "axId", value_identifier)
    set_child(right_values, "axPos", "r")
    set_child(right_values, "crossAx", category_identifier)
    set_child(right_values, "crosses", "max")
    gridlines = right_values.find(f"{{{CHART_NAMESPACE}}}majorGridlines")
    if gridlines is not None:
        right_values.remove(gridlines)
    value_axis.addnext(right_values)
    value_axis.addnext(hidden_category)


def align_axis_zeros(root, series: list[ComboSeries]) -> None:
    columns = [value for _, values, is_line in series if not is_line for value in values]
    lines = [value for _, values, is_line in series if is_line for value in values]
    for axis, limits in zip(root.findall(f".//{{{CHART_NAMESPACE}}}valAx"), zero_aligned_ranges([columns, lines])):
        set_limits(axis, limits)


def set_limits(axis, limits: AxisRange) -> None:
    scaling = axis.find(f"{{{CHART_NAMESPACE}}}scaling")
    for tag in ("max", "min", "majorUnit"):
        for existing in (scaling if tag != "majorUnit" else axis).findall(f"{{{CHART_NAMESPACE}}}{tag}"):
            existing.getparent().remove(existing)
    for tag, value in (("max", limits.maximum), ("min", limits.minimum)):
        scaling.append(chart_element(scaling, tag, value))
    last_crossing = next(child for tag in ("crossBetween", "crosses", "crossesAt", "crossAx") for child in axis.findall(f"{{{CHART_NAMESPACE}}}{tag}"))
    last_crossing.addnext(chart_element(axis, "majorUnit", limits.step))


def chart_element(parent, tag: str, value: float):
    return parent.makeelement(f"{{{CHART_NAMESPACE}}}{tag}", {"val": repr(value)})


def set_child(element, tag: str, value: str) -> None:
    element.find(f"{{{CHART_NAMESPACE}}}{tag}").set("val", value)
