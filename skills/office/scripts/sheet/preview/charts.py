from __future__ import annotations

from dataclasses import dataclass, replace

from openpyxl.utils import range_boundaries

from charts.kinds import PERCENT_GROUPING, STACKED_GROUPINGS, plot_kind
from charts.look import LABEL_FLAGS, ChartLook, document_look
from charts.svg import ChartModel, ChartSeries, chart_svg
from fonts.preview import DEFAULT_FAMILY
from render.office_preview import data_uri, pixels, style_attribute
from core.units import emu_to_pixels
from core.office_theme import ACCENT_SLOTS, THEME_SLOTS


ACCENT_POSITIONS = tuple(THEME_SLOTS.index(slot) for slot in ACCENT_SLOTS)
VISIBLE_PIXELS = 0.5
DRAWN_PLOT_KINDS = ("column", "bar", "line", "area", "pie", "doughnut", "scatter")


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
    return (
        box.left < page_width - VISIBLE_PIXELS
        and box.left + box.width > VISIBLE_PIXELS
        and box.top < page_height - VISIBLE_PIXELS
        and box.top + box.height > VISIBLE_PIXELS
    )


def is_whole(box: Box, page_width: float, page_height: float) -> bool:
    return (
        box.left >= -VISIBLE_PIXELS
        and box.top >= -VISIBLE_PIXELS
        and box.left + box.width <= page_width + VISIBLE_PIXELS
        and box.top + box.height <= page_height + VISIBLE_PIXELS
    )


def image_html(image, box: Box) -> str:
    data = image._data()
    kind = (getattr(image, "format", None) or "png").lower()
    return f'<img src="{data_uri(f"image/{kind}", data)}"{style_attribute(absolute(box))}>'


def absolute(box: Box) -> dict:
    return {"position": "absolute", "left": pixels(box.left), "top": pixels(box.top), "width": pixels(box.width), "height": pixels(box.height)}


def chart_html(chart, box: Box, values_workbook, palette: tuple, preview) -> str:
    model = chart_model(chart, values_workbook, preview)
    return f"<div{style_attribute(absolute(box))}>{chart_svg(model, box.width, box.height, chart_look(chart, model, palette), DEFAULT_FAMILY)}</div>"


def chart_look(chart, model: ChartModel, palette: tuple) -> ChartLook:
    colors = point_colors(chart_items(chart), palette) if model.is_round else tuple(series_color(item, palette, index) for index, item in enumerate(chart_items(chart)))
    look = document_look(colors or round_colors(palette), len(model.series), model.is_round, model.stacked, chart.legend is not None, label_mode(chart_plots(chart)))
    gap_width = next((plot.gapWidth for plot in chart_plots(chart) if getattr(plot, "gapWidth", None) is not None), None)
    return replace(look, gap_width=gap_width) if gap_width is not None else look


def chart_plots(chart) -> list:
    return list(getattr(chart, "_charts", None) or [chart])


def chart_items(chart) -> list:
    return [item for plot in chart_plots(chart) for item in plot.series]


def series_kind(plot, preview) -> str:
    kind = plot_series_kind(plot)
    if kind in DRAWN_PLOT_KINDS:
        return kind
    preview.approximate(f"{plot.tagname} drawn as lines over its categories")
    return "line"


def plot_series_kind(plot) -> str:
    return plot_kind(plot.tagname, getattr(plot, "barDir", None)) or plot.tagname


def is_stacked(plot) -> bool:
    return getattr(plot, "grouping", None) in STACKED_GROUPINGS


def axis_identifier(plot) -> int | None:
    axis = getattr(plot, "y_axis", None)
    return getattr(axis, "axId", None)


def chart_model(chart, values_workbook, preview) -> ChartModel:
    plots = chart_plots(chart)
    series = []
    for plot in plots:
        kind = series_kind(plot, preview)
        for item in plot.series:
            values = numbers(getattr(item, "val", None) or getattr(item, "yVal", None), values_workbook)
            across = tuple(0.0 if value is None else value for value in numbers(getattr(item, "xVal", None), values_workbook))
            series.append(ChartSeries(series_name(item, values_workbook, len(series)), values, kind, across))
    return ChartModel(
        categories=tuple(chart_categories(chart, values_workbook)),
        series=tuple(series),
        title=chart_title(chart),
        stacked=any(is_stacked(plot) for plot in plots),
        percent_stacked=any(getattr(plot, "grouping", None) == PERCENT_GROUPING for plot in plots),
        secondary_axis=len({axis_identifier(plot) for plot in plots}) > 1,
        axis_titles=(axis_title(chart, "x_axis"), axis_title(chart, "y_axis")),
    )


def axis_title(chart, axis_name: str) -> str:
    return title_text(getattr(getattr(chart, axis_name, None), "title", None))


def numbers(source, values_workbook) -> tuple[float, ...]:
    reference = source.numRef.f if source is not None and source.numRef is not None else None
    return tuple(float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None for value in reference_values(reference, values_workbook))


def label_mode(plots: list) -> str:
    labels = next((plot.dLbls for plot in plots if getattr(plot, "dLbls", None) is not None), None)
    shown = {flag for flags in LABEL_FLAGS.values() for flag in flags if labels is not None and getattr(labels, flag)}
    exact = next((mode for mode, flags in LABEL_FLAGS.items() if set(flags) == shown), None)
    return exact or ("value" if "showVal" in shown else "none")


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
    return tuple(f"#{palette[slot].lower()}" for slot in ACCENT_POSITIONS)


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
    return f"#{palette[ACCENT_POSITIONS[index % len(ACCENT_POSITIONS)]].lower()}"


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
    return "+".join(dict.fromkeys(plot_series_kind(plot) for plot in chart_plots(chart)))


def chart_title(chart) -> str:
    return title_text(chart.title)


def title_text(title) -> str:
    if title is None or title.tx is None or title.tx.rich is None:
        return ""
    return "".join(run.t or "" for paragraph in title.tx.rich.p for run in (paragraph.r or []))
