from __future__ import annotations

import base64
from dataclasses import dataclass
import math

from openpyxl.utils import range_boundaries

from office_preview import emu_to_pixels, escaped, pixels, style_attribute
from preview_fonts import KOREAN_FALLBACK_FAMILY


ACCENT_SLOTS = range(4, 10)
TITLE_HEIGHT = 24
AXIS_LABEL_HEIGHT = 18
LEGEND_HEIGHT = 18
PLOT_PADDING = 10


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    width: float
    height: float


@dataclass
class Series:
    name: str
    values: list[float]
    color: str


def drawing_box(anchor, frame, columns: list[int], rows: list[int], scale: float, image=None) -> Box | None:
    start = getattr(anchor, "_from", None)
    if start is None or start.col + 1 not in columns or start.row + 1 not in rows:
        return None
    left = offset(columns, frame.widths, start.col + 1) + emu_to_pixels(start.colOff or 0)
    top = offset(rows, frame.heights, start.row + 1) + emu_to_pixels(start.rowOff or 0)
    end = getattr(anchor, "to", None)
    extent = getattr(anchor, "ext", None)
    if end is not None:
        width = offset(columns, frame.widths, end.col + 1) + emu_to_pixels(end.colOff or 0) - left
        height = offset(rows, frame.heights, end.row + 1) + emu_to_pixels(end.rowOff or 0) - top
    elif extent is not None:
        width, height = emu_to_pixels(extent.width), emu_to_pixels(extent.height)
    else:
        width, height = (image.width, image.height) if image is not None else (480, 288)
    return Box(left * scale, top * scale, max(width, 1) * scale, max(height, 1) * scale)


def offset(items: list[int], sizes: dict, target: int) -> float:
    return sum(sizes[item] for item in items if item < target)


def image_html(image, box: Box) -> str:
    data = image._data()
    kind = (getattr(image, "format", None) or "png").lower()
    return f'<img src="data:image/{kind};base64,{base64.b64encode(data).decode("ascii")}"{style_attribute(absolute(box))}>'


def absolute(box: Box) -> dict:
    return {"position": "absolute", "left": pixels(box.left), "top": pixels(box.top), "width": pixels(box.width), "height": pixels(box.height)}


def chart_html(chart, box: Box, values_workbook, palette: tuple) -> str:
    series = chart_series(chart, values_workbook, palette)
    categories = chart_categories(chart, values_workbook)
    title = chart_title(chart)
    kind = type(chart).__name__
    body = pie_svg(series, categories, box) if kind in ("PieChart", "DoughnutChart", "PieChart3D") else axis_svg(kind, series, categories, box, title)
    heading = f'<text x="{box.width / 2:.1f}" y="18" text-anchor="middle" font-size="14" font-weight="700" fill="#333333">{escaped(title)}</text>' if title else ""
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{box.width:.1f}" height="{box.height:.1f}" viewBox="0 0 {box.width:.1f} {box.height:.1f}" font-family="{KOREAN_FALLBACK_FAMILY}"><rect width="100%" height="100%" fill="#ffffff" stroke="#d9d9d9"/>{heading}{body}</svg>'
    return f"<div{style_attribute(absolute(box))}>{svg}</div>"


def reference_values(reference: str | None, values_workbook) -> list:
    if not reference:
        return []
    sheet_name, _, cells = reference.rpartition("!")
    sheet_name = sheet_name.strip("'") or values_workbook.active.title
    if sheet_name not in values_workbook.sheetnames:
        return []
    worksheet = values_workbook[sheet_name]
    min_column, min_row, max_column, max_row = range_boundaries(cells.replace("$", ""))
    return [worksheet.cell(row=row, column=column).value for row in range(min_row, max_row + 1) for column in range(min_column, max_column + 1)]


def chart_series(chart, values_workbook, palette: tuple) -> list[Series]:
    found = []
    for index, item in enumerate(chart.series):
        reference = item.val.numRef.f if item.val is not None and item.val.numRef is not None else None
        values = [float(value) if isinstance(value, (int, float)) else 0.0 for value in reference_values(reference, values_workbook)]
        name_reference = item.tx.strRef.f if item.tx is not None and item.tx.strRef is not None else None
        names = reference_values(name_reference, values_workbook)
        name = str(names[0]) if names else (item.tx.v if item.tx is not None and item.tx.v else f"계열 {index + 1}")
        found.append(Series(name, values, series_color(item, palette, index)))
    return found


def series_color(item, palette: tuple, index: int) -> str:
    properties = getattr(item, "graphicalProperties", None) or getattr(item, "spPr", None)
    fill = getattr(properties, "solidFill", None) if properties is not None else None
    rgb = getattr(fill, "srgbClr", None) if fill is not None else None
    value = getattr(rgb, "val", None) if rgb is not None else None
    if value:
        return f"#{value.lower()}"
    slots = list(ACCENT_SLOTS)
    return f"#{palette[slots[index % len(slots)]].lower()}"


def chart_categories(chart, values_workbook) -> list[str]:
    for item in chart.series:
        source = item.cat
        if source is None:
            continue
        reference = source.strRef.f if source.strRef is not None else source.numRef.f if source.numRef is not None else None
        values = reference_values(reference, values_workbook)
        if values:
            return ["" if value is None else str(value) for value in values]
    return []


def chart_title(chart) -> str:
    title = chart.title
    if title is None or title.tx is None or title.tx.rich is None:
        return ""
    return "".join(run.t or "" for paragraph in title.tx.rich.p for run in (paragraph.r or []))


def axis_svg(kind: str, series: list[Series], categories: list[str], box: Box, title: str) -> str:
    top = (TITLE_HEIGHT if title else 0) + PLOT_PADDING
    bottom = box.height - AXIS_LABEL_HEIGHT - (LEGEND_HEIGHT if len(series) > 1 else 0) - PLOT_PADDING
    left, right = 44.0, box.width - PLOT_PADDING
    values = [value for item in series for value in item.values] or [0.0]
    low, high = min(0.0, min(values)), max(0.0, max(values))
    high = high if high > low else low + 1
    count = max((len(item.values) for item in series), default=0)
    parts = [axis_lines(left, top, right, bottom, low, high)]
    if kind == "BarChart":
        parts.append(bars(series, count, left, top, right, bottom, low, high))
    else:
        parts.append(lines(series, count, left, top, right, bottom, low, high, kind == "AreaChart"))
    parts.append(category_labels(categories[:count], left, right, bottom, count))
    if len(series) > 1:
        parts.append(legend(series, box))
    return "".join(parts)


def scaled(value: float, low: float, high: float, start: float, end: float) -> float:
    return start + (value - low) / (high - low) * (end - start)


def axis_lines(left: float, top: float, right: float, bottom: float, low: float, high: float) -> str:
    ticks = []
    for step in range(5):
        value = low + (high - low) * step / 4
        y = scaled(value, low, high, bottom, top)
        ticks.append(f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{right:.1f}" y2="{y:.1f}" stroke="#e6e6e6"/>')
        ticks.append(f'<text x="{left - 4:.1f}" y="{y + 4:.1f}" text-anchor="end" font-size="10" fill="#595959">{escaped(short_number(value))}</text>')
    zero = scaled(0.0, low, high, bottom, top)
    return "".join(ticks) + f'<line x1="{left:.1f}" y1="{zero:.1f}" x2="{right:.1f}" y2="{zero:.1f}" stroke="#8c8c8c"/>'


def short_number(value: float) -> str:
    if abs(value) >= 1e8:
        return f"{value / 1e8:.1f}억"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.0f}만"
    return f"{value:.0f}" if value == int(value) else f"{value:.1f}"


def bars(series: list[Series], count: int, left: float, top: float, right: float, bottom: float, low: float, high: float) -> str:
    if count == 0 or not series:
        return ""
    slot = (right - left) / count
    width = slot * 0.7 / len(series)
    zero = scaled(0.0, low, high, bottom, top)
    shapes = []
    for series_index, item in enumerate(series):
        for index, value in enumerate(item.values):
            x = left + slot * index + slot * 0.15 + width * series_index
            y = scaled(value, low, high, bottom, top)
            shapes.append(f'<rect x="{x:.1f}" y="{min(y, zero):.1f}" width="{width:.1f}" height="{abs(zero - y):.1f}" fill="{item.color}"/>')
    return "".join(shapes)


def lines(series: list[Series], count: int, left: float, top: float, right: float, bottom: float, low: float, high: float, filled: bool) -> str:
    if count == 0:
        return ""
    slot = (right - left) / count
    shapes = []
    for item in series:
        points = [(left + slot * (index + 0.5), scaled(value, low, high, bottom, top)) for index, value in enumerate(item.values)]
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        if filled and points:
            zero = scaled(0.0, low, high, bottom, top)
            shapes.append(f'<polygon points="{points[0][0]:.1f},{zero:.1f} {path} {points[-1][0]:.1f},{zero:.1f}" fill="{item.color}" fill-opacity="0.5"/>')
        shapes.append(f'<polyline points="{path}" fill="none" stroke="{item.color}" stroke-width="2"/>')
    return "".join(shapes)


def category_labels(categories: list[str], left: float, right: float, bottom: float, count: int) -> str:
    if count == 0:
        return ""
    slot = (right - left) / count
    return "".join(f'<text x="{left + slot * (index + 0.5):.1f}" y="{bottom + 14:.1f}" text-anchor="middle" font-size="10" fill="#595959">{escaped(label)}</text>' for index, label in enumerate(categories))


def legend(series: list[Series], box: Box) -> str:
    y = box.height - 8
    items, x = [], 12.0
    for item in series:
        items.append(f'<rect x="{x:.1f}" y="{y - 8:.1f}" width="10" height="10" fill="{item.color}"/><text x="{x + 14:.1f}" y="{y + 1:.1f}" font-size="10" fill="#404040">{escaped(item.name)}</text>')
        x += 24 + 7 * len(item.name)
    return "".join(items)


def pie_svg(series: list[Series], categories: list[str], box: Box) -> str:
    if not series or not any(series[0].values):
        return ""
    values = series[0].values
    total = sum(abs(value) for value in values) or 1
    radius = min(box.width, box.height) / 2 - 30
    center_x, center_y = box.width / 2, box.height / 2 + 8
    slices, angle = [], -math.pi / 2
    colors = ["#4472c4", "#ed7d31", "#a5a5a5", "#ffc000", "#5b9bd5", "#70ad47"]
    for index, value in enumerate(values):
        sweep = 2 * math.pi * abs(value) / total
        end = angle + sweep
        large = 1 if sweep > math.pi else 0
        start_point = (center_x + radius * math.cos(angle), center_y + radius * math.sin(angle))
        end_point = (center_x + radius * math.cos(end), center_y + radius * math.sin(end))
        slices.append(f'<path d="M{center_x:.1f},{center_y:.1f} L{start_point[0]:.1f},{start_point[1]:.1f} A{radius:.1f},{radius:.1f} 0 {large} 1 {end_point[0]:.1f},{end_point[1]:.1f} Z" fill="{colors[index % len(colors)]}" stroke="#ffffff"/>')
        middle = angle + sweep / 2
        label = categories[index] if index < len(categories) else ""
        slices.append(f'<text x="{center_x + radius * 0.65 * math.cos(middle):.1f}" y="{center_y + radius * 0.65 * math.sin(middle):.1f}" text-anchor="middle" font-size="10" fill="#ffffff">{escaped(label)}</text>')
        angle = end
    return "".join(slices)
