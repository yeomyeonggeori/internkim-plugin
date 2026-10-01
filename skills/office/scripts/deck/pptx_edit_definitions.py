from __future__ import annotations

from dataclasses import dataclass
import difflib
import re

from office_result import INVALID_VALUE, UNKNOWN_FIELD, Issue
from office_schema import Boolean, CellValue, Choice, Field, ListOf, MapOf, Number, Record, Shape, Text, Variant, wrong_type


HEX_COLOR_PATTERN = re.compile(r"#?[0-9A-Fa-f]{6}")
SHAPE_PATH_PATTERN = re.compile(r"\d+(\.\d+)*")
THEME_COLOR_SLOTS = ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink")
SHAPE_KINDS = ("rectangle", "rounded_rectangle", "oval", "triangle", "right_arrow", "chevron", "pentagon", "diamond")
CHART_TYPES = ("column", "stacked_column", "bar", "stacked_bar", "line", "pie", "doughnut", "area")


@dataclass(frozen=True)
class HexColor(Shape):
    allows_none: bool = False

    @property
    def label(self) -> str:
        return 'six hex digits such as 1F4E79, or "none"' if self.allows_none else "six hex digits such as 1F4E79"

    def problems(self, value: object, location: str) -> list[Issue]:
        if not isinstance(value, str):
            return [wrong_type(self, value, location)]
        if self.allows_none and value == "none" or HEX_COLOR_PATTERN.fullmatch(value):
            return []
        return [INVALID_VALUE.issue(f"{location}: {value!r} is not {self.label}", location)]


@dataclass(frozen=True)
class ShapeAddress(Shape):
    label = 'index or "g.i"'

    def problems(self, value: object, location: str) -> list[Issue]:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return []
        if isinstance(value, str) and SHAPE_PATH_PATTERN.fullmatch(value):
            return []
        return [wrong_type(self, value, location)]


@dataclass(frozen=True)
class GuidedVariant(Variant):
    def problems(self, value: object, location: str) -> list[Issue]:
        problems = Variant.problems(self, value, location)
        if not isinstance(value, dict):
            return problems
        record = self.record_named(value.get(self.discriminator))
        if record is None:
            return [with_close_match(problem, value.get(self.discriminator), self.record_names()) for problem in problems]
        field_names = [self.discriminator, *(field.name for field in record.fields)]
        return [with_close_match(problem, problem.location.rsplit(".", 1)[-1], field_names) if problem.kind is UNKNOWN_FIELD else problem for problem in problems]


def with_close_match(problem: Issue, given: object, candidates: list[str]) -> Issue:
    if problem.kind not in (INVALID_VALUE, UNKNOWN_FIELD) or not isinstance(given, str):
        return problem
    return Issue(problem.kind, problem.message, problem.location, closest_name_suggestion(given, candidates, problem.suggestion))


def closest_name_suggestion(given: str, candidates: list[str], fallback: object) -> object:
    matches = difflib.get_close_matches(given, candidates, n=1, cutoff=0.5)
    return f"did you mean {matches[0]!r}?" if matches else fallback


SLIDE_NUMBER = Number(minimum=1, integer=True)
SLIDE_FIELD = Field("slide", SLIDE_NUMBER, "from deck read", required=True)
SHAPE_FIELD = Field("shape", ShapeAddress(), 'from deck read; "3.1" is shape 1 inside group 3', required=True)
PARAGRAPH_FIELD = Field("paragraph", Number(minimum=0, integer=True), "only this paragraph, from 0; default all")
EMU_COORDINATE = Number(integer=True)
EMU_LENGTH = Number(minimum=1, integer=True)
POSITION_FIELDS = (
    Field("x", EMU_COORDINATE, "left edge in EMU (914400 per inch, 12700 per point)", required=True),
    Field("y", EMU_COORDINATE, "top edge in EMU", required=True),
)
BOX_FIELDS = (
    *POSITION_FIELDS,
    Field("w", EMU_LENGTH, "width in EMU", required=True),
    Field("h", EMU_LENGTH, "height in EMU", required=True),
)
RUN_STYLE_FIELDS = (
    Field("font", Text(non_empty=True), "typeface for Latin and Korean text"),
    Field("size", Number(minimum=1, maximum=400), "size in points"),
    Field("bold", Boolean(), "bold on or off"),
    Field("italic", Boolean(), "italic on or off"),
    Field("underline", Boolean(), "underline on or off"),
    Field("color", HexColor(), "text color"),
)
ALIGNMENT = Choice(("left", "center", "right", "justify"))
TEXT_FIELD = Field("text", Text(), "new text; a newline starts a new paragraph", required=True)
TABLE_ROW = Field("row", Number(minimum=0, integer=True), "from 0", required=True)
TABLE_COLUMN = Field("column", Number(minimum=0, integer=True), "from 0", required=True)
LAYOUT_FIELD = Field("layout", Text(non_empty=True), "layout name as deck read lists it", required=True)
AFTER_FIELD = Field("after", Number(minimum=0, integer=True), "slide number the new slide follows; 0 puts it first")
CELL_ROWS = ListOf(ListOf(CellValue()), non_empty=True)
SERIES = Record("series", "one data series", (
    Field("name", Text(non_empty=True), "series name shown in the legend", required=True),
    Field("values", ListOf(Number(), non_empty=True), "one number per category", required=True),
))


def operation(name: str, description: str, *fields: Field) -> Record:
    return Record(name, description, fields)


TEXT_OPERATIONS = (
    operation("set_text", "replace the text of a shape or of one paragraph, keeping the formatting of the run it starts in", SLIDE_FIELD, SHAPE_FIELD, TEXT_FIELD, PARAGRAPH_FIELD),
    operation("find_replace", "replace every occurrence of text in shapes, groups and table cells, keeping the formatting of the run the match starts in",
        Field("find", Text(non_empty=True), "exact text to find; it must occur at least once", required=True),
        Field("replace", Text(), "replacement text", required=True),
        Field("slide", SLIDE_NUMBER, "only this slide; default every slide"),
        Field("shape", ShapeAddress(), "only this shape of that slide"),
    ),
    operation("set_text_style", "restyle every run of a shape or of one paragraph; fields left out keep their value", SLIDE_FIELD, SHAPE_FIELD, PARAGRAPH_FIELD, *RUN_STYLE_FIELDS),
    operation("set_paragraph", "set alignment, bullets, level and spacing of a shape's paragraphs", SLIDE_FIELD, SHAPE_FIELD, PARAGRAPH_FIELD,
        Field("align", ALIGNMENT, "horizontal alignment"),
        Field("bullet", Choice(("none", "bullet", "number")), "bullet kind"),
        Field("level", Number(minimum=0, maximum=8, integer=True), "list level"),
        Field("lineSpacing", Number(minimum=0.5, maximum=5), "line spacing as a multiple, 1 is single"),
        Field("spaceBefore", Number(minimum=0), "points above the paragraph"),
        Field("spaceAfter", Number(minimum=0), "points below the paragraph"),
    ),
    operation("set_text_frame", "set how a shape's text fits its box", SLIDE_FIELD, SHAPE_FIELD,
        Field("autofit", Choice(("none", "shrink", "resize")), "none keeps the box and size; shrink lowers the text size to fit; resize grows the box to the text"),
        Field("wrap", Boolean(), "wrap lines at the box width"),
        Field("anchor", Choice(("top", "middle", "bottom")), "vertical position of the text in the box"),
    ),
)
ELEMENT_OPERATIONS = (
    operation("set_transform", "move, resize or rotate a shape; give any of x, y, w, h in EMU in slide coordinates, the rest stay", SLIDE_FIELD, SHAPE_FIELD,
        Field("x", EMU_COORDINATE, "left edge"),
        Field("y", EMU_COORDINATE, "top edge"),
        Field("w", EMU_LENGTH, "width"),
        Field("h", EMU_LENGTH, "height"),
        Field("rotation", Number(minimum=-360, maximum=360), "clockwise degrees"),
    ),
    operation("delete_shape", "delete a shape, its animations and any relationship only it used", SLIDE_FIELD, SHAPE_FIELD),
    operation("duplicate_shape", "copy a shape just above itself in z-order; a copied chart gets its own data", SLIDE_FIELD, SHAPE_FIELD,
        Field("x", EMU_COORDINATE, "left edge of the copy; default 0.25 inch right of the original"),
        Field("y", EMU_COORDINATE, "top edge of the copy; default 0.25 inch below the original"),
    ),
    operation("set_z_order", "move a shape in front of or behind the others", SLIDE_FIELD, SHAPE_FIELD,
        Field("to", Choice(("front", "back", "forward", "backward")), "front and back go to the ends; forward and backward move one step", required=True),
    ),
    operation("set_fill", "fill a shape with a solid color or remove its fill", SLIDE_FIELD, SHAPE_FIELD,
        Field("color", HexColor(allows_none=True), "fill color", required=True),
    ),
    operation("set_line", "set a shape's outline", SLIDE_FIELD, SHAPE_FIELD,
        Field("color", HexColor(allows_none=True), "outline color; none removes the outline"),
        Field("width", Number(minimum=0, maximum=100), "outline width in points"),
    ),
    operation("replace_picture", "swap a picture's image, keeping its frame, position and effects; the new image is cropped to fill the frame without stretching", SLIDE_FIELD, SHAPE_FIELD,
        Field("image", Text(non_empty=True), "path to a PNG, JPEG or GIF file", required=True),
    ),
)
INSERT_OPERATIONS = (
    operation("add_text_box", "add a text box that wraps at its width", SLIDE_FIELD, *BOX_FIELDS, TEXT_FIELD, *RUN_STYLE_FIELDS,
        Field("align", ALIGNMENT, "horizontal alignment"),
    ),
    operation("add_shape", "add a filled shape, optionally with centered text", SLIDE_FIELD, *BOX_FIELDS,
        Field("kind", Choice(SHAPE_KINDS), "shape geometry", required=True),
        Field("fill", HexColor(allows_none=True), "fill color; default the theme's"),
        Field("line", HexColor(allows_none=True), "outline color; default the theme's"),
        Field("text", Text(), "text inside the shape"),
    ),
    operation("add_picture", "add an image; give w or h alone to keep its ratio", SLIDE_FIELD, *POSITION_FIELDS,
        Field("image", Text(non_empty=True), "path to a PNG, JPEG or GIF file", required=True),
        Field("w", EMU_LENGTH, "width; default from h or the image's own size"),
        Field("h", EMU_LENGTH, "height; default from w or the image's own size"),
    ),
    operation("add_table", "add a table styled by the theme; the first row is the header", SLIDE_FIELD, *POSITION_FIELDS,
        Field("w", EMU_LENGTH, "width in EMU", required=True),
        Field("h", EMU_LENGTH, "height in EMU; default 0.4 inch per row"),
        Field("rows", CELL_ROWS, "rows of cell values", required=True),
    ),
    operation("add_chart", "add a native chart with its own data workbook", SLIDE_FIELD, *BOX_FIELDS,
        Field("type", Choice(CHART_TYPES), "chart kind", required=True),
        Field("categories", ListOf(CellValue(), non_empty=True), "category labels along the axis", required=True),
        Field("series", ListOf(SERIES, non_empty=True), "data series; pie and doughnut take one", required=True),
        Field("title", Text(), "chart title"),
        Field("legend", Boolean(), "show the legend; default when there is more than one series or a pie"),
    ),
)
TABLE_AND_CHART_OPERATIONS = (
    operation("set_table_cell", "replace one table cell's text, keeping its formatting", SLIDE_FIELD, SHAPE_FIELD, TABLE_ROW, TABLE_COLUMN, TEXT_FIELD),
    operation("insert_table_row", "insert a row formatted like its neighbor; the table grows by its height", SLIDE_FIELD, SHAPE_FIELD,
        Field("at", Number(minimum=0, integer=True), "index the new row takes; default after the last row"),
        Field("values", ListOf(CellValue()), "cell values, left to right"),
    ),
    operation("delete_table_row", "delete a row; the table shrinks by its height", SLIDE_FIELD, SHAPE_FIELD, TABLE_ROW),
    operation("insert_table_column", "insert a column formatted like its neighbor; the table grows by its width", SLIDE_FIELD, SHAPE_FIELD,
        Field("at", Number(minimum=0, integer=True), "index the new column takes; default after the last column"),
        Field("values", ListOf(CellValue()), "cell values, top to bottom"),
    ),
    operation("delete_table_column", "delete a column; the table shrinks by its width", SLIDE_FIELD, SHAPE_FIELD, TABLE_COLUMN),
    operation("merge_table_cells", "merge a block of cells into its top-left cell", SLIDE_FIELD, SHAPE_FIELD, TABLE_ROW, TABLE_COLUMN,
        Field("rows", Number(minimum=1, integer=True), "how many rows the block spans, default 1"),
        Field("columns", Number(minimum=1, integer=True), "how many columns the block spans, default 1"),
    ),
    operation("set_chart_data", "replace a chart's series, and optionally its categories and title, keeping its type and formatting", SLIDE_FIELD, SHAPE_FIELD,
        Field("series", ListOf(SERIES, non_empty=True), "every series the chart shows", required=True),
        Field("categories", ListOf(CellValue(), non_empty=True), "category labels; default the chart's own"),
        Field("title", Text(), "chart title; empty text removes it"),
    ),
)
SLIDE_OPERATIONS = (
    operation("add_slide", "add a slide from a layout, filling its title and body placeholders", LAYOUT_FIELD, AFTER_FIELD,
        Field("title", Text(), "title placeholder text"),
        Field("body", Text(), "first body placeholder text; a newline starts a new paragraph"),
    ),
    operation("duplicate_slide", "copy a slide with its notes, pictures, charts and animations", SLIDE_FIELD,
        Field("after", Number(minimum=0, integer=True), "slide number the copy follows; default the original"),
    ),
    operation("delete_slide", "delete a slide", SLIDE_FIELD),
    operation("reorder", "put the slides in a new order, given as the numbers deck read showed",
        Field("order", ListOf(SLIDE_NUMBER, non_empty=True), "every slide that remains, each once, in the new order", required=True),
    ),
    operation("set_slide_hidden", "hide a slide from the slide show or show it again", SLIDE_FIELD,
        Field("hidden", Boolean(), "true hides the slide", required=True),
    ),
    operation("set_background", "give a slide a solid background color", SLIDE_FIELD,
        Field("color", HexColor(), "background color", required=True),
    ),
    operation("set_layout", "switch a slide to another layout; its placeholders follow the new layout", SLIDE_FIELD, LAYOUT_FIELD),
    operation("set_notes", "replace a slide's speaker notes; empty text clears them", SLIDE_FIELD,
        Field("text", Text(), "notes text; a newline starts a new paragraph", required=True),
    ),
)
DECK_OPERATIONS = (
    operation("set_theme", "change the theme every slide inherits its colors and fonts from",
        Field("colors", MapOf(HexColor(), key="theme slot: " + ", ".join(THEME_COLOR_SLOTS)), "colors by slot"),
        Field("headingFont", Text(non_empty=True), "Latin typeface for titles"),
        Field("bodyFont", Text(non_empty=True), "Latin typeface for body text"),
        Field("koreanFont", Text(non_empty=True), "typeface for Korean text in titles and body"),
    ),
    operation("set_slide_size", "change the slide size in EMU; 12192000 x 6858000 is 16:9",
        Field("width", EMU_LENGTH, "slide width", required=True),
        Field("height", EMU_LENGTH, "slide height", required=True),
        Field("scaleContent", Boolean(), "scale every shape with the slide, default true"),
    ),
)


OPERATIONS = GuidedVariant(
    "operation",
    "one edit of deck apply; slide numbers, shape indexes and table rows refer to the deck as deck read showed it before the batch, "
    "operations run in order, and the batch applies whole or not at all; a slide added in the batch is edited in the next batch",
    "op",
    TEXT_OPERATIONS + ELEMENT_OPERATIONS + INSERT_OPERATIONS + TABLE_AND_CHART_OPERATIONS + SLIDE_OPERATIONS + DECK_OPERATIONS,
)
