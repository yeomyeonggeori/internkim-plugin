from __future__ import annotations

from pptx.oxml.ns import qn

from charts.kinds import PERCENT_GROUPING, STACKED_GROUPINGS, plot_kind
from charts.look import DEFAULT_GAP_WIDTH, DEFAULT_HOLE_PERCENT, DEFAULT_TITLE_SIZE, GENERAL_FORMAT, GRID_COLOR, ChartLook, LabelLook, PointLabel, TextLook
from charts.svg import ChartModel, ChartSeries
from core.office_theme import ACCENT_SLOTS, OFFICE_THEME
from deck.pptx_preview_paint import point_pixels
from deck.pptx_style import resolve_color, theme_slot_color


HORIZONTAL_POSITIONS = {"b", "t"}


def chart_model(chart, details: dict) -> ChartModel:
    plots = plot_elements(chart._chartSpace)
    kinds = [plot_kind(local_name(plot), setting(plot, "c:barDir", "col")) or "column" for plot in plots for _ in plot.findall(qn("c:ser"))]
    groupings = {setting(plot, "c:grouping", "standard") for plot in plots}
    series = tuple(
        ChartSeries(str(entry["name"] or ""), tuple(value or 0.0 for value in entry["values"]), kind, tuple(value or 0.0 for value in entry.get("x") or ()))
        for entry, kind in zip(details["series"], kinds)
    )
    return ChartModel(
        categories=tuple(str(category) for category in details["categories"]),
        series=series,
        title=details.get("title") or "",
        stacked=bool(groupings & set(STACKED_GROUPINGS)),
        percent_stacked=PERCENT_GROUPING in groupings,
        secondary_axis=len({axis_identifiers(plot) for plot in plots}) > 1,
    )


def plot_elements(space) -> list:
    plot_area = space.find(f"{qn('c:chart')}/{qn('c:plotArea')}")
    return [child for child in plot_area if child.tag.endswith("Chart")]


def local_name(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def axis_identifiers(plot) -> frozenset[str]:
    return frozenset(axis.get("val") for axis in plot.findall(qn("c:axId")))


def chart_look(chart, context) -> ChartLook:
    space = chart._chartSpace
    plot_area = space.find(f"{qn('c:chart')}/{qn('c:plotArea')}")
    plots = plot_elements(space)
    plot = plots[0]
    base_text = text_look(context, space.find(qn("c:txPr")), TextLook())
    plotted = [(owner, entry) for owner in plots for entry in owner.findall(qn("c:ser"))]
    theme_colors = tuple("#" + (theme_slot_color(context, slot) or OFFICE_THEME[slot]).lstrip("#") for slot in ACCENT_SLOTS)
    value_axis = plot_value_axis(plot_area, plot)
    category_axis = space.find(f".//{qn('c:catAx')}")
    secondary_axis = plot_value_axis(plot_area, plots[-1]) if len(plots) > 1 else None
    return ChartLook(
        series_colors=tuple(series_color(context, entry, theme_colors[index % len(theme_colors)]) for index, (_, entry) in enumerate(plotted)),
        slice_colors=theme_colors,
        point_colors=tuple(point_colors(context, entry) for _, entry in plotted),
        labels=tuple(label_look(context, first_present(entry.find(qn("c:dLbls")), owner.find(qn("c:dLbls"))), base_text) for owner, entry in plotted),
        text=base_text,
        title=title_look(context, space, base_text),
        legend_position=legend_position(space),
        value_axis_shown=is_shown(value_axis),
        secondary_axis_shown=is_shown(secondary_axis),
        gridlines=gridline_color(context, value_axis),
        axis_line=solid_color(context, category_axis.find(qn("c:spPr")) if category_axis is not None else None, "a:ln"),
        reversed_categories=setting(category_axis, "c:scaling/c:orientation", "minMax") == "maxMin",
        gap_width=int(setting(plot, "c:gapWidth", str(DEFAULT_GAP_WIDTH))),
        hole_percent=int(setting(plot, "c:holeSize", str(DEFAULT_HOLE_PERCENT))),
        value_limits=axis_limits(value_axis),
        major_unit=number_setting(value_axis, "c:majorUnit"),
        secondary_limits=axis_limits(secondary_axis),
        horizontal_limits=axis_limits(plot_value_axis(plot_area, plot, HORIZONTAL_POSITIONS)),
    )


def is_shown(axis) -> bool:
    return axis is not None and setting(axis, "c:delete", "0") != "1"


def title_look(context, space, base_text: TextLook) -> TextLook:
    title = space.find(f"{qn('c:chart')}/{qn('c:title')}")
    own = text_look(context, title.find(qn("c:txPr")) if title is not None else None, TextLook(base_text.color, DEFAULT_TITLE_SIZE, True))
    return rich_text_look(context, title, own) if title is not None else own


def plot_value_axis(plot_area, plot, positions: set[str] | None = None):
    axis_ids = {axis.get("val") for axis in plot.findall(qn("c:axId"))}
    axes = [axis for axis in plot_area.findall(qn("c:valAx")) if setting(axis, "c:axId", "") in axis_ids]
    if positions is None:
        positions = {"l", "r"} if len(axes) > 1 else None
    matching = [axis for axis in axes if positions is None or setting(axis, "c:axPos", "l") in positions]
    return matching[0] if matching else None


def axis_limits(axis) -> tuple[float | None, float | None]:
    return number_setting(axis, "c:scaling/c:min"), number_setting(axis, "c:scaling/c:max")


def first_present(*elements):
    return next((element for element in elements if element is not None), None)


def setting(parent, path: str, default: str) -> str:
    if parent is None:
        return default
    found = parent.find("/".join(qn(part) for part in path.split("/")))
    return found.get("val", default) if found is not None else default


def number_setting(parent, path: str) -> float | None:
    text = setting(parent, path, "")
    return float(text) if text else None


def solid_color(context, properties, *path: str) -> str | None:
    if properties is None:
        return None
    fill = properties.find("/".join(qn(part) for part in (*path, "a:solidFill")))
    if fill is None or not len(fill):
        return None
    return resolve_color(context, fill[0])


def series_color(context, series, theme_color: str) -> str:
    properties = series.find(qn("c:spPr"))
    marker = series.find(f"{qn('c:marker')}/{qn('c:spPr')}")
    return solid_color(context, properties) or solid_color(context, properties, "a:ln") or solid_color(context, marker) or theme_color


def point_colors(context, series) -> dict[int, str]:
    colors = {}
    for point in series.findall(qn("c:dPt")):
        color = solid_color(context, point.find(qn("c:spPr"))) or solid_color(context, point.find(f"{qn('c:marker')}/{qn('c:spPr')}"))
        if color:
            colors[int(setting(point, "c:idx", "0"))] = color
    return colors


def text_look(context, text_properties, fallback: TextLook) -> TextLook:
    defaults = text_properties.find(f".//{qn('a:defRPr')}") if text_properties is not None else None
    if defaults is None:
        return fallback
    size = defaults.get("sz")
    return TextLook(color=solid_color(context, defaults) or fallback.color, size=point_pixels(int(size) / 100) if size else fallback.size)


def label_look(context, labels, base_text: TextLook) -> LabelLook | None:
    if labels is None or setting(labels, "c:delete", "0") == "1":
        return None
    default = point_label(context, labels, PointLabel(format_code=GENERAL_FORMAT, text=base_text))
    points = {int(setting(label, "c:idx", "0")): point_label(context, label, default) for label in labels.findall(qn("c:dLbl"))}
    return LabelLook(default, points)


def point_label(context, element, fallback: PointLabel) -> PointLabel:
    if setting(element, "c:delete", "0") == "1":
        return PointLabel(format_code=fallback.format_code, position=fallback.position, text=fallback.text)
    number_format = element.find(qn("c:numFmt"))
    return PointLabel(
        show_value=flag(element, "c:showVal", fallback.show_value),
        show_percent=flag(element, "c:showPercent", fallback.show_percent),
        show_category=flag(element, "c:showCatName", fallback.show_category),
        format_code=number_format.get("formatCode", fallback.format_code) if number_format is not None else fallback.format_code,
        position=setting(element, "c:dLblPos", fallback.position),
        text=text_look(context, element.find(qn("c:txPr")), rich_text_look(context, element, fallback.text)),
        custom_text="".join(node.text or "" for node in element.iterfind(f"{qn('c:tx')}//{qn('a:t')}")),
    )


def flag(element, path: str, fallback: bool) -> bool:
    return setting(element, path, "1" if fallback else "0") == "1"


def rich_text_look(context, element, fallback: TextLook) -> TextLook:
    properties = element.find(f"{qn('c:tx')}//{qn('a:rPr')}")
    if properties is None:
        return fallback
    size = properties.get("sz")
    return TextLook(color=solid_color(context, properties) or fallback.color, size=point_pixels(int(size) / 100) if size else fallback.size)


def legend_position(space) -> str | None:
    legend = space.find(f"{qn('c:chart')}/{qn('c:legend')}")
    return None if legend is None else setting(legend, "c:legendPos", "r")


def gridline_color(context, value_axis) -> str | None:
    gridlines = value_axis.find(qn("c:majorGridlines")) if value_axis is not None else None
    if gridlines is None:
        return None
    return solid_color(context, gridlines.find(qn("c:spPr")), "a:ln") or GRID_COLOR

