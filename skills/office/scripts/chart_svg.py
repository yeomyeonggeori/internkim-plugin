from __future__ import annotations

from dataclasses import dataclass
import math
from xml.sax.saxutils import escape


DEFAULT_PALETTE = ("#4472c4", "#ed7d31", "#a5a5a5", "#ffc000", "#5b9bd5", "#70ad47")
ROUND_KINDS = ("pie", "doughnut")
TITLE_HEIGHT = 26
CATEGORY_LABEL_HEIGHT = 20
LEGEND_HEIGHT = 20
VALUE_AXIS_WIDTH = 48
PADDING = 10
TICK_COUNT = 4
LABEL_COLOR = "#595959"
GRID_COLOR = "#e6e6e6"
AXIS_COLOR = "#8c8c8c"


@dataclass(frozen=True)
class ChartSeries:
    name: str
    values: tuple[float, ...]
    kind: str


@dataclass(frozen=True)
class ChartModel:
    categories: tuple[str, ...]
    series: tuple[ChartSeries, ...]
    title: str = ""
    stacked: bool = False
    legend: bool = True
    secondary_axis: bool = False

    @property
    def is_round(self) -> bool:
        return bool(self.series) and self.series[0].kind in ROUND_KINDS

    @property
    def is_horizontal(self) -> bool:
        return bool(self.series) and all(series.kind == "bar" for series in self.series)


@dataclass(frozen=True)
class Plot:
    left: float
    top: float
    right: float
    bottom: float
    low: float
    high: float


def chart_svg(model: ChartModel, width: float, height: float, font_family: str, palette: tuple[str, ...] = DEFAULT_PALETTE) -> str:
    colors = [palette[index % len(palette)] for index in range(max(len(model.series), len(model.categories), 1))]
    title = f'<text x="{width / 2:.1f}" y="18" text-anchor="middle" font-size="14" font-weight="700" fill="#262626">{escape(model.title)}</text>' if model.title else ""
    body = round_svg(model, width, height, colors) if model.is_round else axis_svg(model, width, height, colors)
    legend = legend_svg(model, width, height, colors) if model.legend else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" viewBox="0 0 {width:.1f} {height:.1f}" font-family="{escape(font_family)}">'
        f'<rect x="0.5" y="0.5" width="{width - 1:.1f}" height="{height - 1:.1f}" fill="#ffffff" stroke="#d9d9d9"/>{title}{body}{legend}</svg>'
    )


def legend_entries(model: ChartModel) -> list[str]:
    return list(model.categories) if model.is_round else [series.name for series in model.series]


def legend_svg(model: ChartModel, width: float, height: float, colors: list[str]) -> str:
    entries = legend_entries(model)
    widths = [22 + 7.5 * text_units(entry) for entry in entries]
    x = max(PADDING, (width - sum(widths)) / 2)
    y = height - 8
    items = []
    for index, (entry, entry_width) in enumerate(zip(entries, widths)):
        items.append(f'<rect x="{x:.1f}" y="{y - 9:.1f}" width="10" height="10" fill="{colors[index]}"/><text x="{x + 14:.1f}" y="{y:.1f}" font-size="11" fill="{LABEL_COLOR}">{escape(entry)}</text>')
        x += entry_width
    return "".join(items)


def text_units(text: str) -> float:
    return sum(1.7 if ord(character) > 0x2E80 else 1.0 for character in text)


def plot_frame(model: ChartModel, width: float, height: float, values: list[float]) -> Plot:
    low, high = value_range(values)
    top = (TITLE_HEIGHT if model.title else 0) + PADDING
    bottom = height - CATEGORY_LABEL_HEIGHT - (LEGEND_HEIGHT if model.legend else 0) - PADDING
    left = PADDING + (VALUE_AXIS_WIDTH if not model.is_horizontal else category_axis_width(model))
    right = width - PADDING * 2 - (VALUE_AXIS_WIDTH if model.secondary_axis else 0)
    return Plot(left, top, right, bottom, low, high)


def value_range(values: list[float]) -> tuple[float, float]:
    values = values or [0.0]
    low, high = min(0.0, min(values)), max(0.0, max(values))
    if high <= low:
        return low, low + 1
    return (-nice_ceiling(-low) if low < 0 else 0.0), nice_ceiling(high) if high > 0 else 0.0


def primary_values(model: ChartModel) -> list[float]:
    if model.stacked:
        return stacked_totals(model)
    return [value for series in model.series if not (model.secondary_axis and series.kind in ("line", "area")) for value in series.values]


def secondary_values(model: ChartModel) -> list[float]:
    return [value for series in model.series if series.kind in ("line", "area") for value in series.values]


def category_axis_width(model: ChartModel) -> float:
    return min(160.0, 12 + 7 * max((text_units(label) for label in model.categories), default=4))


def stacked_totals(model: ChartModel) -> list[float]:
    stacked = [series for series in model.series if series.kind in ("column", "bar")]
    count = max((len(series.values) for series in stacked), default=0)
    positives = [sum(max(0.0, series.values[index]) for series in stacked if index < len(series.values)) for index in range(count)]
    negatives = [sum(min(0.0, series.values[index]) for series in stacked if index < len(series.values)) for index in range(count)]
    others = [value for series in model.series if series.kind not in ("column", "bar") for value in series.values]
    return positives + negatives + others


def nice_ceiling(value: float) -> float:
    if value <= 0:
        return 0.0
    magnitude = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * magnitude:
            return step * magnitude
    return 10 * magnitude


def scaled(value: float, plot: Plot, start: float, end: float) -> float:
    return start + (value - plot.low) / (plot.high - plot.low) * (end - start)


def short_number(value: float) -> str:
    if abs(value) >= 1e8:
        return f"{value / 1e8:g}억"
    if abs(value) >= 1e4:
        return f"{value / 1e4:g}만"
    return f"{value:,.0f}" if value == int(value) else f"{value:g}"


def axis_svg(model: ChartModel, width: float, height: float, colors: list[str]) -> str:
    plot = plot_frame(model, width, height, primary_values(model))
    if model.is_horizontal:
        return value_grid(plot, horizontal=True) + horizontal_bars(model, plot, colors) + category_labels(model, plot, horizontal=True)
    line_plot = plot
    parts = [value_grid(plot, horizontal=False), column_bars(model, plot, colors)]
    if model.secondary_axis:
        low, high = value_range(secondary_values(model))
        line_plot = Plot(plot.left, plot.top, plot.right, plot.bottom, low, high)
        parts.append(right_axis_labels(line_plot))
    parts += [area_and_lines(model, line_plot, colors), category_labels(model, plot, horizontal=False)]
    return "".join(parts)


def right_axis_labels(plot: Plot) -> str:
    labels = []
    for step in range(TICK_COUNT + 1):
        value = plot.low + (plot.high - plot.low) * step / TICK_COUNT
        y = scaled(value, plot, plot.bottom, plot.top)
        labels.append(f'<text x="{plot.right + 6:.1f}" y="{y + 4:.1f}" font-size="10" fill="{LABEL_COLOR}">{escape(short_number(value))}</text>')
    return "".join(labels)


def value_grid(plot: Plot, horizontal: bool) -> str:
    parts = []
    for step in range(TICK_COUNT + 1):
        value = plot.low + (plot.high - plot.low) * step / TICK_COUNT
        if horizontal:
            x = scaled(value, plot, plot.left, plot.right)
            parts.append(f'<line x1="{x:.1f}" y1="{plot.top:.1f}" x2="{x:.1f}" y2="{plot.bottom:.1f}" stroke="{GRID_COLOR}"/><text x="{x:.1f}" y="{plot.bottom + 14:.1f}" text-anchor="middle" font-size="10" fill="{LABEL_COLOR}">{escape(short_number(value))}</text>')
        else:
            y = scaled(value, plot, plot.bottom, plot.top)
            parts.append(f'<line x1="{plot.left:.1f}" y1="{y:.1f}" x2="{plot.right:.1f}" y2="{y:.1f}" stroke="{GRID_COLOR}"/><text x="{plot.left - 6:.1f}" y="{y + 4:.1f}" text-anchor="end" font-size="10" fill="{LABEL_COLOR}">{escape(short_number(value))}</text>')
    return "".join(parts)


def bar_series(model: ChartModel, kinds: tuple[str, ...]) -> list[tuple[int, ChartSeries]]:
    return [(index, series) for index, series in enumerate(model.series) if series.kind in kinds]


def column_bars(model: ChartModel, plot: Plot, colors: list[str]) -> str:
    bars = bar_series(model, ("column",))
    if not bars or not model.categories:
        return ""
    slot = (plot.right - plot.left) / len(model.categories)
    lanes = 1 if model.stacked else len(bars)
    width = slot * 0.65 / lanes
    zero = scaled(0.0, plot, plot.bottom, plot.top)
    shapes, offsets = [], [0.0] * len(model.categories)
    for lane, (index, series) in enumerate(bars):
        for position, value in enumerate(series.values[:len(model.categories)]):
            base = offsets[position] if model.stacked else 0.0
            x = plot.left + slot * position + slot * 0.175 + width * (0 if model.stacked else lane)
            start, end = scaled(base, plot, plot.bottom, plot.top), scaled(base + value, plot, plot.bottom, plot.top)
            shapes.append(f'<rect x="{x:.1f}" y="{min(start, end):.1f}" width="{width:.1f}" height="{abs(end - start):.1f}" fill="{colors[index]}"/>')
            if model.stacked:
                offsets[position] += value
    return "".join(shapes) + f'<line x1="{plot.left:.1f}" y1="{zero:.1f}" x2="{plot.right:.1f}" y2="{zero:.1f}" stroke="{AXIS_COLOR}"/>'


def horizontal_bars(model: ChartModel, plot: Plot, colors: list[str]) -> str:
    bars = bar_series(model, ("bar",))
    if not bars or not model.categories:
        return ""
    slot = (plot.bottom - plot.top) / len(model.categories)
    lanes = 1 if model.stacked else len(bars)
    thickness = slot * 0.65 / lanes
    shapes, offsets = [], [0.0] * len(model.categories)
    for lane, (index, series) in enumerate(bars):
        for position, value in enumerate(series.values[:len(model.categories)]):
            base = offsets[position] if model.stacked else 0.0
            y = plot.top + slot * position + slot * 0.175 + thickness * (0 if model.stacked else lane)
            start, end = scaled(base, plot, plot.left, plot.right), scaled(base + value, plot, plot.left, plot.right)
            shapes.append(f'<rect x="{min(start, end):.1f}" y="{y:.1f}" width="{abs(end - start):.1f}" height="{thickness:.1f}" fill="{colors[index]}"/>')
            if model.stacked:
                offsets[position] += value
    zero = scaled(0.0, plot, plot.left, plot.right)
    return "".join(shapes) + f'<line x1="{zero:.1f}" y1="{plot.top:.1f}" x2="{zero:.1f}" y2="{plot.bottom:.1f}" stroke="{AXIS_COLOR}"/>'


def area_and_lines(model: ChartModel, plot: Plot, colors: list[str]) -> str:
    if not model.categories:
        return ""
    slot = (plot.right - plot.left) / len(model.categories)
    zero = scaled(0.0, plot, plot.bottom, plot.top)
    shapes = []
    for index, series in bar_series(model, ("area", "line")):
        points = [(plot.left + slot * (position + 0.5), scaled(value, plot, plot.bottom, plot.top)) for position, value in enumerate(series.values[:len(model.categories)])]
        if not points:
            continue
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        if series.kind == "area":
            shapes.append(f'<polygon points="{points[0][0]:.1f},{zero:.1f} {path} {points[-1][0]:.1f},{zero:.1f}" fill="{colors[index]}" fill-opacity="0.55"/>')
            continue
        shapes.append(f'<polyline points="{path}" fill="none" stroke="{colors[index]}" stroke-width="2.5"/>')
        shapes.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{colors[index]}"/>' for x, y in points)
    return "".join(shapes)


def category_labels(model: ChartModel, plot: Plot, horizontal: bool) -> str:
    if not model.categories:
        return ""
    if horizontal:
        slot = (plot.bottom - plot.top) / len(model.categories)
        return "".join(f'<text x="{plot.left - 6:.1f}" y="{plot.top + slot * (index + 0.5) + 4:.1f}" text-anchor="end" font-size="10" fill="{LABEL_COLOR}">{escape(label)}</text>' for index, label in enumerate(model.categories))
    slot = (plot.right - plot.left) / len(model.categories)
    return "".join(f'<text x="{plot.left + slot * (index + 0.5):.1f}" y="{plot.bottom + 14:.1f}" text-anchor="middle" font-size="10" fill="{LABEL_COLOR}">{escape(label)}</text>' for index, label in enumerate(model.categories))


def round_svg(model: ChartModel, width: float, height: float, colors: list[str]) -> str:
    series = model.series[0]
    total = sum(abs(value) for value in series.values)
    if total <= 0:
        return ""
    top = (TITLE_HEIGHT if model.title else 0) + PADDING
    bottom = height - (LEGEND_HEIGHT if model.legend else 0) - PADDING
    radius = max(10.0, min(width - 2 * PADDING, bottom - top) / 2)
    center_x, center_y = width / 2, (top + bottom) / 2
    inner = radius * 0.55 if series.kind == "doughnut" else 0.0
    slices, angle = [], -math.pi / 2
    for index, value in enumerate(series.values):
        sweep = 2 * math.pi * abs(value) / total
        slices.append(slice_path(center_x, center_y, radius, inner, angle, angle + sweep, colors[index]))
        middle = angle + sweep / 2
        label_radius = (radius + inner) / 2 if inner else radius * 0.62
        share = f"{abs(value) / total:.0%}"
        if sweep > 0.25:
            slices.append(f'<text x="{center_x + label_radius * math.cos(middle):.1f}" y="{center_y + label_radius * math.sin(middle) + 4:.1f}" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">{share}</text>')
        angle += sweep
    return "".join(slices)


def slice_path(center_x: float, center_y: float, radius: float, inner: float, start: float, end: float, color: str) -> str:
    if end - start >= 2 * math.pi - 1e-6:
        end = start + 2 * math.pi - 1e-4
    large = 1 if end - start > math.pi else 0
    outer_start = (center_x + radius * math.cos(start), center_y + radius * math.sin(start))
    outer_end = (center_x + radius * math.cos(end), center_y + radius * math.sin(end))
    if not inner:
        path = f"M{center_x:.1f},{center_y:.1f} L{outer_start[0]:.1f},{outer_start[1]:.1f} A{radius:.1f},{radius:.1f} 0 {large} 1 {outer_end[0]:.1f},{outer_end[1]:.1f} Z"
    else:
        inner_start = (center_x + inner * math.cos(end), center_y + inner * math.sin(end))
        inner_end = (center_x + inner * math.cos(start), center_y + inner * math.sin(start))
        path = (
            f"M{outer_start[0]:.1f},{outer_start[1]:.1f} A{radius:.1f},{radius:.1f} 0 {large} 1 {outer_end[0]:.1f},{outer_end[1]:.1f} "
            f"L{inner_start[0]:.1f},{inner_start[1]:.1f} A{inner:.1f},{inner:.1f} 0 {large} 0 {inner_end[0]:.1f},{inner_end[1]:.1f} Z"
        )
    return f'<path d="{path}" fill="{color}" stroke="#ffffff" stroke-width="1.5"/>'
