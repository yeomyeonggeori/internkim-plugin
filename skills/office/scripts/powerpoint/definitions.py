from __future__ import annotations

from dataclasses import dataclass
import re

from charts.kinds import DECK_CHART_KINDS
from charts.look import LABEL_FLAGS
from core.design_rules import DESIGN_RULE_KINDS
from core.office_operations import OPERATION_ISSUE_KINDS
from core.office_result import ERROR, SETUP_COMMAND, WARNING, Issue, IssueKind
from core.template_merge import MERGE_VALUES, PACKAGE_MERGE_ISSUE_KINDS
from core.table_labels import CELL_ADDRESS_FIELDS
from core.text_checks import TEXT_CHECK_ISSUE_KINDS
from core.office_theme import THEME_SLOTS
from core.office_schema import Boolean, CellValue, Choice, Field, HexColor, ListOf, MapOf, Number, Record, Shape, Text, Variant, wrong_type
from powerpoint.model.connectors import ARROW_ENDS, CONNECTOR_KINDS, DEFAULT_ARROW, DEFAULT_WIDTH_POINTS, ELBOW_KIND, STRAIGHT_KIND
from powerpoint.model.lengths import LENGTH_EXAMPLES, Length
from powerpoint.model.table_styles import TABLE_STYLE_NAMES
from core.units import EMU_PER_INCH, EMU_PER_POINT
from core.image_formats import PICTURE_FORMATS_TEXT


OVERLAP_RATIO = 0.12
DISTORTION_TOLERANCE = 0.05
BACKGROUND_SHARE_OF_SLIDE = 0.7
DECK_LOCATION = "deck"


@dataclass(frozen=True)
class ReviewCheck:
    kind: IssueKind

    def issue(self, text: str, location: str | None = None, suggestion: object = None) -> Issue:
        return self.kind.issue(text, location, suggestion)

    def deck_issue(self, text: str) -> Issue:
        return self.issue(text, DECK_LOCATION)


def review_check(code: str, meaning: str, suggestion: str) -> ReviewCheck:
    return ReviewCheck(IssueKind(code, WARNING, meaning, suggestion))


def review_check_of_rule(code: str) -> ReviewCheck:
    rule = DESIGN_RULE_KINDS[code]
    return review_check(rule.code, rule.meaning, rule.suggestion)


CONTENT_OVERFLOW = review_check_of_rule("CONTENT_OVERFLOW")
OUT_OF_FRAME = review_check_of_rule("OUT_OF_FRAME")
TEXT_OVERLAP = review_check("TEXT_OVERLAP", "two pieces of text cover each other", "separate the two text blocks or shorten the one that spills")
IMAGE_DISTORTED = review_check("IMAGE_DISTORTED", "an image is stretched away from its own aspect ratio", "put the photo in a cover or image slide, which crops it to its frame, or give its box the image's own ratio")
CHART_POINT_OUTSIDE_AXIS = review_check("CHART_POINT_OUTSIDE_AXIS", "a chart value lies outside the limits of the axis it is drawn on, so PowerPoint and Keynote leave that bar or point out or cut it off", "widen the axis limits to hold every value, or remove the limits so the application sets them")
CHART_ZERO_MISALIGNED = review_check("CHART_ZERO_MISALIGNED", "a chart with two value axes draws zero at different heights, so a negative value on one axis can sit above the other's baseline", "set both axes' limits so zero falls at the same height, or draw the series on one axis")
SLIDE_COUNT_MISMATCH = IssueKind("SLIDE_COUNT_MISMATCH", ERROR, "the slide count differs from --slide-count", "add or remove slides until the count matches the request")
PICTURE_UNREADABLE = IssueKind("PICTURE_UNREADABLE", ERROR, f"an image file given to an operation is not a {PICTURE_FORMATS_TEXT} picture", f"pass the path of a {PICTURE_FORMATS_TEXT} file")
PPTX_NOT_RENDERED = IssueKind("PPTX_NOT_RENDERED", WARNING, "the renderer could not draw the slides, so nobody looked at them", f"run {SETUP_COMMAND} and run again, or say the slides were checked by measurement only and not seen")

LAYOUT_AUDIT_ISSUE_KINDS = (CONTENT_OVERFLOW.kind, OUT_OF_FRAME.kind, TEXT_OVERLAP.kind, IMAGE_DISTORTED.kind, CHART_POINT_OUTSIDE_AXIS.kind, CHART_ZERO_MISALIGNED.kind)
APPLY_ISSUE_KINDS = (PICTURE_UNREADABLE,)
PPTX_CHECK_ISSUE_KINDS = (PPTX_NOT_RENDERED,)


SHAPE_PATH_PATTERN = re.compile(r"\d+(\.\d+)*")
SHAPE_KINDS = ("rectangle", "rounded_rectangle", "oval", "triangle", "right_arrow", "chevron", "pentagon", "diamond")
ALIGN_EDGES = ("left", "center", "right", "top", "middle", "bottom")
ARRANGE_REFERENCES = ("selection", "slide")
TRANSITION_KINDS = ("none", "cut", "fade", "push", "wipe", "split", "cover", "pull", "dissolve", "zoom", "random")
TRANSITION_SPEEDS = ("fast", "medium", "slow")
ANIMATION_EFFECTS = ("appear", "fade", "fly_in", "wipe", "zoom")
ANIMATION_STARTS = ("on_click", "with_previous", "after_previous")
DIRECTIONS = ("from_bottom", "from_left", "from_right", "from_top")
CROP_SHARE = Number(minimum=0, maximum=0.99)


@dataclass(frozen=True)
class ShapeAddress(Shape):
    label = 'index or "g.i"'

    def problems(self, value: object, location: str) -> list[Issue]:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return []
        if isinstance(value, str) and SHAPE_PATH_PATTERN.fullmatch(value):
            return []
        return [wrong_type(self, value, location)]


SLIDE_NUMBER = Number(minimum=1, integer=True)
SLIDE_FIELD = Field("slide", SLIDE_NUMBER, "from office read", required=True)
SHAPE_FIELD = Field("shape", ShapeAddress(), 'from office read; "3.1" is shape 1 inside group 3', required=True)
SHAPES_FIELD = Field("shapes", ListOf(ShapeAddress(), non_empty=True), "shape indexes from office read", required=True)
PARAGRAPH_FIELD = Field("paragraph", Number(minimum=0, integer=True), "only this paragraph, from 0; default all")
X_LENGTH = Length("x")
Y_LENGTH = Length("y")
WIDTH = Length("x", minimum=1)
HEIGHT = Length("y", minimum=1)
POSITION_FIELDS = (
    Field("x", X_LENGTH, "left edge", required=True),
    Field("y", Y_LENGTH, "top edge", required=True),
)
BOX_FIELDS = (
    *POSITION_FIELDS,
    Field("w", WIDTH, "width", required=True),
    Field("h", HEIGHT, "height", required=True),
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
ANCHOR = Choice(("top", "middle", "bottom"))
TEXT_FIELD = Field("text", Text(), "new text; a newline starts a new paragraph", required=True)
TABLE_ROW = Field("row", Number(minimum=0, integer=True), "from 0", required=True)
TABLE_COLUMN = Field("column", Number(minimum=0, integer=True), "from 0", required=True)
LAYOUT_FIELD = Field("layout", Text(non_empty=True), "layout name as office read lists it", required=True)
AFTER_FIELD = Field("after", Number(minimum=0, integer=True), "slide number the new slide follows; 0 puts it first")
CELL_ROWS = ListOf(ListOf(CellValue()), non_empty=True)
SERIES = Record("series", "one data series", (
    Field("name", Text(non_empty=True), "series name shown in the legend", required=True),
    Field("values", ListOf(Number(), non_empty=True), "one number per category", required=True),
))


CHART_SERIES = Record("series", "one data series", (
    *SERIES.fields,
    Field("line", Boolean(), "combo only: draw this series as a line over the columns"),
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
    operation("set_text_style", "restyle the text of a shape or of one paragraph, or only each occurrence of find in it; fields left out keep their value", SLIDE_FIELD, SHAPE_FIELD, PARAGRAPH_FIELD,
        Field("find", Text(non_empty=True), "only this exact text, every time it occurs; the rest keeps its formatting"),
        *RUN_STYLE_FIELDS,
    ),
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
        Field("anchor", ANCHOR, "vertical position of the text in the box"),
    ),
)
ELEMENT_OPERATIONS = (
    operation("set_transform", "move, resize or rotate a shape; give any of x, y, w, h in slide coordinates, the rest stay", SLIDE_FIELD, SHAPE_FIELD,
        Field("x", X_LENGTH, "left edge"),
        Field("y", Y_LENGTH, "top edge"),
        Field("w", WIDTH, "width"),
        Field("h", HEIGHT, "height"),
        Field("rotation", Number(minimum=-360, maximum=360), "clockwise degrees"),
    ),
    operation("delete_shape", "delete a shape, its animations and any relationship only it used", SLIDE_FIELD, SHAPE_FIELD),
    operation("duplicate_shape", "copy a shape just above itself in z-order; a copied chart gets its own data", SLIDE_FIELD, SHAPE_FIELD,
        Field("x", X_LENGTH, "left edge of the copy; default 0.25 inch right of the original"),
        Field("y", Y_LENGTH, "top edge of the copy; default 0.25 inch below the original"),
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
        Field("image", Text(non_empty=True), f"path to a {PICTURE_FORMATS_TEXT} file", required=True),
    ),
    operation("crop_picture", "crop a picture inside its frame; each side is the share of the image cut from that edge, sides left out keep their value", SLIDE_FIELD, SHAPE_FIELD,
        Field("left", CROP_SHARE, "share cut from the left, 0.1 is 10%"),
        Field("top", CROP_SHARE, "share cut from the top"),
        Field("right", CROP_SHARE, "share cut from the right"),
        Field("bottom", CROP_SHARE, "share cut from the bottom"),
    ),
    operation("set_link", "make a shape, or one piece of its text, a link to a web address or to another slide", SLIDE_FIELD, SHAPE_FIELD,
        Field("url", Text(), "address to open, such as https://example.com or mailto:; empty text removes the link"),
        Field("toSlide", SLIDE_NUMBER, "slide the show jumps to; give this or url"),
        Field("text", Text(non_empty=True), "only this exact text in the shape becomes the link; default the whole shape"),
    ),
)
ARRANGE_OPERATIONS = (
    operation("align_shapes", "line shapes up on one edge or center line", SLIDE_FIELD, SHAPES_FIELD,
        Field("edge", Choice(ALIGN_EDGES), "center is the vertical center line, middle the horizontal one", required=True),
        Field("to", Choice(ARRANGE_REFERENCES), "line up with the shapes' common box (default, two or more shapes) or with the slide"),
    ),
    operation("distribute_shapes", "space shapes evenly along one axis; only that coordinate changes", SLIDE_FIELD, SHAPES_FIELD,
        Field("axis", Choice(("horizontal", "vertical")), "direction to space along", required=True),
        Field("to", Choice(ARRANGE_REFERENCES), "keep the outer two shapes and even the gaps between (default, three or more) or even the gaps to the slide edges"),
    ),
    operation("group_shapes", "group two or more shapes of the slide into one shape at the place of the frontmost", SLIDE_FIELD, SHAPES_FIELD),
    operation("ungroup_shape", "dissolve a group; its shapes stay where they are and take its place", SLIDE_FIELD, SHAPE_FIELD),
)
INSERT_OPERATIONS = (
    operation("add_text_box", "add a text box that wraps at its width; without a color its text takes the theme's dark or light text color, whichever reads better on what lies under the box", SLIDE_FIELD, *BOX_FIELDS, TEXT_FIELD, *RUN_STYLE_FIELDS,
        Field("align", ALIGNMENT, "horizontal alignment"),
    ),
    operation("add_shape", "add a filled shape, optionally with centered text", SLIDE_FIELD, *BOX_FIELDS,
        Field("kind", Choice(SHAPE_KINDS), "shape geometry", required=True),
        Field("fill", HexColor(allows_none=True), "fill color; default the theme's"),
        Field("line", HexColor(allows_none=True), "outline color; default the theme's"),
        Field("text", Text(), "text inside the shape"),
    ),
    operation("add_connector", "draw a connector between two shapes of one slide, from the side of the first that faces the second; it stays attached when either shape moves", SLIDE_FIELD,
        Field("from", ShapeAddress(), "shape the connector starts at, from office read", required=True),
        Field("to", ShapeAddress(), "shape the connector ends at, from office read", required=True),
        Field("kind", Choice(CONNECTOR_KINDS), f"{STRAIGHT_KIND} (default) or {ELBOW_KIND}, which turns at right angles"),
        Field("arrow", Choice(tuple(ARROW_ENDS)), f"where arrowheads go; default {DEFAULT_ARROW}"),
        Field("color", HexColor(), "line color; default the theme's dark or light text color, whichever reads on the slide"),
        Field("width", Number(minimum=0.25, maximum=20), f"line width in points, default {DEFAULT_WIDTH_POINTS:g}"),
    ),
    operation("add_picture", "add an image; give w or h alone to keep its ratio", SLIDE_FIELD, *POSITION_FIELDS,
        Field("image", Text(non_empty=True), f"path to a {PICTURE_FORMATS_TEXT} file", required=True),
        Field("w", WIDTH, "width; default from h or the image's own size"),
        Field("h", HEIGHT, "height; default from w or the image's own size"),
    ),
    operation("add_table", "add a table styled by the theme; the first row is the header", SLIDE_FIELD, *POSITION_FIELDS,
        Field("w", WIDTH, "width", required=True),
        Field("h", HEIGHT, "height; default 0.4 inch per row"),
        Field("rows", CELL_ROWS, "rows of cell values", required=True),
    ),
    operation("add_chart", "add a native chart with its own data workbook", SLIDE_FIELD, *BOX_FIELDS,
        Field("type", Choice(DECK_CHART_KINDS), "chart kind; combo draws the series marked line as lines over columns, scatter places points by number", required=True),
        Field("categories", ListOf(CellValue(), non_empty=True), "category labels along the axis; for scatter the x value of each point", required=True),
        Field("series", ListOf(CHART_SERIES, non_empty=True), "data series; pie and doughnut take one", required=True),
        Field("title", Text(), "chart title"),
        Field("legend", Boolean(), "show the legend; default when there is more than one series or a pie"),
        Field("colors", ListOf(HexColor()), "one color per series in order, or per slice of a pie or doughnut; the rest keep the theme's"),
        Field("dataLabels", Choice(tuple(LABEL_FLAGS)), "label each point with its value or category, or each slice of a pie or doughnut with its percent of the whole"),
        Field("xTitle", Text(), "category axis title, the x axis of a scatter"),
        Field("yTitle", Text(), "value axis title"),
        Field("secondaryAxis", Boolean(), "combo only: draw the lines against their own axis on the right; default when lines and columns differ more than tenfold"),
    ),
)
TABLE_AND_CHART_OPERATIONS = (
    operation("set_table_cell", "replace one table cell's text, keeping its formatting; format_table_cells styles it; name its row by index or label, and its column by index or label", SLIDE_FIELD, SHAPE_FIELD, *CELL_ADDRESS_FIELDS, TEXT_FIELD),
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
    operation("set_table_style", "pick a table's built-in style and the parts it emphasizes; fields left out keep their value, and cell formatting stays", SLIDE_FIELD, SHAPE_FIELD,
        Field("style", Choice(TABLE_STYLE_NAMES), "built-in style; an Accent style takes that theme color"),
        Field("firstRow", Boolean(), "emphasize the header row"),
        Field("lastRow", Boolean(), "emphasize the total row"),
        Field("firstCol", Boolean(), "emphasize the first column"),
        Field("lastCol", Boolean(), "emphasize the last column"),
        Field("bandRow", Boolean(), "shade every other row"),
        Field("bandCol", Boolean(), "shade every other column"),
    ),
    operation("format_table_cells", "fill, outline and restyle the text of a block of table cells; fields left out keep their value", SLIDE_FIELD, SHAPE_FIELD,
        Field("row", Number(minimum=0, integer=True), "first row of the block, from 0; default every row"),
        Field("rows", Number(minimum=1, integer=True), "how many rows from row, default 1"),
        Field("column", Number(minimum=0, integer=True), "first column of the block, from 0; default every column"),
        Field("columns", Number(minimum=1, integer=True), "how many columns from column, default 1"),
        Field("fill", HexColor(allows_none=True), "cell fill; none leaves the cells transparent"),
        *RUN_STYLE_FIELDS,
        Field("align", ALIGNMENT, "horizontal alignment"),
        Field("anchor", ANCHOR, "vertical position of the text in the cell"),
        Field("borderColor", HexColor(allows_none=True), "color of all four edges of each cell; none removes them"),
        Field("borderWidth", Number(minimum=0.25, maximum=20), "edge width in points, default 1"),
    ),
    operation("set_table_column_width", "set one column's width; the table grows or shrinks by the difference", SLIDE_FIELD, SHAPE_FIELD, TABLE_COLUMN,
        Field("width", WIDTH, "new column width", required=True),
    ),
    operation("set_table_row_height", "set one row's height; text taller than the row still grows it", SLIDE_FIELD, SHAPE_FIELD, TABLE_ROW,
        Field("height", HEIGHT, "new row height", required=True),
    ),
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
    operation("reorder", "put the slides in a new order, given as the numbers office read showed",
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
    operation("set_transition", "set how a slide comes in during the show",
        Field("slide", SLIDE_NUMBER, "only this slide; default every slide"),
        Field("kind", Choice(TRANSITION_KINDS), "none removes the transition", required=True),
        Field("speed", Choice(TRANSITION_SPEEDS), "default medium"),
        Field("advanceAfter", Number(minimum=0), "seconds before the show moves on by itself; default on click"),
    ),
    operation("add_animation", "make a shape enter the slide with an effect, after the slide's other animations", SLIDE_FIELD, SHAPE_FIELD,
        Field("effect", Choice(ANIMATION_EFFECTS), "entrance effect", required=True),
        Field("start", Choice(ANIMATION_STARTS), "default on_click"),
        Field("direction", Choice(DIRECTIONS), "where fly_in and wipe come from; default from_bottom"),
        Field("duration", Number(minimum=0, maximum=60), "seconds; default 0.5"),
        Field("delay", Number(minimum=0, maximum=60), "seconds after its start; default 0"),
    ),
    operation("remove_animations", "remove the animations of one shape, or of the whole slide", SLIDE_FIELD,
        Field("shape", ShapeAddress(), "only this shape's animations"),
    ),
    operation("add_comment", "add a review comment to a slide", SLIDE_FIELD,
        Field("text", Text(non_empty=True), "comment text", required=True),
        Field("author", Text(non_empty=True), "author name; default InternKim"),
        Field("x", X_LENGTH, "where the comment marker sits; default the top left"),
        Field("y", Y_LENGTH, "where the comment marker sits"),
    ),
    operation("set_header_footer", "show or hide the footer text, slide number and date",
        Field("slide", SLIDE_NUMBER, "only this slide; default every slide"),
        Field("footer", Text(), "footer text; empty text removes the footer"),
        Field("slideNumber", Boolean(), "show the slide number"),
        Field("date", Text(), "date text as it should read; empty text removes the date"),
    ),
)
SECTION_FIELD = Field("section", Text(non_empty=True), "section name as office read lists it", required=True)
SECTION_OPERATIONS = (
    operation("add_section", "start a named section at a slide; it runs to the next section", SLIDE_FIELD,
        Field("name", Text(non_empty=True), "section name", required=True),
    ),
    operation("rename_section", "rename a section", SECTION_FIELD,
        Field("name", Text(non_empty=True), "new name", required=True),
    ),
    operation("move_to_section", "move slides to the end of a section, in the order given",
        Field("slides", ListOf(SLIDE_NUMBER, non_empty=True), "slide numbers from office read", required=True),
        SECTION_FIELD,
    ),
    operation("remove_section", "remove a section; its slides join the section before it", SECTION_FIELD),
)
DECK_OPERATIONS = (
    operation("set_theme", "change the theme every slide inherits its colors and fonts from",
        Field("colors", MapOf(HexColor(), key="theme slot: " + ", ".join(THEME_SLOTS)), "colors by slot"),
        Field("headingFont", Text(non_empty=True), "Latin typeface for titles"),
        Field("bodyFont", Text(non_empty=True), "Latin typeface for body text"),
        Field("koreanFont", Text(non_empty=True), "typeface for Korean text in titles and body"),
    ),
    operation("set_slide_size", "change the slide size; 12192000 x 6858000 EMU (13.333in x 7.5in) is 16:9",
        Field("width", WIDTH, "slide width", required=True),
        Field("height", HEIGHT, "slide height", required=True),
        Field("scaleContent", Boolean(), "scale every shape with the slide, default true"),
    ),
)


OPERATIONS = Variant(
    "operation",
    "one edit of office apply; slide numbers, shape indexes and table rows refer to the deck as office read showed it before the batch, "
    "operations run in order, and the batch applies whole or not at all unless --mode says otherwise; a slide added in the batch is edited in the next batch; "
    f"a length is EMU ({EMU_PER_INCH} per inch, {EMU_PER_POINT} per point) or text with a unit such as {LENGTH_EXAMPLES} of the slide",
    "op",
    TEXT_OPERATIONS + ELEMENT_OPERATIONS + ARRANGE_OPERATIONS + INSERT_OPERATIONS + TABLE_AND_CHART_OPERATIONS + SLIDE_OPERATIONS + SECTION_OPERATIONS + DECK_OPERATIONS,
)

GUIDE_INPUTS = (
    ("apply", "pptx", "the operations", ListOf(OPERATIONS, non_empty=True)),
    ("merge", "pptx", "the values", MERGE_VALUES),
)
GUIDE_ISSUES = (
    ("apply", "pptx", OPERATION_ISSUE_KINDS + APPLY_ISSUE_KINDS + LAYOUT_AUDIT_ISSUE_KINDS),
    ("check", "pptx", (SLIDE_COUNT_MISMATCH,) + TEXT_CHECK_ISSUE_KINDS + LAYOUT_AUDIT_ISSUE_KINDS + PPTX_CHECK_ISSUE_KINDS),
    ("render", "pptx", PPTX_CHECK_ISSUE_KINDS),
    ("merge", "pptx", PACKAGE_MERGE_ISSUE_KINDS),
)
