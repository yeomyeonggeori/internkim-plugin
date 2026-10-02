from __future__ import annotations

from dataclasses import dataclass
import json

from charts.kinds import SHEET_CHART_TYPES
from charts.look import LABEL_FLAGS
from fonts.registry import OFFICE_KOREAN_FAMILY
from render.office_preview import PREVIEW_ISSUE_KINDS
from core.office_operations import OPERATION_ISSUE_KINDS
from core.template_merge import MERGE_VALUES, PACKAGE_MERGE_ISSUE_KINDS
from core.office_result import ERROR, INVALID_VALUE, WARNING, WRONG_TYPE, Issue, IssueKind
from core.excel_limits import CHART_TITLE_LIMIT, FORBIDDEN_SHEET_NAME_TEXT, HEADER_FOOTER_LIMIT, MAXIMUM_SHEET_NAME_LENGTH
from core.page_sizes import PAPER_NAMES
from core.office_schema import HEX_COLOR_PATTERN, AnyOf, Boolean, CellValue, Choice, Field, HexColor, ListOf, MapOf, Number, Record, Shape, Text, Variant, closest_name, color_problem, guess_text, wrong_type
from core.text_checks import PLACEHOLDER_LEFT, TEXT_CHECK_ISSUE_KINDS
from core.office_theme import THEME_SLOTS
from sheet.workbook.theme_colors import THEME_COLOR, theme_reference
from core.image_formats import PICTURE_FORMATS_TEXT


SHOWN_ROW_LIMIT = 4


@dataclass(frozen=True)
class Rows(ListOf):
    def problems(self, value: object, location: str) -> list[Issue]:
        if not isinstance(value, list) or not value or not all(isinstance(row, dict) for row in value):
            return super().problems(value, location)
        header = list(dict.fromkeys(key for row in value for key in row))
        reordered = [index for index, row in enumerate(value) if [key for key in header if key in row] != list(row)]
        listed = ", ".join(f"{location}[{index}]" for index in reordered[:SHOWN_ROW_LIMIT])
        order_note = f", and {listed} {'lists its' if len(reordered) == 1 else 'list their'} keys in another order" if reordered else ""
        converted = [header, *([row.get(key) for key in header] for row in value)]
        shown = json.dumps(converted[:SHOWN_ROW_LIMIT + 1], ensure_ascii=False) + (" and so on" if len(converted) > SHOWN_ROW_LIMIT + 1 else "")
        return [WRONG_TYPE.issue(
            f"{location}: rows are lists of cells, and these are objects keyed by header{order_note}",
            location,
            f"write the header once and every row as a list in the header's order: {shown}",
        )]


@dataclass(frozen=True)
class CellColor(Shape):
    label = "hex or theme color such as 1F4E79, accent1 or dk2-25%"
    accepted = "six hex digits, or a theme slot (" + " ".join(THEME_SLOTS) + ") with an optional tint such as accent1+40%"

    def problems(self, value: object, location: str) -> list[Issue]:
        if not isinstance(value, str):
            return [wrong_type(self, value, location)]
        if HEX_COLOR_PATTERN.fullmatch(value) or theme_reference(value) is not None:
            return []
        slot = THEME_COLOR.fullmatch(value.strip())
        nearest = closest_name(slot["slot"], THEME_SLOTS) if slot else None
        if nearest is None:
            return [color_problem(value, self.accepted, location)]
        written = value.strip()[len(slot["slot"]):]
        return [INVALID_VALUE.issue(f"{location}: {value!r} is not {self.accepted}{guess_text(nearest + written)}", location, f'use "{nearest + written}"')]


ROWS = Rows(ListOf(CellValue()))
READ_ROW_LIMIT = 500

SHEET = Record("sheet", "one worksheet; the first row, or the row after the heading, is the header", (
    Field("title", Text(non_empty=True), f"sheet name, at most {MAXIMUM_SHEET_NAME_LENGTH} characters, without {FORBIDDEN_SHEET_NAME_TEXT}", required=True),
    Field("heading", Text(), "bold title row above the table"),
    Field("rows", ROWS, "rows in order; text starting with = is a formula and YYYY-MM-DD is a date"),
    Field("csvPath", Text(non_empty=True), "read the rows from this CSV or TSV file instead of rows"),
    Field("delimiter", Text(non_empty=True), "csvPath delimiter, default comma; \\t for tab"),
    Field("freezePanes", Text(), "top-left unfrozen cell, default the cell under the header; empty text freezes nothing"),
    Field("autoFilter", Boolean(), "filter over the table, default true"),
    Field("columnWidths", MapOf(Number(minimum=0), key="column letter"), "width per column, at least 4"),
    Field("numberFormats", MapOf(Text(non_empty=True), key="column letter"), "Excel number format per column"),
))


SHEET_NAME = Field("sheet", Text(non_empty=True), "sheet name from office read, default the first sheet")
CELL_ADDRESS = Text(non_empty=True)
VALUE_TYPE = Field("type", Choice(("auto", "text")), "auto (default) stores text starting with = as a formula and YYYY-MM-DD as a date; text keeps it as literal text")
COUNT = Field("count", Number(minimum=1, integer=True), "how many, default 1")
RANGE = Field("range", CELL_ADDRESS, "range such as A1:D10, or one cell", required=True)
COLOR = Text(non_empty=True)
STYLE_COLOR = CellColor()
FIT_PAGES = AnyOf((Boolean(), Number(minimum=0, maximum=1000, integer=True)), name="true, false or a page count")
HIDDEN = Field("hidden", Boolean(), "true (default) hides, false shows again")
CHART_INDEX = Field("chart", Number(minimum=0, integer=True), "chart index on the sheet, from office read", required=True)
SHAPE_GEOMETRIES = {"rectangle": "rect", "rounded_rectangle": "roundRect", "ellipse": "ellipse", "arrow": "rightArrow", "callout": "wedgeRectCallout", "textbox": "rect"}
COMPARISON_OPERATORS = ("between", "not_between", "equal", "not_equal", "greater_than", "less_than", "greater_or_equal", "less_or_equal")
DATA_LABELS = tuple(LABEL_FLAGS)
CHART_FIELDS = (
    Field("title", Text(maximum_length=CHART_TITLE_LIMIT), f"chart title; Excel keeps at most {CHART_TITLE_LIMIT} characters in a chart or axis title"),
    Field("anchor", CELL_ADDRESS, "cell the chart's top-left corner sits on, default two columns right of the data"),
    Field("horizontal", Boolean(), "bar and combo: bars run sideways"),
    Field("stacked", AnyOf((Boolean(), Choice(("percent",))), name='true, false or "percent"'), "bar, area and line: stack the series; percent stacks each category to 100%"),
    Field("lineSeries", Number(minimum=1, integer=True), "combo: how many of the last series are lines, default 1"),
    Field("secondaryAxis", Boolean(), "combo: lines use a right-hand axis, default true"),
    Field("xTitle", Text(maximum_length=CHART_TITLE_LIMIT), "category axis title"),
    Field("yTitle", Text(maximum_length=CHART_TITLE_LIMIT), "value axis title"),
    Field("legend", Choice(("bottom", "right", "top", "none")), "legend position, default bottom; none hides it"),
    Field("dataLabels", AnyOf((Boolean(), Choice(DATA_LABELS)), name="true, false or " + ", ".join(DATA_LABELS)), "label each point with its value (true), its category, or on a pie or doughnut its percent of the whole or category_percent for both; false or none removes them"),
    Field("colors", ListOf(HexColor()), "one color per series in order, or per slice of a pie or doughnut, such as [\"1F4E79\", \"F59E0B\"]; series past the list take the default palette"),
    Field("width", Number(minimum=4, maximum=60), "width in centimetres, default 16"),
    Field("height", Number(minimum=3, maximum=40), "height in centimetres, default 8"),
)

PIVOT_FUNCTIONS = ("sum", "count", "average", "max", "min")
PIVOT_FIELDS = AnyOf((Text(non_empty=True), ListOf(Text(non_empty=True), non_empty=True)), name="header name or list of header names")
PIVOT_VALUE = AnyOf((Text(non_empty=True), Record("pivot value", "one summarized value of a pivot", (
    Field("field", Text(non_empty=True), "header to summarize; with formula, the new value's name", required=True),
    Field("function", Choice(PIVOT_FUNCTIONS), "how it combines, default the pivot's function"),
    Field("showAs", Choice(("value", "percent_of_total", "percent_of_row", "percent_of_column")), "value (default) or a share of the grand, row or column total"),
    Field("formula", Text(non_empty=True), "calculated value over other headers with + - * / ^ and parentheses, such as amount-cost; quote names with spaces: 'Unit Price'*qty"),
    Field("label", Text(non_empty=True), "caption, default Sum of <field> and so on"),
    Field("numberFormat", Text(non_empty=True), "number format, default the pivot's, or 0.0% for a percent"),
))), name="header name or pivot value")

PIVOT_NUMBER_GROUP = Record("number group", "bins of equal width over a number header", (
    Field("step", Number(minimum=0), "width of each bin, more than 0", required=True),
    Field("start", Number(), "lower bound of the first bin, default the smallest value rounded down to a multiple of step"),
))
PIVOT_TOP = Record("top items", "a top or bottom filter on a row or column header", (
    Field("field", Text(non_empty=True), "row or column header whose items are ranked", required=True),
    Field("count", Number(minimum=1, integer=True), "how many items stay", required=True),
    Field("bottom", Boolean(), "keep the smallest totals instead, default false"),
))

OPERATIONS = Variant(
    "operation",
    "one edit of office apply; operations run in order and each sees the workbook the ones before it left, and the batch applies whole or not at all unless --mode says otherwise",
    "op",
    (
        Record("set_cell", "write one cell; an unstyled cell in or touching a table of at least two rows and two columns takes the table's default style, the one office create gives every cell", (
            SHEET_NAME,
            Field("cell", CELL_ADDRESS, "cell address such as B7", required=True),
            Field("value", CellValue(), "number, text or true/false; text starting with = is a formula; omit or null to clear the cell"),
            VALUE_TYPE,
        )),
        Record("set_range", "write a block of values from its top-left cell; unstyled cells take the table's default style as set_cell describes", (
            SHEET_NAME,
            Field("cell", CELL_ADDRESS, "top-left cell address", required=True),
            Field("values", ROWS, "rows of values; each item follows set_cell's value", required=True),
            VALUE_TYPE,
        )),
        Record("append_rows", "write rows under the last filled row, from its first filled column, styled as set_cell describes", (
            SHEET_NAME,
            Field("rows", ROWS, "rows of values; each item follows set_cell's value", required=True),
            VALUE_TYPE,
        )),
        Record("format_range", "format every cell in a range; unnamed properties stay as they are", (
            SHEET_NAME,
            RANGE,
            Field("numberFormat", Text(non_empty=True), "Excel number format such as #,##0 or 0.0%"),
            Field("bold", Boolean(), "bold text on or off"),
            Field("italic", Boolean(), "italic text on or off"),
            Field("underline", Boolean(), "single underline on or off"),
            Field("strikethrough", Boolean(), "line through the text on or off"),
            Field("fontSize", Number(minimum=6, maximum=72), "font size in points"),
            Field("fontName", Text(non_empty=True), f"font family such as {OFFICE_KOREAN_FAMILY}"),
            Field("fontColor", STYLE_COLOR, "text color"),
            Field("fill", STYLE_COLOR, "background color such as DCEAF7 or accent1+80%"),
            Field("alignment", Choice(("left", "center", "right")), "horizontal alignment"),
            Field("verticalAlignment", Choice(("top", "center", "bottom")), "vertical alignment"),
            Field("indent", Number(minimum=0, maximum=15, integer=True), "indent level of left-aligned text"),
            Field("wrapText", Boolean(), "wrap long text inside the cell"),
            Field("textRotation", AnyOf((Number(minimum=-90, maximum=90, integer=True), Choice(("vertical",))), name='degrees from -90 to 90, or "vertical"'), "turn the text: positive degrees counterclockwise, negative clockwise, vertical stacks the letters"),
            Field("border", Choice(("all", "outline", "top", "bottom", "none")), "draw borders on every cell edge, around the range, on its top or bottom edge, or remove them"),
            Field("borderStyle", Choice(("thin", "medium", "thick", "dashed", "double")), "border line, default thin"),
            Field("borderColor", STYLE_COLOR, "border color, default 94A3B8"),
        )),
        Record("merge_cells", "merge a range into one cell that keeps the top-left value", (SHEET_NAME, RANGE)),
        Record("unmerge_cells", "split a merged range back into cells", (SHEET_NAME, RANGE)),
        Record("set_column_width", "set a column's width in characters; a Korean character counts as two", (
            SHEET_NAME,
            Field("column", Text(non_empty=True), "column letter such as C", required=True),
            Field("width", Number(minimum=4), "width in characters, at least 4", required=True),
        )),
        Record("set_row_height", "set the height of rows in points", (
            SHEET_NAME,
            Field("row", Number(minimum=1, integer=True), "first row number", required=True),
            Field("height", Number(minimum=3, maximum=409), "height in points, 15 is Excel's default", required=True),
            COUNT,
        )),
        Record("hide_rows", "hide rows, or show them with hidden false", (
            SHEET_NAME,
            Field("at", Number(minimum=1, integer=True), "first row number", required=True),
            COUNT,
            HIDDEN,
        )),
        Record("hide_columns", "hide columns, or show them with hidden false", (
            SHEET_NAME,
            Field("at", Text(non_empty=True), "first column letter", required=True),
            COUNT,
            HIDDEN,
        )),
        Record("hide_sheet", "hide a sheet, or show it with hidden false; one sheet always stays visible", (
            Field("sheet", Text(non_empty=True), "sheet name", required=True),
            HIDDEN,
        )),
        Record("freeze_panes", "freeze the rows above and the columns left of a cell", (
            SHEET_NAME,
            Field("cell", Text(), "top-left unfrozen cell such as A2; empty text unfreezes"),
        )),
        Record("set_auto_filter", "put a filter on a range's header row", (
            SHEET_NAME,
            Field("range", Text(), "header and data range such as A1:F40; empty text removes the filter"),
        )),
        Record("sort_range", "sort the rows of a range by one or two columns; formulas move with their rows", (
            SHEET_NAME,
            RANGE,
            Field("by", Text(non_empty=True), "column letter to sort by", required=True),
            Field("descending", Boolean(), "largest first, default false"),
            Field("thenBy", Text(non_empty=True), "column letter that breaks ties"),
            Field("thenDescending", Boolean(), "thenBy largest first"),
            Field("hasHeader", Boolean(), "the first row is a header that stays on top, default true"),
        )),
        Record("fill_range", "fill a range from its first row downward, or its first column rightward, the way dragging the fill handle does; formulas shift their relative references", (
            SHEET_NAME,
            Field("range", CELL_ADDRESS, "the first row or column and the cells to fill, such as C2:C40", required=True),
            Field("direction", Choice(("down", "right")), "down (default) copies the first row; right copies the first column"),
            Field("series", Boolean(), "count up from the first value: numbers and dates by step, text ending in a number by its number"),
            Field("step", Number(), "series: amount added per cell, default 1; days for dates"),
        )),
        Record("copy_range", "copy a block to another place, like copy and paste; formulas shift their relative references", (
            SHEET_NAME,
            Field("range", CELL_ADDRESS, "block to copy, such as A1:F20", required=True),
            Field("to", CELL_ADDRESS, "top-left cell of the destination", required=True),
            Field("toSheet", Text(non_empty=True), "sheet of the destination, default the same sheet"),
            Field("paste", Choice(("all", "values", "formats")), "all (default), values only with formulas turned into their results, or formats only"),
        )),
        Record("clear_range", "empty a range", (
            SHEET_NAME,
            RANGE,
            Field("what", Choice(("contents", "formats", "all")), "contents (default) keeps the formatting; formats keeps the values; all also removes links and notes"),
        )),
        Record("convert_to_values", "replace the formulas in a range with the values they compute", (
            SHEET_NAME,
            RANGE,
        )),
        Record("set_filter_criteria", "show only the rows whose cell in a filtered column holds one of the values, and hide the rest", (
            SHEET_NAME,
            Field("column", Text(non_empty=True), "column letter inside the sheet's filter", required=True),
            Field("values", ListOf(Text()), "values to show, matched as text ignoring case; empty or absent shows every row again"),
        )),
        Record("find_replace", "replace text in text cells, in formulas, or both", (
            Field("sheet", Text(non_empty=True), "sheet name, default every sheet"),
            Field("find", Text(non_empty=True), "text to find", required=True),
            Field("replace", Text(), "replacement text, empty to delete", required=True),
            Field("in", Choice(("values", "formulas", "all")), "where to look, default values"),
            Field("matchCase", Boolean(), "match upper and lower case exactly, default false"),
            Field("wholeCell", Boolean(), "replace only cells whose whole text equals find, default false"),
        )),
        Record("add_conditional_format", "color cells by a rule; highlight rules default to a light red fill with dark red text", (
            SHEET_NAME,
            RANGE,
            Field("rule", Choice(("greater_than", "less_than", "between", "equal", "not_equal", "greater_or_equal", "less_or_equal", "contains_text", "not_contains_text", "begins_with", "ends_with", "blank", "not_blank", "duplicate", "unique", "top", "bottom", "above_average", "below_average", "formula", "color_scale", "data_bar", "icon_set")), "what to color", required=True),
            Field("value", CellValue(), "number or text the rule compares with, or the text contains_text, begins_with and ends_with look for, ignoring case; text starting with = is a formula such as =$B$1"),
            Field("value2", CellValue(), "between: the upper bound"),
            Field("formula", Text(non_empty=True), "formula rule: true for cells to color, written for the range's top-left cell, such as =$E2<0"),
            Field("rank", Number(minimum=1, integer=True), "top and bottom: how many, default 10"),
            Field("percent", Boolean(), "top and bottom: rank is a percentage"),
            Field("fill", STYLE_COLOR, "highlight fill, default FFC7CE; data_bar bar color, default 638EC6"),
            Field("fontColor", STYLE_COLOR, "highlight text color, default 9C0006"),
            Field("bold", Boolean(), "highlight text bold"),
            Field("scale", Choice(("red_yellow_green", "green_yellow_red", "white_green", "white_red", "white_blue")), "color_scale colors from lowest to highest, default red_yellow_green"),
            Field("minColor", STYLE_COLOR, "color_scale: color of the lowest value, in place of the scale's"),
            Field("midColor", STYLE_COLOR, "color_scale: color of the middle, which makes three colors"),
            Field("maxColor", STYLE_COLOR, "color_scale: color of the highest value, in place of the scale's"),
            Field("minValue", Number(), "color_scale: the number that takes minColor, default the lowest value"),
            Field("midValue", Number(), "color_scale: the number that takes midColor, default the 50th percentile"),
            Field("maxValue", Number(), "color_scale: the number that takes maxColor, default the highest value"),
            Field("icons", Choice(("3_traffic_lights", "3_arrows", "3_flags", "3_symbols", "4_arrows", "4_rating", "5_arrows", "5_rating")), "icon_set icons, default 3_traffic_lights"),
        )),
        Record("clear_conditional_formats", "remove the conditional formats that overlap a range, or every one on the sheet", (
            SHEET_NAME,
            Field("range", Text(non_empty=True), "range such as B2:B40, default the whole sheet"),
        )),
        Record("add_data_validation", "limit what can be typed into a range; a list shows a dropdown", (
            SHEET_NAME,
            RANGE,
            Field("type", Choice(("list", "whole", "decimal", "date", "text_length", "custom")), "what is allowed", required=True),
            Field("values", ListOf(Text(non_empty=True)), "list: the choices, without commas"),
            Field("source", Text(non_empty=True), "list: a range holding the choices instead of values, such as =Lists!$A$2:$A$9"),
            Field("operator", Choice(COMPARISON_OPERATORS), "whole, decimal, date, text_length: how the value compares, default between when both bounds are given"),
            Field("minimum", CellValue(), "lower bound; a date is YYYY-MM-DD"),
            Field("maximum", CellValue(), "upper bound; a date is YYYY-MM-DD"),
            Field("formula", Text(non_empty=True), "custom: formula true for an allowed value, written for the top-left cell"),
            Field("allowBlank", Boolean(), "an empty cell is allowed, default true"),
            Field("prompt", Text(), "message shown when the cell is selected"),
            Field("error", Text(), "message shown when a value is refused"),
        )),
        Record("clear_data_validations", "remove the data validations that overlap a range", (SHEET_NAME, RANGE)),
        Record("add_table", "turn a block with a header row into an Excel table with banded rows and its own filter", (
            SHEET_NAME,
            RANGE,
            Field("name", Text(non_empty=True), "table name, letters, digits and underscores, default Table1, Table2 and so on"),
            Field("style", Text(non_empty=True), "Excel table style, default TableStyleMedium2"),
            Field("bandedRows", Boolean(), "shade every other row, default true"),
        )),
        Record("set_hyperlink", "make a cell a link to a web address, an email, or a place in the workbook", (
            SHEET_NAME,
            Field("cell", CELL_ADDRESS, "cell address", required=True),
            Field("url", Text(non_empty=True), "https:// or mailto: address, or #Sheet!A1 for a place in the workbook", required=True),
            Field("text", Text(), "text shown in the cell, default the cell's current value or the address"),
            Field("tooltip", Text(), "text shown on hover"),
        )),
        Record("set_comment", "attach a note to a cell, or remove it with empty text", (
            SHEET_NAME,
            Field("cell", CELL_ADDRESS, "cell address", required=True),
            Field("text", Text(), "note text; empty removes the note", required=True),
            Field("author", Text(), "author shown with the note"),
        )),
        Record("set_page_setup", "set how a sheet prints; unnamed properties stay as they are", (
            SHEET_NAME,
            Field("orientation", Choice(("portrait", "landscape")), "page orientation"),
            Field("paperSize", Choice(PAPER_NAMES), "paper size"),
            Field("fitToWidth", FIT_PAGES, "shrink the columns onto this many pages wide; true is one page, and 0 or false lets the width run on"),
            Field("fitToHeight", FIT_PAGES, "shrink the rows onto this many pages tall; true is one page, and 0 or false lets the length run on"),
            Field("printGridlines", Boolean(), "print the cell gridlines"),
            Field("printTitleRows", Text(), "rows repeated on every page such as 1:1; empty text removes them"),
            Field("printArea", Text(), "range to print such as A1:H40; empty text prints the used range"),
            Field("margins", Choice(("normal", "narrow", "wide")), "page margins"),
            Field("centerHorizontally", Boolean(), "center the printout between the side margins"),
            Field("pageNumbers", Boolean(), "print page X / Y in the footer"),
            Field("scale", Number(minimum=10, maximum=400, integer=True), "print at this percent of full size instead of fitting the width"),
            Field("header", Text(maximum_length=HEADER_FOOTER_LIMIT), f"text printed at the top of every page, at most {HEADER_FOOTER_LIMIT} characters as Excel allows; {{page}}, {{pages}}, {{date}}, {{sheet}} and {{file}} are filled in; empty text removes it"),
            Field("footer", Text(maximum_length=HEADER_FOOTER_LIMIT), "text printed at the bottom of every page, with header's placeholders and limit; empty text removes it"),
            Field("pageBreakRows", ListOf(Number(minimum=1, integer=True)), "rows after which a new page starts; an empty list removes them"),
            Field("pageBreakColumns", ListOf(Text(non_empty=True)), "column letters after which a new page starts; an empty list removes them"),
        )),
        Record("protect_sheet", "lock a sheet's cells against editing, or unlock it with protected false", (
            SHEET_NAME,
            Field("protected", Boolean(), "true (default) locks, false unlocks"),
            Field("password", Text(non_empty=True), "password asked to unlock it"),
        )),
        Record("add_sheet", "add an empty sheet", (
            Field("name", Text(non_empty=True), f"new sheet name, at most {MAXIMUM_SHEET_NAME_LENGTH} characters", required=True),
            Field("index", Number(minimum=0, integer=True), "position among the sheets, default last"),
        )),
        Record("delete_sheet", "delete a sheet; formulas, names and charts that read it show #REF!, which office check reports", (
            Field("sheet", Text(non_empty=True), "sheet name", required=True),
        )),
        Record("duplicate_sheet", "copy a sheet with its cells, styles, sizes, merges, conditional formats and validations right after it; charts, images, tables and pivots stay on the original", (
            Field("sheet", Text(non_empty=True), "sheet to copy", required=True),
            Field("name", Text(non_empty=True), "name of the copy, default the sheet name with (2)"),
        )),
        Record("move_sheet", "move a sheet to another position among the sheets", (
            Field("sheet", Text(non_empty=True), "sheet name", required=True),
            Field("index", Number(minimum=0, integer=True), "new position, 0 for first", required=True),
        )),
        Record("add_defined_name", "name a range or a constant so formulas can use the name; an existing name is replaced", (
            Field("name", Text(non_empty=True), "name such as TaxRate, starting with a letter", required=True),
            SHEET_NAME,
            Field("range", CELL_ADDRESS, "range the name stands for, such as B2:B20"),
            Field("value", CellValue(), "number or text the name stands for, instead of a range"),
            Field("local", Boolean(), "the name works only on its sheet, default the whole workbook"),
        )),
        Record("delete_defined_name", "remove a defined name; formulas that use it show #NAME?", (
            Field("name", Text(non_empty=True), "name from office read", required=True),
        )),
        Record("rename_sheet", "rename a sheet and rewrite every formula, defined name and chart reference to it", (
            Field("sheet", Text(non_empty=True), "current sheet name", required=True),
            Field("name", Text(non_empty=True), f"new sheet name, at most {MAXIMUM_SHEET_NAME_LENGTH} characters", required=True),
        )),
        Record("insert_rows", "insert empty rows before a row; formulas, absolute references, references from other sheets, defined names, filters, merged ranges, tables, charts, sparklines and shapes follow", (
            SHEET_NAME,
            Field("at", Number(minimum=1, integer=True), "row number the new rows are inserted before", required=True),
            COUNT,
        )),
        Record("delete_rows", "delete rows; references into them become #REF!, and ranges shrink", (
            SHEET_NAME,
            Field("at", Number(minimum=1, integer=True), "first row number to delete", required=True),
            COUNT,
        )),
        Record("insert_columns", "insert empty columns before a column, shifting references like insert_rows", (
            SHEET_NAME,
            Field("at", Text(non_empty=True), "column letter the new columns are inserted before", required=True),
            COUNT,
        )),
        Record("delete_columns", "delete columns, shifting references like delete_rows", (
            SHEET_NAME,
            Field("at", Text(non_empty=True), "first column letter to delete", required=True),
            COUNT,
        )),
        Record("recalculate", "store a freshly computed value for every formula the workbook can compute", ()),
        Record("add_chart", "add a chart of a block whose first column holds the categories and whose first row names the series; a column with no number is left out with a warning, and a block with none is refused; scatter uses the first column as x values", (
            SHEET_NAME,
            Field("type", Choice(SHEET_CHART_TYPES), "chart kind; combo draws the first series as bars and the last ones as lines", required=True),
            Field("range", CELL_ADDRESS, "data block including its header row and category column, such as A1:C7", required=True),
            *CHART_FIELDS,
        )),
        Record("edit_chart", "change a chart; unnamed properties stay, and type needs range", (
            SHEET_NAME,
            CHART_INDEX,
            Field("type", Choice(SHEET_CHART_TYPES), "new chart kind"),
            Field("range", CELL_ADDRESS, "new data block"),
            *CHART_FIELDS,
        )),
        Record("delete_chart", "remove a chart", (SHEET_NAME, CHART_INDEX)),
        Record("add_image", f"place a {PICTURE_FORMATS_TEXT} image with its top-left corner on a cell", (
            SHEET_NAME,
            Field("cell", CELL_ADDRESS, "cell the image's top-left corner sits on", required=True),
            Field("path", Text(non_empty=True), "image file path", required=True),
            Field("width", Number(minimum=1, maximum=60), "width in centimetres, default 8; the height keeps the image's proportions"),
        )),
        Record("add_shape", "draw a shape or text box with text, its top-left corner on a cell", (
            SHEET_NAME,
            Field("cell", CELL_ADDRESS, "cell the shape's top-left corner sits on", required=True),
            Field("shape", Choice(tuple(SHAPE_GEOMETRIES)), "kind of shape, default rectangle"),
            Field("text", Text(), "text inside; \\n starts a new line"),
            Field("fill", COLOR, "fill color, default DCEAF7; a textbox has none unless given"),
            Field("lineColor", COLOR, "outline color, default 2563EB"),
            Field("fontColor", COLOR, "text color, default 1F2937"),
            Field("fontSize", Number(minimum=6, maximum=72), "text size in points, default 11"),
            Field("bold", Boolean(), "bold text"),
            Field("width", Number(minimum=1, maximum=60), "width in centimetres, default 6"),
            Field("height", Number(minimum=0.5, maximum=40), "height in centimetres, default 2"),
        )),
        Record("add_sparklines", "draw one small chart per row of a block into the cells of a one-column target range", (
            SHEET_NAME,
            Field("range", CELL_ADDRESS, "data block, one row per sparkline, such as B2:M10", required=True),
            Field("target", CELL_ADDRESS, "cells that show them, one per data row, such as N2:N10", required=True),
            Field("type", Choice(("line", "column", "win_loss")), "sparkline kind, default line"),
            Field("color", COLOR, "series color, default 2563EB"),
            Field("markers", Boolean(), "line: mark every point"),
            Field("highLow", Boolean(), "mark the highest and lowest points"),
        )),
        Record("add_pivot_table", "summarize a block with a header row into a native pivot table whose numbers are filled in already", (
            SHEET_NAME,
            Field("range", CELL_ADDRESS, "source block including its header row", required=True),
            Field("row", PIVOT_FIELDS, "header whose values become the rows; a list nests them, outer first, with a subtotal row per outer item", required=True),
            Field("column", PIVOT_FIELDS, "header whose values become the columns, or a list, outer first; needs exactly one value"),
            Field("filters", ListOf(Text(non_empty=True)), "headers shown as report filters above the pivot, every item selected"),
            Field("values", ListOf(PIVOT_VALUE, non_empty=True), "what to summarize: header names, or objects for a per-value function, percent or formula", required=True),
            Field("function", Choice(PIVOT_FUNCTIONS), "how values given by name combine, default sum"),
            Field("groupDates", MapOf(Choice(("month", "quarter", "year")), key="row or column header"), "group a date header by month, quarter or year; every row needs a date"),
            Field("groupNumbers", MapOf(PIVOT_NUMBER_GROUP, key="row or column header"), "group a number header into bins of equal width, such as {\"Amount\": {\"step\": 1000000}}; every row needs a number"),
            Field("top", PIVOT_TOP, "keep only the items of one row or column header with the largest, or smallest, totals of the first value"),
            Field("targetSheet", Text(non_empty=True), "sheet the pivot goes on, created when missing, default a new sheet named Pivot"),
            Field("targetCell", CELL_ADDRESS, "top-left cell of the pivot, default A3"),
            Field("name", Text(non_empty=True), "pivot table name, default PivotTable1, PivotTable2 and so on"),
            Field("totalLabel", Text(non_empty=True), "caption of the total row and column, default Grand Total"),
            Field("numberFormat", Text(non_empty=True), "number format of the values, default #,##0"),
        )),
    ),
)
OPERATION_BATCH = ListOf(OPERATIONS, non_empty=True)

WORKBOOK_SPECIFICATION = Record("workbook", "the JSON spec office create builds an .xlsx from", (
    Field("title", Text(), "workbook title stored as document metadata; a visible title is a heading or row you write"),
    Field("sheets", ListOf(SHEET, non_empty=True), "the worksheets", required=True),
    Field("operations", ListOf(OPERATIONS), "operations, as office apply takes them, run on the new workbook, for charts, pivots, rules and print setup"),
))

FORMULA_NOT_EVALUATED = IssueKind("FORMULA_NOT_EVALUATED", WARNING, "a formula could not be computed here, so the file holds no value for it until Excel recalculates", "read the cells the formula uses; the formula itself was kept as written")
CIRCULAR_REFERENCE = IssueKind("CIRCULAR_REFERENCE", ERROR, "a formula reads its own cell, directly or through other formulas, so Excel warns on open and shows 0; office create and office apply write nothing when their own cells make one", "point the formula at the cells beside it, such as =SUM(A2:A9) in A10")
FORMULA_SYNTAX = IssueKind("FORMULA_SYNTAX", ERROR, "a formula does not parse: a ( or { left open, a ) that closes nothing, an operator with nothing on one side, or an unclosed quote, so nothing was written", "fix the formula where the message says, or keep it as literal text with \"type\": \"text\"")
HEADER_NOT_FROZEN = IssueKind("HEADER_NOT_FROZEN", WARNING, "a data table, a sheet with at least two header cells and at least 10 rows under them, has a header row that is not frozen", "freeze the pane under the header row")
AUTO_FILTER_MISSING = IssueKind("AUTO_FILTER_MISSING", WARNING, "a data table, a sheet with at least two header cells and at least 10 rows under them, has no auto filter", "add a filter over the header and data rows")
BLANK_HEADER_CELLS = IssueKind("BLANK_HEADER_CELLS", WARNING, "header cells are blank", "name every column")
STALE_CACHED_VALUE = IssueKind("STALE_CACHED_VALUE", WARNING, "a formula's stored value differs from what the formula computes, so a viewer that does not recalculate shows the wrong number", "apply recalculate")
FORMULA_ERROR = IssueKind("FORMULA_ERROR", ERROR, "a formula computes #DIV/0!, #REF!, #NAME?, #VALUE! or #N/A", "fix the formula's references or the cells it reads, with set_cell")
MISSING_SHEET_REFERENCE = IssueKind("MISSING_SHEET_REFERENCE", ERROR, "a formula reads a sheet the workbook does not have; office create and office apply write nothing when their own formulas do", "add the sheet first, or point the formula at an existing one")
UNKNOWN_FUNCTION = IssueKind("UNKNOWN_FUNCTION", ERROR, "a formula calls a function Excel does not have, so it shows #NAME?; office create and office apply write nothing when their own formulas do", "write the Excel function the message names, such as SUM for SUMM")
BROKEN_DEFINED_NAME = IssueKind("BROKEN_DEFINED_NAME", ERROR, "a defined name points at #REF! or a sheet the workbook does not have", "read the workbook's defined names and recreate the reference")
CONTENT_WOULD_BE_LOST = IssueKind("CONTENT_WOULD_BE_LOST", ERROR, "the workbook holds content the editor cannot carry through a save, such as form controls, embedded objects or an unknown extension, so nothing was written", "pass --allow-loss to save without it, or leave this workbook to Excel")
CONTENT_DROPPED = IssueKind("CONTENT_DROPPED", WARNING, "--allow-loss saved the workbook without content the editor cannot carry", "tell the user what was dropped")
VALUE_STORED_AS_TEXT = IssueKind("VALUE_STORED_AS_TEXT", WARNING, "a cell holds text that reads as a number, a date or a formula missing its =, so sums, sorting, filters and charts treat it as words", "apply the operations in fix: they write the typed value or formula and keep how it looked", suggestion_applies_fix=True)
CHART_REFERENCE_BROKEN = IssueKind("CHART_REFERENCE_BROKEN", ERROR, "a chart series reads a sheet the workbook does not have, a range with no values, or values that hold no number, so the chart draws nothing for it", "read the sheet and point the chart at its data with edit_chart and range")
CHART_COLUMN_LEFT_OUT = IssueKind("CHART_COLUMN_LEFT_OUT", WARNING, "a column of a chart's range, other than its first, holds no number, so the chart leaves it out instead of drawing an empty series", "apply the operations in fix: numbers stored as text are converted and the chart rebuilt, and a text column is left out of the range; or leave it as it is", suggestion_applies_fix=True)
PIVOT_VALUES_EMPTY = IssueKind("PIVOT_VALUES_EMPTY", ERROR, "a pivot table's value cells are all empty, which is what summing a column of numbers stored as text gives", "convert the source column to numbers with the operations in its VALUE_STORED_AS_TEXT fix, delete the pivot's sheet with delete_sheet, and add the pivot again")
READABLE_PRINT_POINTS = 8
PRINT_LAYOUT_FIX = "apply the operations in fix: they move a chart that sits beside the data under it, then fit the columns onto the fewest pages wide, in landscape when that keeps fewer, at which body text prints at a readable size"
SHEET_PRINTS_WIDE = IssueKind("SHEET_PRINTS_WIDE", WARNING, "a sheet's columns print across more than one page wide, so each printed row is cut apart onto separate sheets of paper", PRINT_LAYOUT_FIX, suggestion_applies_fix=True)
SHEET_PRINTS_SMALL = IssueKind("SHEET_PRINTS_SMALL", WARNING, f"a sheet's print scale, from fitting it to pages or set outright, shrinks its body text under {READABLE_PRINT_POINTS} pt, too small to read on paper", PRINT_LAYOUT_FIX, suggestion_applies_fix=True)
NUMBER_TOO_WIDE = IssueKind("NUMBER_TOO_WIDE", ERROR, "a number is wider than its column and Excel shows it as ####", "apply the set_column_width in fix", suggestion_applies_fix=True)

PRINT_LAYOUT_ISSUE_KINDS = (SHEET_PRINTS_WIDE, SHEET_PRINTS_SMALL)
TABLE_CHECK_ISSUE_KINDS = (
    HEADER_NOT_FROZEN,
    AUTO_FILTER_MISSING,
    BLANK_HEADER_CELLS,
)
CHECK_ISSUE_KINDS = (
    STALE_CACHED_VALUE,
    FORMULA_ERROR,
    MISSING_SHEET_REFERENCE,
    UNKNOWN_FUNCTION,
    BROKEN_DEFINED_NAME,
    NUMBER_TOO_WIDE,
    VALUE_STORED_AS_TEXT,
    CHART_REFERENCE_BROKEN,
    PIVOT_VALUES_EMPTY,
    PLACEHOLDER_LEFT,
    CIRCULAR_REFERENCE,
    FORMULA_NOT_EVALUATED,
    *PRINT_LAYOUT_ISSUE_KINDS,
)

GUIDE_INPUTS = (
    ("create", "xlsx", "the JSON spec", WORKBOOK_SPECIFICATION),
    ("apply", "xlsx", "the operations", OPERATION_BATCH),
    ("merge", "xlsx", "the values", MERGE_VALUES),
)


def behavior_lines() -> list[str]:
    return [
        "  formulas are stored exactly as written: write each reference for the row it lands in, counting a heading row",
        "  each formula also stores the value it computes, so viewers that never recalculate show numbers; a formula that cannot be computed here keeps no value and is reported as FORMULA_NOT_EVALUATED",
        "  the spec title is document metadata; nothing is added to the sheet unless you write it, such as a heading",
        "  CSV values become numbers when they are plain integers or decimals; 007, +82, 1,500 and anything over 15 digits stay text; text that is exactly YYYY-MM-DD becomes a date wherever it is written, unless set_cell or set_range says \"type\": \"text\"",
        "  office apply writes the whole batch or nothing; --dry-run lists the changes and --output leaves the source alone",
        "  inserting, deleting and renaming rewrite every formula, defined name, filter, merged range, table, chart series, sparkline and shape that points at the cells; a reference into a deleted row becomes #REF!",
        "  edits keep macros, sparklines, slicers, shapes, Excel extensions and unknown parts; content no edit can carry stops the save with CONTENT_WOULD_BE_LOST",
    ]


GUIDE_SECTIONS = (("xlsx", "How the commands treat a workbook", behavior_lines),)

WRITE_ISSUE_KINDS = (FORMULA_SYNTAX, UNKNOWN_FUNCTION, MISSING_SHEET_REFERENCE, CIRCULAR_REFERENCE, FORMULA_NOT_EVALUATED, CHART_COLUMN_LEFT_OUT)
EDIT_ISSUE_KINDS = (CONTENT_WOULD_BE_LOST, CONTENT_DROPPED)
GUIDE_ISSUES = (
    ("create", "xlsx", WRITE_ISSUE_KINDS),
    ("create", "csv", WRITE_ISSUE_KINDS + PRINT_LAYOUT_ISSUE_KINDS),
    ("apply", "xlsx", WRITE_ISSUE_KINDS + EDIT_ISSUE_KINDS + OPERATION_ISSUE_KINDS),
    ("check", "xlsx", CHECK_ISSUE_KINDS + TABLE_CHECK_ISSUE_KINDS + TEXT_CHECK_ISSUE_KINDS),
    ("render", "xlsx", PREVIEW_ISSUE_KINDS + PRINT_LAYOUT_ISSUE_KINDS),
    ("merge", "xlsx", PACKAGE_MERGE_ISSUE_KINDS + WRITE_ISSUE_KINDS),
)
