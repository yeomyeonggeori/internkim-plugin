from __future__ import annotations

from dataclasses import dataclass
import html
import math

from pptx_style import theme_slot_color


ACCENT_SLOTS = ("accent1", "accent2", "accent3", "accent4", "accent5", "accent6")
TITLE_HEIGHT = 28
LEGEND_HEIGHT = 24
AXIS_LABEL_WIDTH = 40
CATEGORY_LABEL_HEIGHT = 20
EDGE = 8
MOST_GRID_LINES = 7
LABEL_SIZE = 13
TITLE_SIZE = 19
GRID_COLOR = "#D9D9D9"
TEXT_COLOR = "#404040"
BAR_SHARE = 0.7


@dataclass(frozen=True)
class Plot:
    left: float
    top: float
    width: float
    height: float


def chart_svg(details: dict, width: float, height: float, context, font_family: str) -> str:
    colors = [theme_slot_color(context, slot) or "4472C4" for slot in ACCENT_SLOTS]
    colors = ["#" + color.lstrip("#") for color in colors]
    kind = details["type"]
    series = [entry for entry in details["series"] if entry["values"]]
    title_space = TITLE_HEIGHT if details.get("title") else 0
    round_chart = "pie" in kind or "doughnut" in kind
    legend_space = LEGEND_HEIGHT if len(series) > 1 or round_chart else 0
    parts = [title_svg(details.get("title"), width, font_family)]
    plot = Plot(EDGE, EDGE + title_space, width - 2 * EDGE, height - 2 * EDGE - title_space - legend_space)
    if round_chart:
        parts.append(pie_svg(series[0] if series else {"values": []}, plot, colors, "doughnut" in kind))
        labels = [str(category) for category in details["categories"]]
    else:
        parts.append(axis_chart_svg(kind, details["categories"], series, plot, colors, font_family))
        labels = [entry["name"] for entry in series]
    if legend_space:
        parts.append(legend_svg(labels, colors, width, height - EDGE - LEGEND_HEIGHT / 2, font_family))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" viewBox="0 0 {width:.1f} {height:.1f}">{"".join(parts)}</svg>'


def text_svg(x: float, y: float, text: str, font_family: str, size: int, anchor: str = "middle") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="{html.escape(font_family)}" font-size="{size}" fill="{TEXT_COLOR}" text-anchor="{anchor}" dominant-baseline="middle">{html.escape(text)}</text>'


def title_svg(title: str | None, width: float, font_family: str) -> str:
    return text_svg(width / 2, EDGE + TITLE_HEIGHT / 2, title, font_family, TITLE_SIZE) if title else ""


@dataclass(frozen=True)
class Scale:
    low: float
    high: float
    step: float


def nice_step(span: float) -> float:
    raw = span / MOST_GRID_LINES if span > 0 else 1.0
    magnitude = 10 ** math.floor(math.log10(raw))
    return next(step * magnitude for step in (1, 2, 5, 10) if step * magnitude >= raw)


def value_scale(kind: str, series: list[dict]) -> Scale:
    if "stacked" in kind:
        values = [sum(entry["values"][index] or 0 for entry in series) for index in range(len(series[0]["values"]))]
    else:
        values = [value or 0 for entry in series for value in entry["values"]]
    low, high = min(0.0, min(values)), max(0.0, max(values))
    step = nice_step(high - low)
    return Scale(math.floor(low / step) * step, max(math.ceil(high / step), 1) * step, step)


def axis_chart_svg(kind: str, categories: list, series: list[dict], plot: Plot, colors: list[str], font_family: str) -> str:
    if not series:
        return ""
    horizontal = kind.startswith("bar")
    area = Plot(plot.left + AXIS_LABEL_WIDTH, plot.top, plot.width - AXIS_LABEL_WIDTH, plot.height - CATEGORY_LABEL_HEIGHT)
    if horizontal:
        area = Plot(plot.left + AXIS_LABEL_WIDTH * 2, plot.top, plot.width - AXIS_LABEL_WIDTH * 2, plot.height - CATEGORY_LABEL_HEIGHT)
    scale = value_scale(kind, series)
    low, high = scale.low, scale.high
    parts = [grid_svg(area, scale, horizontal, font_family), category_labels_svg(categories, area, horizontal, font_family)]
    if "line" in kind or "area" in kind:
        parts.extend(line_svg(entry["values"], area, low, high, color, "area" in kind) for entry, color in zip(series, colors * 4))
    else:
        parts.append(bars_svg(kind, series, area, low, high, colors, horizontal))
    return "".join(parts)


def scaled(value: float, low: float, high: float, length: float) -> float:
    return (value - low) / (high - low) * length


def grid_svg(area: Plot, scale: Scale, horizontal: bool, font_family: str) -> str:
    parts = []
    steps = round((scale.high - scale.low) / scale.step)
    for step in range(steps + 1):
        value = scale.low + scale.step * step
        label = f"{value:g}"
        if horizontal:
            x = area.left + area.width * step / steps
            parts.append(f'<line x1="{x:.1f}" y1="{area.top:.1f}" x2="{x:.1f}" y2="{area.top + area.height:.1f}" stroke="{GRID_COLOR}"/>')
            parts.append(text_svg(x, area.top + area.height + CATEGORY_LABEL_HEIGHT / 2, label, font_family, LABEL_SIZE))
        else:
            y = area.top + area.height - area.height * step / steps
            parts.append(f'<line x1="{area.left:.1f}" y1="{y:.1f}" x2="{area.left + area.width:.1f}" y2="{y:.1f}" stroke="{GRID_COLOR}"/>')
            parts.append(text_svg(area.left - 4, y, label, font_family, LABEL_SIZE, "end"))
    return "".join(parts)


def category_labels_svg(categories: list, area: Plot, horizontal: bool, font_family: str) -> str:
    count = max(len(categories), 1)
    parts = []
    for index, category in enumerate(categories):
        if horizontal:
            y = area.top + area.height * (index + 0.5) / count
            parts.append(text_svg(area.left - 4, y, str(category), font_family, LABEL_SIZE, "end"))
        else:
            x = area.left + area.width * (index + 0.5) / count
            parts.append(text_svg(x, area.top + area.height + CATEGORY_LABEL_HEIGHT / 2, str(category), font_family, LABEL_SIZE))
    return "".join(parts)


def bars_svg(kind: str, series: list[dict], area: Plot, low: float, high: float, colors: list[str], horizontal: bool) -> str:
    count = len(series[0]["values"])
    band = (area.height if horizontal else area.width) / max(count, 1)
    stacked = "stacked" in kind
    thickness = band * BAR_SHARE / (1 if stacked else len(series))
    length_axis = area.width if horizontal else area.height
    parts = []
    for index in range(count):
        offset = 0.0
        for position, (entry, color) in enumerate(zip(series, colors * 4)):
            value = entry["values"][index] or 0
            start = scaled(offset if stacked else max(low, 0), low, high, length_axis)
            end = scaled((offset if stacked else 0) + value, low, high, length_axis)
            across = band * index + band * (1 - BAR_SHARE) / 2 + (0 if stacked else thickness * position)
            parts.append(bar_rectangle(area, horizontal, across, thickness, min(start, end), abs(end - start), color))
            offset += value if stacked else 0
    return "".join(parts)


def bar_rectangle(area: Plot, horizontal: bool, across: float, thickness: float, start: float, length: float, color: str) -> str:
    if horizontal:
        return f'<rect x="{area.left + start:.1f}" y="{area.top + across:.1f}" width="{length:.1f}" height="{thickness:.1f}" fill="{color}"/>'
    return f'<rect x="{area.left + across:.1f}" y="{area.top + area.height - start - length:.1f}" width="{thickness:.1f}" height="{length:.1f}" fill="{color}"/>'


def line_svg(values: list, area: Plot, low: float, high: float, color: str, filled: bool) -> str:
    count = max(len(values), 1)
    points = [(area.left + area.width * (index + 0.5) / count, area.top + area.height - scaled(value or 0, low, high, area.height)) for index, value in enumerate(values)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    if filled:
        baseline = area.top + area.height - scaled(max(low, 0), low, high, area.height)
        return f'<polygon points="{points[0][0]:.1f},{baseline:.1f} {path} {points[-1][0]:.1f},{baseline:.1f}" fill="{color}" fill-opacity="0.8"/>'
    markers = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>' for x, y in points)
    return f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="2.25"/>{markers}'


def pie_svg(entry: dict, plot: Plot, colors: list[str], doughnut: bool) -> str:
    values = [max(value or 0, 0) for value in entry["values"]]
    total = sum(values) or 1
    radius = min(plot.width, plot.height) / 2
    center_x, center_y = plot.left + plot.width / 2, plot.top + plot.height / 2
    parts, angle = [], -math.pi / 2
    for value, color in zip(values, colors * 4):
        sweep = 2 * math.pi * value / total
        parts.append(slice_path(center_x, center_y, radius, angle, sweep, color))
        angle += sweep
    if doughnut:
        parts.append(f'<circle cx="{center_x:.1f}" cy="{center_y:.1f}" r="{radius / 2:.1f}" fill="#FFFFFF"/>')
    return "".join(parts)


def slice_path(center_x: float, center_y: float, radius: float, start: float, sweep: float, color: str) -> str:
    if sweep >= 2 * math.pi - 1e-6:
        return f'<circle cx="{center_x:.1f}" cy="{center_y:.1f}" r="{radius:.1f}" fill="{color}"/>'
    end = start + sweep
    start_point = (center_x + radius * math.cos(start), center_y + radius * math.sin(start))
    end_point = (center_x + radius * math.cos(end), center_y + radius * math.sin(end))
    large = 1 if sweep > math.pi else 0
    return f'<path d="M{center_x:.1f},{center_y:.1f} L{start_point[0]:.1f},{start_point[1]:.1f} A{radius:.1f},{radius:.1f} 0 {large} 1 {end_point[0]:.1f},{end_point[1]:.1f} Z" fill="{color}"/>'


def legend_svg(labels: list[str], colors: list[str], width: float, y: float, font_family: str) -> str:
    slot = width / max(len(labels), 1)
    parts = []
    for index, (label, color) in enumerate(zip(labels, colors * 4)):
        x = slot * index + slot / 2 - 20
        parts.append(f'<rect x="{x:.1f}" y="{y - 5:.1f}" width="10" height="10" fill="{color}"/>')
        parts.append(text_svg(x + 14, y, label, font_family, LABEL_SIZE, "start"))
    return "".join(parts)
