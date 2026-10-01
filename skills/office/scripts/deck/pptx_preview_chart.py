from __future__ import annotations

from dataclasses import dataclass
import html
import math

from pptx_chart_look import ChartLook, LabelLook, TextLook, formatted


TITLE_HEIGHT = 28
LEGEND_ROW_HEIGHT = 24
LEGEND_SHARE = 0.4
AXIS_LABEL_WIDTH = 40
CATEGORY_LABEL_HEIGHT = 20
EDGE = 8
MOST_GRID_LINES = 7
TITLE_SIZE = 19
LABEL_GAP = 4
PIE_LABEL_RADIUS_SHARE = 0.6


@dataclass(frozen=True)
class Plot:
    left: float
    top: float
    width: float
    height: float


@dataclass(frozen=True)
class Scale:
    low: float
    high: float
    step: float


def chart_svg(details: dict, width: float, height: float, look: ChartLook, font_family: str) -> str:
    kind = details["type"]
    series = [entry for entry in details["series"] if entry["values"]]
    round_chart = "pie" in kind or "doughnut" in kind
    title_space = TITLE_HEIGHT if details.get("title") else 0
    if round_chart:
        legend_labels = [str(category) for category in details["categories"]]
        legend_colors = [look.slice_color(index) for index in range(len(legend_labels))]
    else:
        legend_labels = [entry["name"] for entry in series]
        legend_colors = look.series_colors
    area = Plot(EDGE, EDGE + title_space, width - 2 * EDGE, height - 2 * EDGE - title_space)
    plot, legend = split_legend(area, look.legend_position if legend_labels else None)
    parts = [title_svg(details.get("title"), width, font_family)]
    if round_chart:
        parts.append(pie_svg(series[0] if series else {"values": []}, plot, look, "doughnut" in kind, font_family))
    else:
        parts.append(axis_chart_svg(kind, details["categories"], series, plot, look, font_family))
    if legend is not None:
        parts.append(legend_svg(legend_labels, legend_colors, legend, look.legend_position, look.text, font_family))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" viewBox="0 0 {width:.1f} {height:.1f}">{"".join(parts)}</svg>'


def split_legend(area: Plot, position: str | None) -> tuple[Plot, Plot | None]:
    if position is None:
        return area, None
    if position == "r":
        legend_width = area.width * LEGEND_SHARE
        return Plot(area.left, area.top, area.width - legend_width, area.height), Plot(area.left + area.width - legend_width, area.top, legend_width, area.height)
    if position == "t":
        return Plot(area.left, area.top + LEGEND_ROW_HEIGHT, area.width, area.height - LEGEND_ROW_HEIGHT), Plot(area.left, area.top, area.width, LEGEND_ROW_HEIGHT)
    return Plot(area.left, area.top, area.width, area.height - LEGEND_ROW_HEIGHT), Plot(area.left, area.top + area.height - LEGEND_ROW_HEIGHT, area.width, LEGEND_ROW_HEIGHT)


def text_svg(x: float, y: float, text: str, font_family: str, look: TextLook, anchor: str = "middle") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{html.escape(font_family)}" font-size="{look.size:.1f}" fill="{look.color}" '
        f'text-anchor="{anchor}" dominant-baseline="middle">{html.escape(text)}</text>'
    )


def title_svg(title: str | None, width: float, font_family: str) -> str:
    return text_svg(width / 2, EDGE + TITLE_HEIGHT / 2, title, font_family, TextLook(size=TITLE_SIZE)) if title else ""


def nice_step(span: float) -> float:
    raw = span / MOST_GRID_LINES if span > 0 else 1.0
    magnitude = 10 ** math.floor(math.log10(raw))
    return next(step * magnitude for step in (1, 2, 5, 10) if step * magnitude >= raw)


def value_scale(kind: str, series: list[dict], look: ChartLook) -> Scale:
    fixed_low, fixed_high = look.value_limits
    if fixed_low is not None and fixed_high is not None and fixed_high > fixed_low:
        return Scale(fixed_low, fixed_high, look.major_unit or nice_step(fixed_high - fixed_low))
    if "stacked" in kind:
        values = [sum(entry["values"][index] or 0 for entry in series) for index in range(len(series[0]["values"]))]
    else:
        values = [number or 0 for entry in series for number in entry["values"]]
    low, high = min(0.0, min(values)), max(0.0, max(values))
    step = look.major_unit or nice_step(high - low)
    return Scale(math.floor(low / step) * step, max(math.ceil(high / step), 1) * step, step)


def category_order(count: int, horizontal: bool, look: ChartLook) -> list[int]:
    order = list(range(count))
    return order[::-1] if look.reversed_categories != horizontal else order


def axis_chart_svg(kind: str, categories: list, series: list[dict], plot: Plot, look: ChartLook, font_family: str) -> str:
    if not series:
        return ""
    horizontal = kind.startswith("bar")
    value_labels_width = AXIS_LABEL_WIDTH if look.value_axis_shown and not horizontal else 0
    category_width = AXIS_LABEL_WIDTH * 2 if horizontal else 0
    bottom_labels = CATEGORY_LABEL_HEIGHT if not horizontal or look.value_axis_shown else 0
    area = Plot(plot.left + value_labels_width + category_width, plot.top, plot.width - value_labels_width - category_width, plot.height - bottom_labels)
    order = category_order(len(categories), horizontal, look)
    scale = value_scale(kind, series, look)
    parts = [grid_svg(area, scale, horizontal, look, font_family), category_labels_svg([categories[index] for index in order], area, horizontal, look.text, font_family), axis_line_svg(area, scale, horizontal, look.axis_line)]
    if "line" in kind or "area" in kind:
        parts.extend(line_svg(entry, position, order, area, scale, look, "area" in kind, font_family) for position, entry in enumerate(series))
    else:
        parts.append(bars_svg(kind, series, order, area, scale, look, horizontal, font_family))
    return "".join(parts)


def scaled(number: float, scale: Scale, length: float) -> float:
    return (number - scale.low) / (scale.high - scale.low) * length


def grid_svg(area: Plot, scale: Scale, horizontal: bool, look: ChartLook, font_family: str) -> str:
    parts = []
    steps = max(1, round((scale.high - scale.low) / scale.step))
    for step in range(steps + 1):
        label = f"{scale.low + scale.step * step:g}"
        if horizontal:
            x = area.left + area.width * step / steps
            if look.gridlines:
                parts.append(f'<line x1="{x:.1f}" y1="{area.top:.1f}" x2="{x:.1f}" y2="{area.top + area.height:.1f}" stroke="{look.gridlines}"/>')
            if look.value_axis_shown:
                parts.append(text_svg(x, area.top + area.height + CATEGORY_LABEL_HEIGHT / 2, label, font_family, look.text))
        else:
            y = area.top + area.height - area.height * step / steps
            if look.gridlines:
                parts.append(f'<line x1="{area.left:.1f}" y1="{y:.1f}" x2="{area.left + area.width:.1f}" y2="{y:.1f}" stroke="{look.gridlines}"/>')
            if look.value_axis_shown:
                parts.append(text_svg(area.left - LABEL_GAP, y, label, font_family, look.text, "end"))
    return "".join(parts)


def axis_line_svg(area: Plot, scale: Scale, horizontal: bool, color: str | None) -> str:
    if color is None:
        return ""
    if horizontal:
        x = area.left + scaled(max(scale.low, 0), scale, area.width)
        return f'<line x1="{x:.1f}" y1="{area.top:.1f}" x2="{x:.1f}" y2="{area.top + area.height:.1f}" stroke="{color}" stroke-width="1.5"/>'
    y = area.top + area.height - scaled(max(scale.low, 0), scale, area.height)
    return f'<line x1="{area.left:.1f}" y1="{y:.1f}" x2="{area.left + area.width:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="1.5"/>'


def category_labels_svg(categories: list, area: Plot, horizontal: bool, text: TextLook, font_family: str) -> str:
    count = max(len(categories), 1)
    parts = []
    for index, category in enumerate(categories):
        if horizontal:
            parts.append(text_svg(area.left - LABEL_GAP, area.top + area.height * (index + 0.5) / count, str(category), font_family, text, "end"))
        else:
            parts.append(text_svg(area.left + area.width * (index + 0.5) / count, area.top + area.height + CATEGORY_LABEL_HEIGHT / 2, str(category), font_family, text))
    return "".join(parts)


def bars_svg(kind: str, series: list[dict], order: list[int], area: Plot, scale: Scale, look: ChartLook, horizontal: bool, font_family: str) -> str:
    band = (area.height if horizontal else area.width) / max(len(order), 1)
    stacked = "stacked" in kind
    share = 1 / (1 + look.gap_width / 100)
    thickness = band * share / (1 if stacked else len(series))
    length_axis = area.width if horizontal else area.height
    bars, labels = [], []
    for slot, index in enumerate(order):
        offset = 0.0
        for position, entry in enumerate(series):
            number = entry["values"][index] or 0
            start = scaled(offset if stacked else max(scale.low, 0), scale, length_axis)
            end = scaled((offset if stacked else 0) + number, scale, length_axis)
            across = band * slot + band * (1 - share) / 2 + (0 if stacked else thickness * position)
            bars.append(bar_rectangle(area, horizontal, across, thickness, min(start, end), abs(end - start), look.color_of(position, index)))
            labels.append(bar_label_svg(look.labels[position], index, number, area, horizontal, (across + thickness / 2, start, end), font_family))
            offset += number if stacked else 0
    return "".join(bars + labels)


def bar_rectangle(area: Plot, horizontal: bool, across: float, thickness: float, start: float, length: float, color: str) -> str:
    if horizontal:
        return f'<rect x="{area.left + start:.1f}" y="{area.top + across:.1f}" width="{length:.1f}" height="{thickness:.1f}" fill="{color}"/>'
    return f'<rect x="{area.left + across:.1f}" y="{area.top + area.height - start - length:.1f}" width="{thickness:.1f}" height="{length:.1f}" fill="{color}"/>'


def bar_label_svg(labels: LabelLook | None, index: int, number: float, area: Plot, horizontal: bool, span: tuple[float, float, float], font_family: str) -> str:
    label = labels.at(index) if labels is not None else None
    if label is None or not label.shown:
        return ""
    middle, start, end = span
    text = label.text
    centered = label.position == "ctr"
    along = (start + end) / 2 if centered else end
    shown = formatted(number, label.format_code)
    if horizontal:
        return text_svg(area.left + along + (0 if centered else LABEL_GAP), area.top + middle, shown, font_family, text, "middle" if centered else "start")
    return text_svg(area.left + middle, area.top + area.height - along - (0 if centered else text.size / 2 + LABEL_GAP), shown, font_family, text)


def line_svg(entry: dict, position: int, order: list[int], area: Plot, scale: Scale, look: ChartLook, filled: bool, font_family: str) -> str:
    count = max(len(order), 1)
    color = look.series_colors[position]
    points = [(area.left + area.width * (slot + 0.5) / count, area.top + area.height - scaled(entry["values"][index] or 0, scale, area.height)) for slot, index in enumerate(order)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    if filled:
        baseline = area.top + area.height - scaled(max(scale.low, 0), scale, area.height)
        return f'<polygon points="{points[0][0]:.1f},{baseline:.1f} {path} {points[-1][0]:.1f},{baseline:.1f}" fill="{color}" fill-opacity="0.8"/>'
    markers = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>' for x, y in points)
    labels = "".join(line_label_svg(look.labels[position], index, entry["values"][index] or 0, x, y, font_family) for (x, y), index in zip(points, order))
    return f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="2.25"/>{markers}{labels}'


def line_label_svg(labels: LabelLook | None, index: int, number: float, x: float, y: float, font_family: str) -> str:
    label = labels.at(index) if labels is not None else None
    if label is None or not label.shown:
        return ""
    offset = label.text.size / 2 + LABEL_GAP
    return text_svg(x, y + offset if label.position == "b" else y - offset, formatted(number, label.format_code), font_family, label.text)


def pie_svg(entry: dict, plot: Plot, look: ChartLook, doughnut: bool, font_family: str) -> str:
    values = [max(number or 0, 0) for number in entry["values"]]
    total = sum(values) or 1
    radius = min(plot.width, plot.height) / 2
    hole = radius * look.hole_percent / 100 if doughnut else 0
    center_x, center_y = plot.left + plot.width / 2, plot.top + plot.height / 2
    label = look.labels[0] if look.labels else None
    slices, labels, angle = [], [], -math.pi / 2
    for index, number in enumerate(values):
        sweep = 2 * math.pi * number / total
        slices.append(slice_path((center_x, center_y), radius, hole, angle, sweep, look.slice_color(index)))
        point = label.at(index) if label is not None else None
        if point is not None and point.shown and number:
            middle = angle + sweep / 2
            distance = (radius + hole) / 2 if doughnut else radius * PIE_LABEL_RADIUS_SHARE
            shown = formatted(number / total if point.show_percent else number, point.format_code)
            labels.append(text_svg(center_x + distance * math.cos(middle), center_y + distance * math.sin(middle), shown, font_family, point.text))
        angle += sweep
    return "".join(slices + labels)


def arc_point(center: tuple[float, float], radius: float, angle: float) -> str:
    return f"{center[0] + radius * math.cos(angle):.1f},{center[1] + radius * math.sin(angle):.1f}"


def slice_path(center: tuple[float, float], radius: float, hole: float, start: float, sweep: float, color: str) -> str:
    full = sweep >= 2 * math.pi - 1e-6
    end = start + (2 * math.pi - 1e-4 if full else sweep)
    large = 1 if end - start > math.pi else 0
    outer = f"M{arc_point(center, radius, start)} A{radius:.1f},{radius:.1f} 0 {large} 1 {arc_point(center, radius, end)}"
    if hole <= 0:
        return f'<path d="M{center[0]:.1f},{center[1]:.1f} L{outer[1:]} Z" fill="{color}"/>'
    inner = f"L{arc_point(center, hole, end)} A{hole:.1f},{hole:.1f} 0 {large} 0 {arc_point(center, hole, start)}"
    return f'<path d="{outer} {inner} Z" fill="{color}"/>'


def legend_svg(labels: list[str], colors: list[str], area: Plot, position: str, text: TextLook, font_family: str) -> str:
    swatch = max(8.0, text.size * 0.7)
    parts = []
    for index, (label, color) in enumerate(zip(labels, colors)):
        if position == "r":
            x, y = area.left + EDGE, area.top + area.height / 2 + (index - (len(labels) - 1) / 2) * text.size * 2
        else:
            slot = area.width / len(labels)
            x, y = area.left + slot * index + slot / 2 - 20, area.top + area.height / 2
        parts.append(f'<rect x="{x:.1f}" y="{y - swatch / 2:.1f}" width="{swatch:.1f}" height="{swatch:.1f}" fill="{color}"/>')
        parts.append(text_svg(x + swatch + LABEL_GAP, y, label, font_family, text, "start"))
    return "".join(parts)
