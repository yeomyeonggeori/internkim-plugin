from __future__ import annotations

from dataclasses import dataclass

from pptx.oxml.ns import qn

from powerpoint.definitions import CHART_POINT_OUTSIDE_AXIS, CHART_ZERO_MISALIGNED
from core.office_result import Issue


ZERO_HEIGHT_TOLERANCE = 0.02
VALUE_TOLERANCE = 1e-9
STACKED_GROUPINGS = {"stacked"}
UNCHECKED_GROUPINGS = {"percentStacked"}
CATEGORY_PLOTS = ("barChart", "bar3DChart", "lineChart", "line3DChart", "areaChart", "area3DChart")


@dataclass(frozen=True)
class ValueAxis:
    identifier: str
    minimum: float | None
    maximum: float | None
    is_logarithmic: bool

    @property
    def is_bounded(self) -> bool:
        return self.minimum is not None and self.maximum is not None and self.maximum > self.minimum

    def zero_height(self) -> float:
        return min(1.0, max(0.0, -self.minimum / (self.maximum - self.minimum)))

    def holds(self, value: float) -> bool:
        above = self.minimum is None or value >= self.minimum - VALUE_TOLERANCE * max(1.0, abs(self.minimum))
        below = self.maximum is None or value <= self.maximum + VALUE_TOLERANCE * max(1.0, abs(self.maximum))
        return above and below


@dataclass(frozen=True)
class PlottedSeries:
    name: str
    values: tuple[float, ...]
    axis: ValueAxis


def limit(scaling, tag: str) -> float | None:
    element = scaling.find(qn(f"c:{tag}"))
    return float(element.get("val")) if element is not None else None


def value_axes(plot_area) -> dict[str, ValueAxis]:
    axes = {}
    for axis in plot_area.findall(qn("c:valAx")):
        scaling = axis.find(qn("c:scaling"))
        identifier = axis.find(qn("c:axId")).get("val")
        axes[identifier] = ValueAxis(identifier, limit(scaling, "min"), limit(scaling, "max"), scaling.find(qn("c:logBase")) is not None)
    return axes


def cached_numbers(reference) -> tuple[float, ...]:
    if reference is None:
        return ()
    points = sorted(reference.iter(qn("c:pt")), key=lambda point: int(point.get("idx")))
    return tuple(float(point.find(qn("c:v")).text) for point in points if point.find(qn("c:v")) is not None)


def series_name(series) -> str:
    title = series.find(qn("c:tx"))
    names = [value.text for value in title.iter(qn("c:v"))] if title is not None else []
    return names[0] if names else f"series {series.find(qn('c:idx')).get('val')}"


def stacked_totals(series_values: list[tuple[float, ...]]) -> tuple[float, ...]:
    count = max((len(values) for values in series_values), default=0)
    highs = [sum(max(0.0, values[index]) for values in series_values if index < len(values)) for index in range(count)]
    lows = [sum(min(0.0, values[index]) for values in series_values if index < len(values)) for index in range(count)]
    return tuple(highs + lows)


def plotted_series(plot_area) -> list[PlottedSeries]:
    axes = value_axes(plot_area)
    plotted = []
    for tag in CATEGORY_PLOTS:
        for plot in plot_area.findall(qn(f"c:{tag}")):
            axis = next((axes[identifier.get("val")] for identifier in plot.findall(qn("c:axId")) if identifier.get("val") in axes), None)
            grouping = plot.find(qn("c:grouping"))
            grouping_name = grouping.get("val") if grouping is not None else "standard"
            if axis is None or grouping_name in UNCHECKED_GROUPINGS:
                continue
            series = plot.findall(qn("c:ser"))
            values = [cached_numbers(entry.find(qn("c:val"))) for entry in series]
            if grouping_name in STACKED_GROUPINGS:
                plotted.append(PlottedSeries("the stacked total", stacked_totals(values), axis))
            else:
                plotted.extend(PlottedSeries(series_name(entry), entry_values, axis) for entry, entry_values in zip(series, values))
    return plotted


def axis_span(axis: ValueAxis) -> str:
    if axis.minimum is None:
        return f"up to {axis.maximum:g}"
    if axis.maximum is None:
        return f"from {axis.minimum:g}"
    return f"from {axis.minimum:g} to {axis.maximum:g}"


def outside_axis_issues(series_list: list[PlottedSeries], location: str, chart_name: str) -> list[Issue]:
    issues = []
    for series in series_list:
        if series.axis.is_logarithmic:
            continue
        outside = [value for value in series.values if not series.axis.holds(value)]
        if outside:
            listed = ", ".join(f"{value:g}" for value in outside)
            issues.append(CHART_POINT_OUTSIDE_AXIS.issue(f"{chart_name}: {series.name} has {listed} outside its axis, which runs {axis_span(series.axis)}", location))
    return issues


def zero_issues(series_list: list[PlottedSeries], location: str, chart_name: str) -> list[Issue]:
    axes = list({series.axis.identifier: series.axis for series in series_list if series.axis.is_bounded and not series.axis.is_logarithmic}.values())
    if len(axes) < 2 or not any(axis.minimum < 0 for axis in axes):
        return []
    heights = [axis.zero_height() for axis in axes]
    if max(heights) - min(heights) <= ZERO_HEIGHT_TOLERANCE:
        return []
    described = "; ".join(f"{', '.join(series.name for series in series_list if series.axis is axis)} put zero at {height:.0%} of the plot's height" for axis, height in zip(axes, heights))
    return [CHART_ZERO_MISALIGNED.issue(f"{chart_name}: two value axes draw zero at different heights: {described}", location)]


def chart_issues(chart_space, location: str, chart_name: str) -> list[Issue]:
    plot_area = chart_space.find(f"{qn('c:chart')}/{qn('c:plotArea')}")
    if plot_area is None:
        return []
    series_list = plotted_series(plot_area)
    return outside_axis_issues(series_list, location, chart_name) + zero_issues(series_list, location, chart_name)


def slide_chart_issues(slide, number: int) -> list[Issue]:
    return [
        issue
        for index, shape in enumerate(slide.shapes)
        if getattr(shape, "has_chart", False) and shape.has_chart
        for issue in chart_issues(shape.chart._chartSpace, f"slide {number}", f"chart {index} ({shape.name})")
    ]


def presentation_chart_issues(presentation) -> list[Issue]:
    return [issue for number, slide in enumerate(presentation.slides, start=1) for issue in slide_chart_issues(slide, number)]
