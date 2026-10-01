from __future__ import annotations

from dataclasses import dataclass

from openpyxl.utils import range_boundaries

from chart_svg import ChartModel, ChartSeries, chart_svg
from office_preview import data_uri, emu_to_pixels, pixels, style_attribute
from preview_fonts import KOREAN_FALLBACK_FAMILY


ACCENT_SLOTS = range(4, 10)
ROUND_KINDS = {"PieChart": "pie", "PieChart3D": "pie", "ProjectedPieChart": "pie", "DoughnutChart": "doughnut"}


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    width: float
    height: float


def drawing_box(anchor, frame, columns: list[int], body_rows: list[int], scale: float, image=None) -> Box | None:
    start = getattr(anchor, "_from", None)
    if start is None or not columns or not body_rows:
        return None
    left = axis_position(start.col + 1, columns[0], frame.columns, frame.widths) + emu_to_pixels(start.colOff or 0)
    top = axis_position(start.row + 1, body_rows[0], frame.rows, frame.heights) + emu_to_pixels(start.rowOff or 0)
    end = getattr(anchor, "to", None)
    extent = getattr(anchor, "ext", None)
    if end is not None:
        width = axis_position(end.col + 1, columns[0], frame.columns, frame.widths) + emu_to_pixels(end.colOff or 0) - left
        height = axis_position(end.row + 1, body_rows[0], frame.rows, frame.heights) + emu_to_pixels(end.rowOff or 0) - top
    elif extent is not None:
        width, height = emu_to_pixels(extent.width), emu_to_pixels(extent.height)
    else:
        width, height = (image.width, image.height) if image is not None else (480, 288)
    box = Box(left * scale, top * scale, max(width, 1) * scale, max(height, 1) * scale)
    page_width = sum(frame.widths[column] for column in columns) * scale
    page_height = sum(frame.heights[row] for row in body_rows) * scale
    return box if overlaps(box, page_width, page_height) else None


def axis_position(target: int, first_on_page: int, frame_items: list[int], sizes: dict) -> float:
    if target >= first_on_page:
        return sum(sizes[item] for item in frame_items if first_on_page <= item < target)
    return -sum(sizes[item] for item in frame_items if target <= item < first_on_page)


def overlaps(box: Box, page_width: float, page_height: float) -> bool:
    return box.left < page_width and box.left + box.width > 0 and box.top < page_height and box.top + box.height > 0


def is_whole(box: Box, page_width: float, page_height: float) -> bool:
    return box.left >= -0.5 and box.top >= -0.5 and box.left + box.width <= page_width + 0.5 and box.top + box.height <= page_height + 0.5


def image_html(image, box: Box) -> str:
    data = image._data()
    kind = (getattr(image, "format", None) or "png").lower()
    return f'<img src="{data_uri(f"image/{kind}", data)}"{style_attribute(absolute(box))}>'


def absolute(box: Box) -> dict:
    return {"position": "absolute", "left": pixels(box.left), "top": pixels(box.top), "width": pixels(box.width), "height": pixels(box.height)}


def chart_html(chart, box: Box, values_workbook, palette: tuple, preview) -> str:
    model = chart_model(chart, values_workbook, preview)
    colors = point_colors(chart_items(chart), palette) if model.is_round else tuple(series_color(item, palette, index) for index, item in enumerate(chart_items(chart)))
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


def point_colors(items: list, palette: tuple) -> tuple:
    points = list(getattr(items[0], "dPt", None) or []) if items else []
    painted = {point.idx: solid_color(point.graphicalProperties) for point in points}
    if not any(painted.values()):
        return round_colors(palette)
    defaults = round_colors(palette)
    count = max(painted) + 1
    return tuple(painted.get(index) or defaults[index % len(defaults)] for index in range(count))


def solid_color(properties) -> str | None:
    fill = getattr(properties, "solidFill", None) if properties is not None else None
    rgb = getattr(fill, "srgbClr", None) if fill is not None else None
    value = rgb if isinstance(rgb, str) else getattr(rgb, "val", None)
    return f"#{value.lower()}" if value else None


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
    color = solid_color(properties) or solid_color(getattr(properties, "line", None))
    if color:
        return color
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


def chart_kind(chart) -> str:
    return "+".join(dict.fromkeys(series_kind_name(plot) for plot in chart_plots(chart)))


def series_kind_name(plot) -> str:
    kind = type(plot).__name__
    if kind.startswith("BarChart"):
        return "bar" if plot.barDir == "bar" else "column"
    return ROUND_KINDS.get(kind) or kind.removesuffix("3D").removesuffix("Chart").lower()


def chart_title(chart) -> str:
    title = chart.title
    if title is None or title.tx is None or title.tx.rich is None:
        return ""
    return "".join(run.t or "" for paragraph in title.tx.rich.p for run in (paragraph.r or []))
