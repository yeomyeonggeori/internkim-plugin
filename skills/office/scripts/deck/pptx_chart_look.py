from __future__ import annotations

from dataclasses import dataclass, field
import re

from pptx.oxml.ns import qn

from pptx_preview_paint import point_pixels
from pptx_style import resolve_color, theme_slot_color


ACCENT_SLOTS = ("accent1", "accent2", "accent3", "accent4", "accent5", "accent6")
FALLBACK_ACCENT = "4472C4"
GRID_COLOR = "#D9D9D9"
TEXT_COLOR = "#404040"
LABEL_SIZE = 13
DEFAULT_GAP_WIDTH = 150
DEFAULT_HOLE_PERCENT = 50
QUOTED_LITERAL = re.compile(r'"([^"]*)"')


@dataclass(frozen=True)
class TextLook:
    color: str = TEXT_COLOR
    size: float = LABEL_SIZE


@dataclass(frozen=True)
class PointLabel:
    shown: bool
    show_percent: bool
    format_code: str
    position: str
    text: TextLook


@dataclass(frozen=True)
class LabelLook:
    default: PointLabel
    points: dict[int, PointLabel] = field(default_factory=dict)

    def at(self, index: int) -> PointLabel:
        return self.points.get(index, self.default)


@dataclass(frozen=True)
class ChartLook:
    series_colors: list[str]
    point_colors: list[dict[int, str]]
    theme_colors: list[str]
    labels: list[LabelLook | None]
    text: TextLook
    legend_position: str | None
    value_axis_shown: bool
    gridlines: str | None
    axis_line: str | None
    reversed_categories: bool
    gap_width: int
    hole_percent: int
    value_limits: tuple[float | None, float | None]
    major_unit: float | None

    def color_of(self, series: int, point: int) -> str:
        return self.point_colors[series].get(point, self.series_colors[series])

    def slice_color(self, point: int) -> str:
        return self.point_colors[0].get(point, self.theme_colors[point % len(self.theme_colors)]) if self.point_colors else self.theme_colors[0]


def chart_look(chart, context) -> ChartLook:
    space = chart._chartSpace
    plot = next(child for child in space.find(f"{qn('c:chart')}/{qn('c:plotArea')}") if child.tag.endswith("Chart"))
    base_text = text_look(context, space.find(qn("c:txPr")), TextLook())
    series = plot.findall(qn("c:ser"))
    theme_colors = ["#" + (theme_slot_color(context, slot) or FALLBACK_ACCENT).lstrip("#") for slot in ACCENT_SLOTS]
    value_axis = space.find(f".//{qn('c:valAx')}")
    category_axis = space.find(f".//{qn('c:catAx')}")
    plot_labels = plot.find(qn("c:dLbls"))
    return ChartLook(
        series_colors=[series_color(context, entry, theme_colors[index % len(theme_colors)]) for index, entry in enumerate(series)],
        point_colors=[point_colors(context, entry) for entry in series],
        theme_colors=theme_colors,
        labels=[label_look(context, first_present(entry.find(qn("c:dLbls")), plot_labels), base_text) for entry in series],
        text=base_text,
        legend_position=legend_position(space),
        value_axis_shown=value_axis is not None and setting(value_axis, "c:delete", "0") != "1",
        gridlines=gridline_color(context, value_axis),
        axis_line=solid_color(context, category_axis.find(qn("c:spPr")) if category_axis is not None else None, "a:ln"),
        reversed_categories=setting(category_axis, "c:scaling/c:orientation", "minMax") == "maxMin",
        gap_width=int(setting(plot, "c:gapWidth", str(DEFAULT_GAP_WIDTH))),
        hole_percent=int(setting(plot, "c:holeSize", str(DEFAULT_HOLE_PERCENT))),
        value_limits=(number_setting(value_axis, "c:scaling/c:min"), number_setting(value_axis, "c:scaling/c:max")),
        major_unit=number_setting(value_axis, "c:majorUnit"),
    )


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
    return solid_color(context, properties) or solid_color(context, properties, "a:ln") or theme_color


def point_colors(context, series) -> dict[int, str]:
    colors = {}
    for point in series.findall(qn("c:dPt")):
        color = solid_color(context, point.find(qn("c:spPr")))
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
    default = point_label(context, labels, PointLabel(False, False, "General", "outEnd", base_text))
    points = {int(setting(label, "c:idx", "0")): point_label(context, label, default) for label in labels.findall(qn("c:dLbl"))}
    return LabelLook(default, points)


def point_label(context, element, fallback: PointLabel) -> PointLabel:
    if setting(element, "c:delete", "0") == "1":
        return PointLabel(False, False, fallback.format_code, fallback.position, fallback.text)
    number_format = element.find(qn("c:numFmt"))
    show_value = setting(element, "c:showVal", "1" if fallback.shown and not fallback.show_percent else "0") == "1"
    show_percent = setting(element, "c:showPercent", "1" if fallback.show_percent else "0") == "1"
    return PointLabel(
        shown=show_value or show_percent,
        show_percent=show_percent,
        format_code=number_format.get("formatCode", fallback.format_code) if number_format is not None else fallback.format_code,
        position=setting(element, "c:dLblPos", fallback.position),
        text=text_look(context, element.find(qn("c:txPr")), fallback.text),
    )


def legend_position(space) -> str | None:
    legend = space.find(f"{qn('c:chart')}/{qn('c:legend')}")
    return None if legend is None else setting(legend, "c:legendPos", "r")


def gridline_color(context, value_axis) -> str | None:
    gridlines = value_axis.find(qn("c:majorGridlines")) if value_axis is not None else None
    if gridlines is None:
        return None
    return solid_color(context, gridlines.find(qn("c:spPr")), "a:ln") or GRID_COLOR


def formatted(number: float, format_code: str) -> str:
    if format_code == "General":
        return f"{number:g}"
    literals = QUOTED_LITERAL.findall(format_code)
    pattern = QUOTED_LITERAL.sub("", format_code)
    is_percent = "%" in pattern
    decimals = len(pattern.split(".", 1)[1].rstrip("%")) if "." in pattern else 0
    shown = number * 100 if is_percent else number
    digits = f"{shown:,.{decimals}f}" if "," in pattern else f"{shown:.{decimals}f}"
    prefix = literals[0] if literals and format_code.startswith('"') else ""
    suffix = "".join(literals[1:] if prefix else literals)
    return f"{prefix}{digits}{'%' if is_percent else ''}{suffix}"
