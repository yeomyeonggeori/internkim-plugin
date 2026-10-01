from __future__ import annotations

import base64
from dataclasses import dataclass

from openpyxl.utils import range_boundaries

from chart_svg import ChartModel, ChartSeries, chart_svg
from office_preview import emu_to_pixels, pixels, style_attribute
from preview_fonts import KOREAN_FALLBACK_FAMILY


ACCENT_SLOTS = range(4, 10)
ROUND_KINDS = {"PieChart": "pie", "PieChart3D": "pie", "ProjectedPieChart": "pie", "DoughnutChart": "doughnut"}


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    width: float
    height: float


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


def chart_html(chart, box: Box, values_workbook, palette: tuple, preview) -> str:
    model = chart_model(chart, values_workbook, preview)
    colors = round_colors(palette) if model.is_round else tuple(series_color(item, palette, index) for index, item in enumerate(chart_items(chart)))
    return f"<div{style_attribute(absolute(box))}>{chart_svg(model, box.width, box.height, KOREAN_FALLBACK_FAMILY, colors or round_colors(palette))}</div>"


def chart_plots(chart) -> list:
    return list(getattr(chart, "_charts", None) or [chart])


def chart_items(chart) -> list:
    return [item for plot in chart_plots(chart) for item in plot.series]


def series_kind(plot, preview) -> str:
    kind = type(plot).__name__
    if kind == "BarChart" or kind == "BarChart3D":
        return "bar" if plot.barDir == "bar" else "column"
    if kind in ROUND_KINDS:
        return ROUND_KINDS[kind]
    if kind in ("AreaChart", "AreaChart3D"):
        return "area"
    if kind not in ("LineChart", "LineChart3D"):
        preview.approximate(f"{kind} drawn as lines over its categories")
    return "line"


def is_stacked(plot) -> bool:
    return getattr(plot, "grouping", None) in ("stacked", "percentStacked")


def axis_identifier(plot) -> int | None:
    axis = getattr(plot, "y_axis", None)
    return getattr(axis, "axId", None)


def chart_model(chart, values_workbook, preview) -> ChartModel:
    plots = chart_plots(chart)
    series = []
    for plot in plots:
        kind = series_kind(plot, preview)
        for item in plot.series:
            reference = item.val.numRef.f if item.val is not None and item.val.numRef is not None else None
            values = tuple(float(value) if isinstance(value, (int, float)) else 0.0 for value in reference_values(reference, values_workbook))
            series.append(ChartSeries(series_name(item, values_workbook, len(series)), values, kind))
    secondary = len({axis_identifier(plot) for plot in plots}) > 1
    return ChartModel(tuple(chart_categories(chart, values_workbook)), tuple(series), chart_title(chart), any(is_stacked(plot) for plot in plots), chart.legend is not None, secondary)


def series_name(item, values_workbook, index: int) -> str:
    name_reference = item.tx.strRef.f if item.tx is not None and item.tx.strRef is not None else None
    names = reference_values(name_reference, values_workbook)
    return str(names[0]) if names else (item.tx.v if item.tx is not None and item.tx.v else f"계열 {index + 1}")


def round_colors(palette: tuple) -> tuple:
    return tuple(f"#{palette[slot].lower()}" for slot in ACCENT_SLOTS)


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


def series_color(item, palette: tuple, index: int) -> str:
    properties = getattr(item, "graphicalProperties", None) or getattr(item, "spPr", None)
    fill = getattr(properties, "solidFill", None) if properties is not None else None
    rgb = getattr(fill, "srgbClr", None) if fill is not None else None
    value = getattr(rgb, "val", None) if rgb is not None else None
    if value:
        return f"#{value.lower()}"
    line = getattr(properties, "line", None) if properties is not None else None
    line_fill = getattr(line, "solidFill", None) if line is not None else None
    line_rgb = getattr(getattr(line_fill, "srgbClr", None), "val", None) if line_fill is not None else None
    if line_rgb:
        return f"#{line_rgb.lower()}"
    slots = list(ACCENT_SLOTS)
    return f"#{palette[slots[index % len(slots)]].lower()}"


def chart_categories(chart, values_workbook) -> list[str]:
    for item in chart_items(chart):
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
