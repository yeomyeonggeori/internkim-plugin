from __future__ import annotations

from dataclasses import dataclass, field, replace

from core.office_theme import OFFICE_ACCENTS


LABEL_FLAGS = {"none": (), "value": ("showVal",), "category": ("showCatName",), "percent": ("showPercent",), "category_percent": ("showCatName", "showPercent")}
GENERAL_FORMAT = "General"
PERCENT_FORMAT = "0%"
INSIDE_POSITIONS = ("ctr", "inEnd", "inBase", "bestFit")
OUTSIDE_POSITION = "outEnd"
BELOW_POSITION = "b"
LEFT_POSITION = "l"
TEXT_COLOR = "#404040"
GRID_COLOR = "#D9D9D9"
DEFAULT_TEXT_SIZE = 13
DEFAULT_TITLE_SIZE = 19
DEFAULT_GAP_WIDTH = 150
DEFAULT_HOLE_PERCENT = 50
NO_LIMITS = (None, None)
OFFICE_SERIES_COLORS = tuple(f"#{color.lower()}" for color in OFFICE_ACCENTS)


@dataclass(frozen=True)
class TextLook:
    color: str = TEXT_COLOR
    size: float = DEFAULT_TEXT_SIZE
    bold: bool = False
    family: str = ""


@dataclass(frozen=True)
class PointLabel:
    show_value: bool = False
    show_percent: bool = False
    show_category: bool = False
    format_code: str | None = GENERAL_FORMAT
    position: str = ""
    text: TextLook = TextLook()
    custom_text: str = ""

    @property
    def shown(self) -> bool:
        return self.show_value or self.show_percent or self.show_category or bool(self.custom_text)

    @property
    def is_inside(self) -> bool:
        return self.position in INSIDE_POSITIONS

    def typeset(self, family: str) -> PointLabel:
        return replace(self, text=replace(self.text, family=family))


@dataclass(frozen=True)
class LabelLook:
    default: PointLabel
    points: dict[int, PointLabel] = field(default_factory=dict)

    def at(self, index: int) -> PointLabel:
        return self.points.get(index, self.default)

    def typeset(self, family: str) -> LabelLook:
        return LabelLook(self.default.typeset(family), {index: label.typeset(family) for index, label in self.points.items()})


@dataclass(frozen=True)
class ChartLook:
    series_colors: tuple[str, ...]
    slice_colors: tuple[str, ...]
    point_colors: tuple[dict[int, str], ...] = ()
    labels: tuple[LabelLook | None, ...] = ()
    text: TextLook = TextLook()
    title: TextLook = TextLook(size=DEFAULT_TITLE_SIZE, bold=True)
    legend_position: str | None = "b"
    value_axis_shown: bool = True
    secondary_axis_shown: bool = True
    gridlines: str | None = GRID_COLOR
    axis_line: str | None = None
    frame: str | None = None
    reversed_categories: bool = False
    gap_width: int = DEFAULT_GAP_WIDTH
    hole_percent: int = DEFAULT_HOLE_PERCENT
    value_limits: tuple[float | None, float | None] = NO_LIMITS
    major_unit: float | None = None
    secondary_limits: tuple[float | None, float | None] = NO_LIMITS
    horizontal_limits: tuple[float | None, float | None] = NO_LIMITS
    axis_format: str | None = GENERAL_FORMAT

    def color_of(self, series: int, point: int) -> str:
        own = self.point_colors[series] if series < len(self.point_colors) else {}
        return own.get(point, self.series_colors[series % len(self.series_colors)])

    def slice_color(self, point: int) -> str:
        own = self.point_colors[0] if self.point_colors else {}
        return own.get(point, self.slice_colors[point % len(self.slice_colors)])

    def label_of(self, series: int) -> LabelLook | None:
        return self.labels[series] if series < len(self.labels) else None

    def typeset(self, family: str) -> ChartLook:
        return replace(
            self,
            text=replace(self.text, family=family),
            title=replace(self.title, family=family),
            labels=tuple(labels.typeset(family) if labels is not None else None for labels in self.labels),
        )


DOCUMENT_TEXT = TextLook("#595959", 10)
DOCUMENT_LABEL_TEXT = TextLook("#262626", 10)
DOCUMENT_SLICE_TEXT = TextLook("#FFFFFF", 11, bold=True)
DOCUMENT_TITLE = TextLook("#262626", 14, bold=True)
DOCUMENT_GRID_COLOR = "#E6E6E6"
DOCUMENT_AXIS_COLOR = "#8C8C8C"
DOCUMENT_FRAME_COLOR = "#D9D9D9"
DOCUMENT_GAP_WIDTH = 54
DOCUMENT_HOLE_PERCENT = 55


def document_look(colors: tuple[str, ...], series_count: int, is_round: bool, is_stacked: bool, legend: bool, data_labels: str | None) -> ChartLook:
    labels = document_labels(data_labels, is_round, is_stacked)
    return ChartLook(
        series_colors=colors,
        slice_colors=colors,
        labels=(labels,) * series_count,
        text=DOCUMENT_TEXT,
        title=DOCUMENT_TITLE,
        legend_position="b" if legend else None,
        gridlines=DOCUMENT_GRID_COLOR,
        axis_line=DOCUMENT_AXIS_COLOR,
        frame=DOCUMENT_FRAME_COLOR,
        gap_width=DOCUMENT_GAP_WIDTH,
        hole_percent=DOCUMENT_HOLE_PERCENT,
        axis_format=None,
    )


def document_labels(mode: str | None, is_round: bool, is_stacked: bool) -> LabelLook | None:
    if mode is None and is_round:
        return LabelLook(PointLabel(show_percent=True, format_code=None, position="ctr", text=DOCUMENT_SLICE_TEXT))
    flags = LABEL_FLAGS.get(mode or "none", ())
    if not flags:
        return None
    inside = is_stacked or (is_round and "showCatName" not in flags)
    return LabelLook(PointLabel(
        show_value="showVal" in flags,
        show_percent="showPercent" in flags,
        show_category="showCatName" in flags,
        format_code=None,
        position="ctr" if inside else OUTSIDE_POSITION,
        text=DOCUMENT_SLICE_TEXT if is_round and inside else DOCUMENT_LABEL_TEXT,
    ))
