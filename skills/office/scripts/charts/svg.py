from __future__ import annotations

from dataclasses import dataclass, replace
import math
from xml.sax.saxutils import escape

from charts.kinds import ROUND_CHART_KINDS
from charts.look import BELOW_POSITION, LEFT_POSITION, OUTSIDE_POSITION, PERCENT_FORMAT, ChartLook, PointLabel, TextLook
from number_format import displayed


EDGE = 8
LABEL_GAP = 4
AXIS_LABEL_WIDTH = 44
CATEGORY_LABEL_HEIGHT = 20
LEGEND_ROW_HEIGHT = 24
LEGEND_SHARE = 0.4
MOST_GRID_LINES = 7
TITLE_LINE_SHARE = 1.6
END_LABEL_SHARE = 1.5
SWATCH_SHARE = 0.75
PIE_LABEL_RADIUS_SHARE = 0.62
OUTSIDE_LABEL_ROOM = 0.82
SMALLEST_LABELLED_SWEEP = 0.25
AREA_OPACITY = 0.55
LINE_WIDTH = 2.5
MARKER_RADIUS = 3.5
SCATTER_RADIUS = 5
SLICE_STROKE = "#FFFFFF"
BAR_KINDS = ("column", "bar")
LINE_KINDS = ("line", "area", "radar")
LATIN_WIDTH_SHARE = 0.6
WIDE_WIDTH_SHARE = 1.0
WIDE_CHARACTER_START = 0x2E80


@dataclass(frozen=True)
class ChartSeries:
    name: str
    values: tuple[float, ...]
    kind: str
    x_values: tuple[float, ...] = ()


@dataclass(frozen=True)
class ChartModel:
    categories: tuple[str, ...]
    series: tuple[ChartSeries, ...]
    title: str = ""
    stacked: bool = False
    percent_stacked: bool = False
    secondary_axis: bool = False

    @property
    def is_round(self) -> bool:
        return bool(self.series) and self.series[0].kind in ROUND_CHART_KINDS

    @property
    def is_scatter(self) -> bool:
        return bool(self.series) and self.series[0].kind == "scatter"

    @property
    def is_horizontal(self) -> bool:
        return bool(self.series) and all(series.kind == "bar" for series in self.series)


@dataclass(frozen=True)
class Plot:
    left: float
    top: float
    width: float
    height: float

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def right(self) -> float:
        return self.left + self.width


@dataclass(frozen=True)
class Scale:
    low: float
    high: float
    step: float


def chart_svg(model: ChartModel, width: float, height: float, look: ChartLook, font_family: str) -> str:
    look = look.typeset(font_family)
    title_space = look.title.size * TITLE_LINE_SHARE if model.title else 0
    area = Plot(EDGE, EDGE + title_space, width - 2 * EDGE, height - 2 * EDGE - title_space)
    entries = legend_entries(model, look)
    plot, legend = split_legend(area, look.legend_position if entries else None, entries, look.text)
    parts = [frame_svg(width, height, look.frame), title_svg(model.title, width, look.title), body_svg(model, plot, look)]
    if legend is not None:
        parts.append(legend_svg(entries, legend, look.legend_position, look.text))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" viewBox="0 0 {width:.1f} {height:.1f}">'
        f'{"".join(parts)}</svg>'
    )


def body_svg(model: ChartModel, plot: Plot, look: ChartLook) -> str:
    if model.is_round:
        return round_svg(model, plot, look)
    if model.is_scatter:
        return scatter_svg(model, plot, look)
    return axis_chart_svg(model, plot, look)


def frame_svg(width: float, height: float, color: str | None) -> str:
    if color is None:
        return ""
    return f'<rect x="0.5" y="0.5" width="{width - 1:.1f}" height="{height - 1:.1f}" fill="#FFFFFF" stroke="{color}"/>'


def title_svg(title: str, width: float, look: TextLook) -> str:
    return text_svg(width / 2, EDGE + look.size * TITLE_LINE_SHARE / 2, title, look) if title else ""


def text_svg(x: float, y: float, text: str, look: TextLook, anchor: str = "middle") -> str:
    if not text:
        return ""
    weight = ' font-weight="700"' if look.bold else ""
    family = f' font-family="{escape(look.family)}"' if look.family else ""
    return f'<text x="{x:.1f}" y="{y:.1f}"{family} font-size="{look.size:.1f}"{weight} fill="{look.color}" text-anchor="{anchor}" dominant-baseline="middle">{escape(text)}</text>'


def text_width(text: str, look: TextLook) -> float:
    return sum(look.size * (WIDE_WIDTH_SHARE if ord(character) >= WIDE_CHARACTER_START else LATIN_WIDTH_SHARE) for character in text)


def legend_entries(model: ChartModel, look: ChartLook) -> list[tuple[str, str]]:
    if model.is_round:
        return [(str(category), look.slice_color(index)) for index, category in enumerate(model.categories)]
    if model.is_scatter:
        return []
    return [(series.name, look.color_of(index, -1)) for index, series in enumerate(model.series)]


def split_legend(area: Plot, position: str | None, entries: list[tuple[str, str]], look: TextLook) -> tuple[Plot, Plot | None]:
    if position is None:
        return area, None
    if position == "r":
        legend_width = min(area.width * LEGEND_SHARE, max(entry_width(name, look) for name, _ in entries) + EDGE)
        return Plot(area.left, area.top, area.width - legend_width, area.height), Plot(area.right - legend_width, area.top, legend_width, area.height)
    if position == "t":
        return Plot(area.left, area.top + LEGEND_ROW_HEIGHT, area.width, area.height - LEGEND_ROW_HEIGHT), Plot(area.left, area.top, area.width, LEGEND_ROW_HEIGHT)
    return Plot(area.left, area.top, area.width, area.height - LEGEND_ROW_HEIGHT), Plot(area.left, area.bottom - LEGEND_ROW_HEIGHT, area.width, LEGEND_ROW_HEIGHT)


def entry_width(name: str, look: TextLook) -> float:
    return look.size * SWATCH_SHARE + LABEL_GAP + text_width(name, look) + look.size


def legend_svg(entries: list[tuple[str, str]], area: Plot, position: str, look: TextLook) -> str:
    swatch = look.size * SWATCH_SHARE
    if position == "r":
        step = look.size * 2
        places = [(area.left + EDGE, area.top + area.height / 2 + (index - (len(entries) - 1) / 2) * step) for index in range(len(entries))]
    else:
        widths = [entry_width(name, look) for name, _ in entries]
        x = max(area.left, area.left + (area.width - sum(widths)) / 2)
        places = []
        for entry_size in widths:
            places.append((x, area.top + area.height / 2))
            x += entry_size
    parts = []
    for (name, color), (x, y) in zip(entries, places):
        parts.append(f'<rect x="{x:.1f}" y="{y - swatch / 2:.1f}" width="{swatch:.1f}" height="{swatch:.1f}" fill="{color}"/>')
        parts.append(text_svg(x + swatch + LABEL_GAP, y, name, look, "start"))
    return "".join(parts)


def nice_step(span: float) -> float:
    raw = span / MOST_GRID_LINES if span > 0 else 1.0
    magnitude = 10 ** math.floor(math.log10(raw))
    return next(step * magnitude for step in (1, 2, 2.5, 5, 10) if step * magnitude >= raw)


def value_scale(values: list[float], limits: tuple[float | None, float | None], major_unit: float | None) -> Scale:
    fixed_low, fixed_high = limits
    if fixed_low is not None and fixed_high is not None and fixed_high > fixed_low:
        return Scale(fixed_low, fixed_high, major_unit or nice_step(fixed_high - fixed_low))
    values = values or [0.0]
    low, high = min(0.0, min(values)), max(0.0, max(values))
    step = major_unit or nice_step(high - low)
    low_tick = math.floor(low / step) * step
    return Scale(low_tick, max(math.ceil(high / step) * step, low_tick + step), step)


def plotted_values(model: ChartModel, series_list: list[ChartSeries]) -> list[float]:
    if not model.stacked:
        return [value for series in series_list for value in series.values]
    totals = []
    for kind in dict.fromkeys(series.kind for series in series_list):
        group = [series for series in series_list if series.kind == kind]
        count = max(len(series.values) for series in group)
        totals += [sum(max(0.0, series.values[index]) for series in group if index < len(series.values)) for index in range(count)]
        totals += [sum(min(0.0, series.values[index]) for series in group if index < len(series.values)) for index in range(count)]
    return totals


def percent_shares(model: ChartModel) -> ChartModel:
    shared = []
    for series in model.series:
        group = [other for other in model.series if other.kind == series.kind]
        totals = [sum(abs(other.values[position]) for other in group if position < len(other.values)) for position in range(len(series.values))]
        shared.append(replace(series, values=tuple(value / total if total else 0.0 for value, total in zip(series.values, totals))))
    return replace(model, series=tuple(shared), stacked=True)


def scaled(value: float, scale: Scale, length: float) -> float:
    return (value - scale.low) / (scale.high - scale.low) * length


def axis_number(value: float, format_code: str | None) -> str:
    if format_code is None:
        return abbreviated_number(value)
    return displayed(value, format_code).text


def abbreviated_number(value: float) -> str:
    if abs(value) >= 1e8:
        return f"{value / 1e8:g}억"
    if abs(value) >= 1e4:
        return f"{value / 1e4:g}만"
    return f"{value:,.0f}" if value == int(value) else f"{value:g}"


def grouped_number(value: float) -> str:
    return f"{value:,.0f}" if value == int(value) else f"{value:,.2f}".rstrip("0")


def label_text(model: ChartModel, series: ChartSeries, position: int, label: PointLabel) -> str:
    if label.custom_text:
        return label.custom_text
    value = series.values[position] if position < len(series.values) else 0.0
    parts = []
    if label.show_category and position < len(model.categories):
        parts.append(str(model.categories[position]))
    if label.show_value:
        parts.append(grouped_number(value) if label.format_code is None else displayed(value, label.format_code).text)
    if label.show_percent:
        parts.append(displayed(share_of(model, series, position), percent_format(label.format_code)).text)
    return " ".join(part for part in parts if part)


def share_of(model: ChartModel, series: ChartSeries, position: int) -> float:
    if model.is_round:
        total = sum(abs(value) for value in series.values)
        return abs(series.values[position]) / total if total else 0.0
    total = sum(abs(other.values[position]) for other in model.series if other.kind == series.kind and position < len(other.values))
    return abs(series.values[position]) / total if total else 0.0


def percent_format(format_code: str | None) -> str:
    return format_code if format_code and "%" in format_code else PERCENT_FORMAT


def point_label(look: ChartLook, series: int, position: int) -> PointLabel | None:
    labels = look.label_of(series)
    label = labels.at(position) if labels is not None else None
    return label if label is not None and label.shown else None


def category_order(count: int, horizontal: bool, look: ChartLook) -> list[int]:
    order = list(range(count))
    return order[::-1] if look.reversed_categories != horizontal else order


def axis_chart_svg(model: ChartModel, plot: Plot, look: ChartLook) -> str:
    if not model.series or not model.categories:
        return ""
    horizontal = model.is_horizontal
    drawn = percent_shares(model) if model.percent_stacked else model
    axis_format = PERCENT_FORMAT if model.percent_stacked else look.axis_format
    bars = [(index, series) for index, series in enumerate(drawn.series) if series.kind in BAR_KINDS]
    lines = [(index, series) for index, series in enumerate(drawn.series) if series.kind in LINE_KINDS]
    primary = [series for _, series in bars] or [series for _, series in lines]
    scale = value_scale(plotted_values(drawn, primary), look.value_limits, look.major_unit)
    on_secondary = drawn.secondary_axis and bool(bars) and bool(lines)
    line_scale = value_scale(plotted_values(drawn, [series for _, series in lines]), look.secondary_limits, None) if on_secondary else scale
    area = axis_area(drawn, plot, look, horizontal, on_secondary)
    order = category_order(len(drawn.categories), horizontal, look)
    parts = [
        grid_svg(area, scale, horizontal, look, axis_format),
        category_labels_svg([str(drawn.categories[position]) for position in order], area, horizontal, look.text),
        bars_svg(model, drawn, bars, order, area, scale, look, horizontal),
        axis_line_svg(area, scale, horizontal, look.axis_line),
        lines_svg(model, drawn, lines, order, area, line_scale, look),
    ]
    if on_secondary and look.secondary_axis_shown:
        parts.append(right_axis_svg(area, line_scale, look.text, look.axis_format))
    return "".join(parts)


def axis_area(model: ChartModel, plot: Plot, look: ChartLook, horizontal: bool, on_secondary: bool) -> Plot:
    value_width = AXIS_LABEL_WIDTH if look.value_axis_shown and not horizontal else 0
    category_width = category_axis_width(model.categories, look.text) if horizontal else 0
    right_width = AXIS_LABEL_WIDTH if on_secondary and look.secondary_axis_shown else end_label_room(look) if horizontal else 0
    bottom = CATEGORY_LABEL_HEIGHT if not horizontal or look.value_axis_shown else 0
    top = look.text.size / 2
    return Plot(plot.left + value_width + category_width, plot.top + top, plot.width - value_width - category_width - right_width, plot.height - bottom - top)


def end_label_room(look: ChartLook) -> float:
    return look.text.size * END_LABEL_SHARE if look.value_axis_shown else 0


def category_axis_width(categories: tuple[str, ...], look: TextLook) -> float:
    return min(160.0, LABEL_GAP * 3 + max((text_width(str(category), look) for category in categories), default=look.size * 2))


def grid_svg(area: Plot, scale: Scale, horizontal: bool, look: ChartLook, axis_format: str | None) -> str:
    parts = []
    steps = max(1, round((scale.high - scale.low) / scale.step))
    for step in range(steps + 1):
        label = axis_number(scale.low + scale.step * step, axis_format)
        if horizontal:
            x = area.left + area.width * step / steps
            if look.gridlines:
                parts.append(f'<line x1="{x:.1f}" y1="{area.top:.1f}" x2="{x:.1f}" y2="{area.bottom:.1f}" stroke="{look.gridlines}"/>')
            if look.value_axis_shown:
                parts.append(text_svg(x, area.bottom + CATEGORY_LABEL_HEIGHT / 2, label, look.text))
        else:
            y = area.bottom - area.height * step / steps
            if look.gridlines:
                parts.append(f'<line x1="{area.left:.1f}" y1="{y:.1f}" x2="{area.right:.1f}" y2="{y:.1f}" stroke="{look.gridlines}"/>')
            if look.value_axis_shown:
                parts.append(text_svg(area.left - LABEL_GAP, y, label, look.text, "end"))
    return "".join(parts)


def right_axis_svg(area: Plot, scale: Scale, look: TextLook, axis_format: str | None) -> str:
    steps = max(1, round((scale.high - scale.low) / scale.step))
    return "".join(text_svg(area.right + LABEL_GAP, area.bottom - area.height * step / steps, axis_number(scale.low + scale.step * step, axis_format), look, "start") for step in range(steps + 1))


def axis_line_svg(area: Plot, scale: Scale, horizontal: bool, color: str | None) -> str:
    if color is None:
        return ""
    zero = max(scale.low, min(0.0, scale.high))
    if horizontal:
        x = area.left + scaled(zero, scale, area.width)
        return f'<line x1="{x:.1f}" y1="{area.top:.1f}" x2="{x:.1f}" y2="{area.bottom:.1f}" stroke="{color}" stroke-width="1.5"/>'
    y = area.bottom - scaled(zero, scale, area.height)
    return f'<line x1="{area.left:.1f}" y1="{y:.1f}" x2="{area.right:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="1.5"/>'


def category_labels_svg(categories: list[str], area: Plot, horizontal: bool, look: TextLook) -> str:
    count = max(len(categories), 1)
    if horizontal:
        return "".join(text_svg(area.left - LABEL_GAP, area.top + area.height * (index + 0.5) / count, category, look, "end") for index, category in enumerate(categories))
    return "".join(text_svg(area.left + area.width * (index + 0.5) / count, area.bottom + CATEGORY_LABEL_HEIGHT / 2, category, look) for index, category in enumerate(categories))


def bars_svg(model: ChartModel, drawn: ChartModel, bars: list[tuple[int, ChartSeries]], order: list[int], area: Plot, scale: Scale, look: ChartLook, horizontal: bool) -> str:
    if not bars:
        return ""
    band = (area.height if horizontal else area.width) / max(len(order), 1)
    share = 1 / (1 + look.gap_width / 100)
    thickness = band * share / (1 if drawn.stacked else len(bars))
    length_axis = area.width if horizontal else area.height
    offsets = [0.0] * len(drawn.categories)
    shapes, labels = [], []
    for lane, (index, series) in enumerate(bars):
        for slot, position in enumerate(order):
            value = series.values[position] if position < len(series.values) else 0.0
            base = offsets[position] if drawn.stacked else 0.0
            start, end = scaled(base, scale, length_axis), scaled(base + value, scale, length_axis)
            across = band * slot + band * (1 - share) / 2 + (0 if drawn.stacked else thickness * lane)
            shapes.append(bar_rectangle(area, horizontal, across, thickness, min(start, end), abs(end - start), look.color_of(index, position)))
            label = point_label(look, index, position)
            if label is not None:
                centered = label.is_inside or (not label.position and drawn.stacked)
                labels.append(bar_label_svg(label_text(model, model.series[index], position, label), label, centered, area, horizontal, (across + thickness / 2, start, end)))
            if drawn.stacked:
                offsets[position] += value
    return "".join(shapes + labels)


def bar_rectangle(area: Plot, horizontal: bool, across: float, thickness: float, start: float, length: float, color: str) -> str:
    if horizontal:
        return f'<rect x="{area.left + start:.1f}" y="{area.top + across:.1f}" width="{length:.1f}" height="{thickness:.1f}" fill="{color}"/>'
    return f'<rect x="{area.left + across:.1f}" y="{area.bottom - start - length:.1f}" width="{thickness:.1f}" height="{length:.1f}" fill="{color}"/>'


def bar_label_svg(text: str, label: PointLabel, centered: bool, area: Plot, horizontal: bool, span: tuple[float, float, float]) -> str:
    middle, start, end = span
    along = (start + end) / 2 if centered else max(start, end)
    if horizontal:
        return text_svg(area.left + along + (0 if centered else LABEL_GAP), area.top + middle, text, label.text, "middle" if centered else "start")
    return text_svg(area.left + middle, area.bottom - along - (0 if centered else label.text.size / 2 + LABEL_GAP), text, label.text)


def lines_svg(model: ChartModel, drawn: ChartModel, lines: list[tuple[int, ChartSeries]], order: list[int], area: Plot, scale: Scale, look: ChartLook) -> str:
    count = max(len(order), 1)
    xs = [area.left + area.width * (slot + 0.5) / count for slot in range(len(order))]
    floors = {kind: [0.0] * len(drawn.categories) for kind in LINE_KINDS}
    shapes, labels = [], []
    for index, series in lines:
        values = [series.values[position] if position < len(series.values) else 0.0 for position in order]
        bases = [floors[series.kind][position] for position in order] if drawn.stacked else [0.0] * len(order)
        tops = [base + value for base, value in zip(bases, values)]
        if drawn.stacked:
            for position, top in zip(order, tops):
                floors[series.kind][position] = top
        points = [(x, area.bottom - scaled(top, scale, area.height)) for x, top in zip(xs, tops)]
        color = look.color_of(index, -1)
        if series.kind == "area":
            floor = [(x, area.bottom - scaled(max(base, scale.low), scale, area.height)) for x, base in zip(xs, bases)]
            opacity = "" if drawn.stacked else f' fill-opacity="{AREA_OPACITY}"'
            shapes.append(f'<polygon points="{point_list(points + floor[::-1])}" fill="{color}"{opacity}/>')
        else:
            shapes.append(f'<polyline points="{point_list(points)}" fill="none" stroke="{color}" stroke-width="{LINE_WIDTH}"/>')
            shapes.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{MARKER_RADIUS}" fill="{look.color_of(index, position)}"/>' for (x, y), position in zip(points, order))
        labels.extend(line_label_svg(model, index, position, point, look) for point, position in zip(points, order))
    return "".join(shapes + labels)


def point_list(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def line_label_svg(model: ChartModel, index: int, position: int, point: tuple[float, float], look: ChartLook) -> str:
    label = point_label(look, index, position)
    if label is None:
        return ""
    offset = label.text.size / 2 + LABEL_GAP
    x, y = point
    return text_svg(x, y + offset if label.position == BELOW_POSITION else y - offset, label_text(model, model.series[index], position, label), label.text)


def scatter_svg(model: ChartModel, plot: Plot, look: ChartLook) -> str:
    series = model.series[0]
    xs = list(series.x_values) or [float(number) for number in range(1, len(series.values) + 1)]
    ys = list(series.values)
    area = Plot(plot.left + AXIS_LABEL_WIDTH, plot.top, plot.width - AXIS_LABEL_WIDTH - end_label_room(look), plot.height - CATEGORY_LABEL_HEIGHT)
    across = value_scale(xs, look.horizontal_limits, None)
    upward = value_scale(ys, look.value_limits, look.major_unit)
    parts = [grid_svg(area, upward, False, look, look.axis_format), grid_svg(area, across, True, look, look.axis_format)]
    for position, (x, y) in enumerate(zip(xs, ys)):
        center = (area.left + scaled(x, across, area.width), area.bottom - scaled(y, upward, area.height))
        parts.append(f'<circle cx="{center[0]:.1f}" cy="{center[1]:.1f}" r="{SCATTER_RADIUS}" fill="{look.color_of(0, position)}"/>')
        parts.append(point_name_svg(model, position, center, look))
    return "".join(parts)


def point_name_svg(model: ChartModel, position: int, center: tuple[float, float], look: ChartLook) -> str:
    label = point_label(look, 0, position)
    if label is None:
        return ""
    on_left = label.position == LEFT_POSITION
    x = center[0] - LABEL_GAP * 2 if on_left else center[0] + LABEL_GAP * 2
    return text_svg(x, center[1], label_text(model, model.series[0], position, label), label.text, "end" if on_left else "start")


def round_svg(model: ChartModel, plot: Plot, look: ChartLook) -> str:
    series = model.series[0]
    values = [max(value, 0.0) for value in series.values]
    total = sum(values)
    if total <= 0:
        return ""
    labels = [point_label(look, 0, position) for position in range(len(values))]
    outside = any(label is not None and label.position == OUTSIDE_POSITION for label in labels)
    radius = max(EDGE, min(plot.width, plot.height) / 2 * (OUTSIDE_LABEL_ROOM if outside else 1))
    hole = radius * look.hole_percent / 100 if series.kind == "doughnut" else 0.0
    center = (plot.left + plot.width / 2, plot.top + plot.height / 2)
    slices, texts, angle = [], [], -math.pi / 2
    for position, value in enumerate(values):
        sweep = 2 * math.pi * value / total
        slices.append(slice_path(center, radius, hole, angle, sweep, look.slice_color(position)))
        label = labels[position]
        if label is not None and value:
            texts.append(slice_label_svg(label_text(model, series, position, label), label, center, radius, hole, angle + sweep / 2, sweep))
        angle += sweep
    return "".join(slices + texts)


def slice_label_svg(text: str, label: PointLabel, center: tuple[float, float], radius: float, hole: float, middle: float, sweep: float) -> str:
    if label.position == OUTSIDE_POSITION:
        distance = radius + LABEL_GAP * 2
        anchor = "start" if math.cos(middle) >= 0 else "end"
        return text_svg(center[0] + distance * math.cos(middle), center[1] + distance * math.sin(middle), text, label.text, anchor)
    if sweep <= SMALLEST_LABELLED_SWEEP:
        return ""
    distance = (radius + hole) / 2 if hole else radius * PIE_LABEL_RADIUS_SHARE
    return text_svg(center[0] + distance * math.cos(middle), center[1] + distance * math.sin(middle), text, label.text)


def arc_point(center: tuple[float, float], radius: float, angle: float) -> str:
    return f"{center[0] + radius * math.cos(angle):.1f},{center[1] + radius * math.sin(angle):.1f}"


def slice_path(center: tuple[float, float], radius: float, hole: float, start: float, sweep: float, color: str) -> str:
    full = sweep >= 2 * math.pi - 1e-6
    end = start + (2 * math.pi - 1e-4 if full else sweep)
    large = 1 if end - start > math.pi else 0
    outer = f"{arc_point(center, radius, start)} A{radius:.1f},{radius:.1f} 0 {large} 1 {arc_point(center, radius, end)}"
    if hole <= 0:
        path = f"M{center[0]:.1f},{center[1]:.1f} L{outer} Z"
    else:
        path = f"M{outer} L{arc_point(center, hole, end)} A{hole:.1f},{hole:.1f} 0 {large} 0 {arc_point(center, hole, start)} Z"
    return f'<path d="{path}" fill="{color}" stroke="{SLICE_STROKE}" stroke-width="1.5"/>'
