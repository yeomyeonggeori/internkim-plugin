from __future__ import annotations

from charts.kinds import DOCUMENT_CHART_KINDS
from fonts.registry import BODY_SIZE_POINTS, MONOSPACE, SANS_BODY, default_family
from office_preview import PREVIEW_ISSUE_KINDS
from office_operations import OPERATION_ISSUE_KINDS
from office_result import ERROR, WARNING, IssueKind
from page_sizes import PAPER_NAMES
from office_schema import AnyOf, Boolean, CellValue, Choice, Field, HexColor, ListOf, MapOf, Number, Record, Text, Variant
from template_merge import LIST_NEEDS_A_ROW, MERGE_VALUES, TEMPLATE_SYNTAX_ERROR, UNRESOLVED_PLACEHOLDER, UNUSED_VALUE
from text_checks import FORBIDDEN_TEXT_PRESENT, PLACEHOLDER_LEFT, REQUIRED_TEXT_MISSING
from image_formats import PICTURE_FORMATS_TEXT


DOCUMENT_FONT = default_family(SANS_BODY).name


REVISION_TYPES = ("insertion", "deletion", "move", "formatting")
TABLE_ROWS = ListOf(ListOf(CellValue()), non_empty=True)

BLOCK = Variant(
    "block",
    "one piece of document content, in reading order",
    "type",
    (
        Record("heading", "a heading", (
            Field("text", Text(), "heading text"),
            Field("level", Number(1, 4, integer=True), "heading depth, default 1"),
        )),
        Record("paragraph", "a body paragraph", (
            Field("text", Text(), "paragraph text"),
        )),
        Record("bullets", "a bulleted list", (
            Field("items", ListOf(Text(non_empty=True)), "one entry per bullet"),
        )),
        Record("numbered", "a numbered list", (
            Field("items", ListOf(Text(non_empty=True)), "one entry per item"),
        )),
        Record("table", "a bordered table whose first row is the shaded header", (
            Field("rows", TABLE_ROWS, "every row the same width, header row first", required=True),
            Field("style", Text(), "Word table style name, default Table Grid"),
            Field("columnWidthsInches", ListOf(Number(minimum=0)), "one width per column; ignored unless it matches the row width"),
        )),
        Record("pageBreak", "start a new page", ()),
    ),
)

PAGE = Record("page", "page setup on A4", (
    Field("orientation", Choice(("portrait", "landscape")), "default portrait"),
    Field("marginInches", Number(minimum=0), "every margin, default 1"),
))

DOCUMENT_SPECIFICATION = Record("document", "the --spec file of doc create", (
    Field("title", Text(), "centered title above the first block"),
    Field("fontName", Text(non_empty=True), f"font for body and headings, default {DOCUMENT_FONT}"),
    Field("fontSize", Number(minimum=1), f"body size in points, default {BODY_SIZE_POINTS}"),
    Field("page", PAGE, "page setup"),
    Field("blocks", ListOf(BLOCK, non_empty=True), "the content", required=True),
))

BLOCK_LIST = ListOf(BLOCK)

TABLE_FILE_ROWS = AnyOf((
    ListOf(ListOf(CellValue()), non_empty=True),
    ListOf(MapOf(CellValue(), key="column header"), non_empty=True),
), name="rows: a list of row lists, or a list of objects keyed by column header")

TABLE_FILE = AnyOf((
    TABLE_FILE_ROWS,
    Record("table file", "rows with column widths", (
        Field("rows", TABLE_FILE_ROWS, "the rows", required=True),
        Field("columnWidthsInches", ListOf(Number(minimum=0)), "one width per column"),
    )),
), name="rows, or a table file object")

DOCUMENT_EMPTY = IssueKind("DOCUMENT_EMPTY", ERROR, "the document has no visible paragraph text", "add the content blocks, then rebuild")
DOCUMENT_SPARSE = IssueKind("DOCUMENT_SPARSE", WARNING, "the document has fewer than three visible paragraphs", "check that every section of the source made it in")
BODY_SIZE_UNUSUAL = IssueKind("BODY_SIZE_UNUSUAL", WARNING, "normal text is outside 9-12.5 pt", "set the body size to about 10-11 pt")
LINE_SPACING_UNUSUAL = IssueKind("LINE_SPACING_UNUSUAL", WARNING, "normal line spacing is outside 1.0-1.25", "set line spacing to about 1.05-1.2")
MARGIN_TOO_NARROW = IssueKind("MARGIN_TOO_NARROW", WARNING, "a section margin is under 0.5 inch", "widen the margin to 0.7-1 inch")
MARGIN_TOO_WIDE = IssueKind("MARGIN_TOO_WIDE", WARNING, "a section margin is over 1.25 inches", "narrow the margin to 0.7-1 inch")
NO_STRUCTURED_TABLE = IssueKind("NO_STRUCTURED_TABLE", WARNING, "no table has more than one row", "put structured facts in a real table when the source has them")
TABLE_TOO_WIDE = IssueKind("TABLE_TOO_WIDE", WARNING, "a table has more than five columns", "split the table or move detail columns out")
TABLE_EMPTY_CELLS = IssueKind("TABLE_EMPTY_CELLS", WARNING, "a table has empty cells", "fill the cells, or write the user's-language equivalent of Not provided")
TABLE_DENSE_CELLS = IssueKind("TABLE_DENSE_CELLS", WARNING, "a table has cells over 90 characters", "shorten the cell text or widen the column")

VALIDATE_ISSUE_KINDS = (
    DOCUMENT_EMPTY,
    DOCUMENT_SPARSE,
    REQUIRED_TEXT_MISSING,
    FORBIDDEN_TEXT_PRESENT,
    BODY_SIZE_UNUSUAL,
    LINE_SPACING_UNUSUAL,
    MARGIN_TOO_NARROW,
    MARGIN_TOO_WIDE,
    NO_STRUCTURED_TABLE,
    TABLE_TOO_WIDE,
    TABLE_EMPTY_CELLS,
    TABLE_DENSE_CELLS,
)

BLOCK_INDEX = Number(minimum=0, integer=True)
INSERT_AFTER = Field("after", BLOCK_INDEX, "insert after this block index from doc read")
INSERT_BEFORE = Field("before", BLOCK_INDEX, "insert before this block index")
INSERT_AT = Field("at", Choice(("start", "end")), "insert at the start or the end of the body; give one of after, before and at")
TARGET_BLOCK = Field("block", BLOCK_INDEX, "block index from doc read", required=True)
TABLE_BLOCK = Field("block", BLOCK_INDEX, "index of a table block from doc read", required=True)
ROW_INDEX = Number(minimum=0, integer=True)

ALIGNMENT = Choice(("left", "center", "right", "justify"))
HIGHLIGHT_COLORS = ("yellow", "green", "cyan", "pink", "blue", "red", "gray", "none")
CELL_RANGE = (
    TABLE_BLOCK,
    Field("row", ROW_INDEX, "first row index", required=True),
    Field("column", ROW_INDEX, "first column index", required=True),
    Field("toRow", ROW_INDEX, "last row index, default row"),
    Field("toColumn", ROW_INDEX, "last column index, default column"),
)
CHARACTER_FORMAT = (
    Field("bold", Boolean(), "bold"),
    Field("italic", Boolean(), "italic"),
    Field("underline", Boolean(), "underline"),
    Field("color", HexColor(), "text color"),
    Field("size", Number(1, 400), "size in points"),
    Field("font", Text(non_empty=True), "font name for Latin and Korean text"),
)
PARAGRAPH_FORMAT = (
    Field("align", ALIGNMENT, "alignment"),
    Field("spaceBeforePoints", Number(minimum=0), "space above"),
    Field("spaceAfterPoints", Number(minimum=0), "space below"),
)
AFTER_TEXT = Field("afterText", Text(non_empty=True), "exact text in the block the mark follows; default the block's end")
NOTE_FIELDS = (
    TARGET_BLOCK,
    Field("text", Text(non_empty=True), "note text", required=True),
    AFTER_TEXT,
)
HEADER_FOOTER_FIELDS = (
    Field("text", Text(), "the text", required=True),
    Field("section", Number(minimum=0, integer=True), "section index, default 0"),
    Field("page", Choice(("default", "first", "even")), "which pages: first turns on a different first page, even a different even page; default every page"),
    Field("align", ALIGNMENT, "alignment"),
)
WRAPS = ("inline", "square", "topAndBottom", "behindText", "inFrontOfText")
WRAP_FIELD = Field("wrap", Choice(WRAPS), "inline sits in the text line; square and topAndBottom float with text around or above and below; behindText and inFrontOfText float over the text")
FIELD_KINDS = ("DATE", "TIME", "CREATEDATE", "SAVEDATE", "PAGE", "NUMPAGES", "SECTIONPAGES", "AUTHOR", "TITLE", "SUBJECT", "FILENAME", "NUMWORDS", "SEQ")
NOTE_KIND = Field("kind", Choice(("footnote", "endnote")), "which kind of note", required=True)
NOTE_ID = Field("note", Number(minimum=1, integer=True), "note id from doc read", required=True)
TO_BLOCK = Field("toBlock", BLOCK_INDEX, "last block of the range, default block")
MARKDOWN = Field("markdown", Text(non_empty=True), "Markdown: # headings, paragraphs, - or 1. lists, | tables |, > quotes, ![alt](local path) pictures and ```chart blocks", required=True)
CHART_SERIES = Record("series", "one data series", (
    Field("name", Text(non_empty=True), "series name shown in the legend", required=True),
    Field("values", ListOf(Number(), non_empty=True), "one plain number per category; the unit goes in the title", required=True),
    Field("line", Boolean(), "combo only: draw this series as a line over the columns"),
))
CHART_DATA = (
    Field("categories", ListOf(CellValue(), non_empty=True), "category labels along the axis, or slice names of a pie"),
    Field("series", ListOf(CHART_SERIES, non_empty=True), "data series; pie and doughnut take one"),
    Field("title", Text(), "chart title, with the unit, such as 분기 매출 (억 원)"),
    Field("legend", Boolean(), "show the legend; default when there is more than one series or a pie"),
    Field("secondaryAxis", Boolean(), "combo only: draw the lines against their own axis on the right; default when lines and columns differ more than tenfold"),
)
CHART_INDEX = Field("chart", Number(minimum=0, integer=True), "chart index from doc read", required=True)
COMMENT_ID = Field("comment", Number(minimum=0, integer=True), "comment id from doc read", required=True)
REVISION_SELECTOR = (
    Field("all", Boolean(), "every tracked change"),
    Field("ids", ListOf(Text(non_empty=True)), "revision ids from doc read --revisions, such as r1; ids are renumbered after every edit"),
    Field("author", Text(non_empty=True), "only changes by this author"),
    Field("type", Choice(REVISION_TYPES), "only this kind of change"),
    Field("block", BLOCK_INDEX, "only changes in this block"),
)

OPERATIONS = Variant(
    "operation",
    "one edit of doc apply; every index refers to the document as doc read showed it before the batch, and the batch applies whole or not at all",
    "op",
    (
        Record("replace_text", "replace every occurrence of text, keeping the formatting of the run the match starts in", (
            Field("find", Text(non_empty=True), "exact text to find; it must occur at least once", required=True),
            Field("replace", Text(), "replacement text", required=True),
            Field("block", BLOCK_INDEX, "only this block; default the whole body and every table"),
        )),
        Record("set_text", "replace a paragraph's text, keeping its first run's formatting", (
            TARGET_BLOCK,
            Field("text", Text(), "new text", required=True),
        )),
        Record("insert_paragraph", "insert a paragraph", (
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
            Field("text", Text(), "paragraph text", required=True),
            Field("style", Text(non_empty=True), "paragraph style name, default Normal"),
        )),
        Record("insert_heading", "insert a heading", (
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
            Field("text", Text(), "heading text", required=True),
            Field("level", Number(1, 9, integer=True), "heading depth, default 1"),
        )),
        Record("insert_list", "insert list items", (
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
            Field("items", ListOf(Text(non_empty=True), non_empty=True), "one entry per item", required=True),
            Field("numbered", Boolean(), "numbered instead of bulleted"),
        )),
        Record("insert_table", "insert a table", (
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
            Field("rows", TABLE_ROWS, "every row the same width, header row first", required=True),
            Field("style", Text(non_empty=True), "table style name, default Table Grid"),
        )),
        Record("insert_page_break", "insert a page break", (INSERT_AFTER, INSERT_BEFORE)),
        Record("delete_block", "delete a block", (TARGET_BLOCK,)),
        Record("set_style", "set a paragraph or table style that the document defines", (
            TARGET_BLOCK,
            Field("style", Text(non_empty=True), "a style name from doc read's paragraphStyles or tableStyles", required=True),
        )),
        Record("set_cell", "replace one table cell's text", (
            TABLE_BLOCK,
            Field("row", ROW_INDEX, "row index", required=True),
            Field("column", ROW_INDEX, "column index", required=True),
            Field("text", Text(), "new text", required=True),
        )),
        Record("insert_table_row", "insert a row copying the formatting of the row it follows", (
            TABLE_BLOCK,
            Field("after", Number(minimum=0, integer=True), "insert after this row index", required=True),
            Field("cells", ListOf(CellValue()), "one value per column; missing cells stay empty", required=True),
        )),
        Record("delete_table_row", "delete a table row", (
            TABLE_BLOCK,
            Field("row", ROW_INDEX, "row index", required=True),
        )),
        Record("insert_table_column", "insert a column copying the formatting of the column it follows; the table keeps its width", (
            TABLE_BLOCK,
            Field("after", ROW_INDEX, "insert after this column index"),
            Field("at", Choice(("start", "end")), "insert as the first or the last column; give after or at"),
            Field("cells", ListOf(CellValue()), "one value per row, header first; missing cells stay empty"),
        )),
        Record("delete_table_column", "delete a column; the others widen to keep the table's width", (
            TABLE_BLOCK,
            Field("column", ROW_INDEX, "column index", required=True),
        )),
        Record("merge_cells", "merge a rectangle of cells into one, keeping each cell's text", CELL_RANGE),
        Record("split_table_cell", "split a merged cell back into the cells it covers; its text stays in the first", (
            TABLE_BLOCK,
            Field("row", ROW_INDEX, "row index of any cell in the merge", required=True),
            Field("column", ROW_INDEX, "column index of any cell in the merge", required=True),
        )),
        Record("format_cells", "shade, bold or align a rectangle of cells", CELL_RANGE + (
            Field("fill", HexColor(), "background color"),
            Field("bold", Boolean(), "bold text"),
            Field("align", ALIGNMENT, "horizontal alignment"),
            Field("verticalAlign", Choice(("top", "center", "bottom")), "vertical alignment"),
        )),
        Record("format_text", "set character formatting on a block, on every occurrence of exact text, or both", (
            Field("block", BLOCK_INDEX, "only this block; give block, find, or both"),
            Field("find", Text(non_empty=True), "exact text to format; default the whole block"),
            *CHARACTER_FORMAT,
            Field("strike", Boolean(), "strikethrough"),
            Field("highlight", Choice(HIGHLIGHT_COLORS), "highlighter color; none removes it"),
        )),
        Record("set_paragraph_format", "set a paragraph's alignment, spacing, indents and pagination", (
            TARGET_BLOCK,
            *PARAGRAPH_FORMAT,
            Field("lineSpacing", Number(0.5, 5), "line spacing as a multiple, such as 1.15"),
            Field("indentLeftInches", Number(minimum=0), "left indent"),
            Field("firstLineIndentInches", Number(), "first-line indent; negative hangs"),
            Field("keepWithNext", Boolean(), "keep on the same page as the next paragraph"),
            Field("pageBreakBefore", Boolean(), "start the paragraph on a new page"),
        )),
        Record("define_style", "create a paragraph or character style, or change the given fields of an existing one; later operations in the batch can use it", (
            Field("name", Text(non_empty=True), "style name", required=True),
            Field("type", Choice(("paragraph", "character")), "default paragraph"),
            Field("basedOn", Text(non_empty=True), "style it inherits from, such as Normal"),
            *CHARACTER_FORMAT,
            *PARAGRAPH_FORMAT,
        )),
        Record("insert_image", "insert a picture as its own paragraph, scaled down to the text width unless a size is given", (
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
            Field("path", Text(non_empty=True), f"{PICTURE_FORMATS_TEXT} file", required=True),
            Field("widthInches", Number(minimum=0.1), "width; the height keeps the aspect ratio unless also given"),
            Field("heightInches", Number(minimum=0.1), "height"),
            Field("align", ALIGNMENT, "paragraph alignment"),
            Field("description", Text(), "alt text read aloud by screen readers"),
            WRAP_FIELD,
        )),
        Record("set_image_properties", "resize a picture, change its alt text, or float it with text wrapping", (
            TARGET_BLOCK,
            Field("picture", Number(minimum=0, integer=True), "which picture in the block, default 0"),
            Field("widthInches", Number(minimum=0.1), "width; the height keeps the aspect ratio unless also given"),
            Field("heightInches", Number(minimum=0.1), "height"),
            Field("description", Text(), "alt text read aloud by screen readers"),
            WRAP_FIELD,
            Field("align", ALIGNMENT, "horizontal position: the paragraph's alignment when inline, the margin side when floating"),
        )),
        Record("insert_text_box", "insert a bordered box of text that floats beside or between paragraphs", (
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
            Field("text", Text(non_empty=True), "box text; a line break starts a new paragraph", required=True),
            Field("widthInches", Number(minimum=0.5), "width, default half the text width"),
            Field("heightInches", Number(minimum=0.3), "height, default enough for the lines"),
            Field("wrap", Choice(WRAPS), "default square, text flowing around the box"),
            Field("align", ALIGNMENT, "margin side the box sits on, default left"),
            Field("fill", HexColor(), "background color, default none"),
            Field("border", Boolean(), "draw a gray border, default true"),
        )),
        Record("insert_equation", "insert an equation written in LaTeX as a native Word equation", (
            Field("latex", Text(non_empty=True), "LaTeX without dollar signs, such as \\frac{a+b}{2}", required=True),
            Field("block", BLOCK_INDEX, "put the equation inside this paragraph; leave out for an equation on its own centered line"),
            AFTER_TEXT,
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
        )),
        Record("insert_field", "insert a field Word keeps current, such as today's date, the page number or a figure number", (
            TARGET_BLOCK,
            Field("field", Choice(FIELD_KINDS), "SEQ numbers a named sequence such as figures", required=True),
            Field("format", Text(non_empty=True), "DATE, TIME, CREATEDATE and SAVEDATE: a picture such as yyyy-MM-dd or HH:mm"),
            Field("sequence", Text(non_empty=True), "SEQ only: the sequence name, such as 그림"),
            AFTER_TEXT,
        )),
        Record("move_blocks", "move blocks, keeping their order, to another place", (
            Field("blocks", ListOf(BLOCK_INDEX, non_empty=True), "block indexes to move", required=True),
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
        )),
        Record("set_list", "make a range of paragraphs one new bulleted or numbered list; headings in the range stay headings", (
            TARGET_BLOCK,
            TO_BLOCK,
            Field("numbered", Boolean(), "numbered from 1 instead of bulleted"),
            Field("level", Number(0, 2, integer=True), "nesting level, default 0"),
        )),
        Record("clear_list", "make the list items in a range plain body paragraphs", (TARGET_BLOCK, TO_BLOCK)),
        Record("insert_markdown", "insert content written in Markdown, styled with the document's own styles", (
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
            MARKDOWN,
        )),
        Record("replace_blocks", "replace a range of blocks with content written in Markdown", (TARGET_BLOCK, TO_BLOCK, MARKDOWN)),
        Record("edit_note", "replace a footnote's or endnote's text", (
            NOTE_KIND,
            NOTE_ID,
            Field("text", Text(non_empty=True), "new note text", required=True),
        )),
        Record("delete_note", "delete a footnote or endnote and its mark in the text", (NOTE_KIND, NOTE_ID)),
        Record("insert_chart", "insert a native Word chart with its own data workbook as its own paragraph, as wide as the text unless a size is given", (
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
            Field("type", Choice(DOCUMENT_CHART_KINDS), "chart kind; combo draws columns with the series marked line as lines", required=True),
            *(field if field.name not in ("categories", "series") else Field(field.name, field.shape, field.description, required=True) for field in CHART_DATA),
            Field("widthInches", Number(minimum=1), "width; default the text width"),
            Field("heightInches", Number(minimum=1), "height; default a little over half the width"),
            Field("align", ALIGNMENT, "paragraph alignment"),
        )),
        Record("edit_chart", "change a chart's kind, data, title or legend; fields left out keep their current value", (
            CHART_INDEX,
            Field("type", Choice(DOCUMENT_CHART_KINDS), "chart kind"),
            *CHART_DATA,
        )),
        Record("delete_chart", "delete a chart, and its paragraph when nothing else is in it", (CHART_INDEX,)),
        Record("insert_table_of_contents", "insert a table of contents field listing the headings now in the document; Word fills in page numbers when the file opens", (
            INSERT_AFTER,
            INSERT_BEFORE,
            INSERT_AT,
            Field("levels", Number(1, 9, integer=True), "deepest heading level listed, default 3"),
            Field("title", Text(), "title paragraph above the list"),
        )),
        Record("add_bookmark", "name a paragraph so links and cross-references, also later in the batch, can point at it", (
            TARGET_BLOCK,
            Field("name", Text(non_empty=True), "a letter, then letters, digits or _, at most 40 characters", required=True),
        )),
        Record("insert_link", "make exact text inside a block a link to a web address or a bookmark", (
            TARGET_BLOCK,
            Field("find", Text(non_empty=True), "exact text that becomes the link", required=True),
            Field("url", Text(non_empty=True), "web address; give url or bookmark"),
            Field("bookmark", Text(non_empty=True), "bookmark name in this document"),
        )),
        Record("insert_cross_reference", "insert a field showing a bookmarked paragraph's text, page or number", (
            TARGET_BLOCK,
            Field("bookmark", Text(non_empty=True), "bookmark name from add_bookmark", required=True),
            Field("show", Choice(("text", "page", "number")), "default text"),
            AFTER_TEXT,
        )),
        Record("insert_footnote", "add a footnote whose mark goes in a block", NOTE_FIELDS),
        Record("insert_endnote", "add an endnote whose mark goes in a block", NOTE_FIELDS),
        Record("set_header", "replace a section's header text; {PAGE} and {NUMPAGES} become page number fields", HEADER_FOOTER_FIELDS),
        Record("set_footer", "replace a section's footer text; {PAGE} and {NUMPAGES} become page number fields", HEADER_FOOTER_FIELDS),
        Record("set_page_setup", "set paper size, orientation, margins and text columns", (
            Field("section", Number(minimum=0, integer=True), "section index; default every section"),
            Field("paper", Choice(PAPER_NAMES), "paper size"),
            Field("orientation", Choice(("portrait", "landscape")), "page orientation"),
            Field("marginInches", Number(minimum=0), "every margin"),
            Field("marginTopInches", Number(minimum=0), "top margin"),
            Field("marginBottomInches", Number(minimum=0), "bottom margin"),
            Field("marginLeftInches", Number(minimum=0), "left margin"),
            Field("marginRightInches", Number(minimum=0), "right margin"),
            Field("columns", Number(1, 4, integer=True), "text columns"),
            Field("pageNumberStart", Number(minimum=0, integer=True), "restart page numbering at this value, so {PAGE} fields count from it"),
        )),
        Record("insert_section_break", "start a new section after a block, so the pages after it can have their own orientation, margins, headers and footers", (
            Field("after", BLOCK_INDEX, "block index the current section ends with", required=True),
            Field("type", Choice(("nextPage", "continuous", "evenPage", "oddPage")), "where the new section starts, default nextPage"),
            Field("orientation", Choice(("portrait", "landscape")), "orientation of the new section"),
        )),
        Record("set_watermark", "put large diagonal text such as 대외비 or DRAFT, or a picture such as a logo, behind every page; give text or image", (
            Field("text", Text(), "watermark text; empty removes the watermark"),
            Field("image", Text(non_empty=True), f"{PICTURE_FORMATS_TEXT} file centered behind the body"),
            Field("scale", Number(minimum=1, maximum=1000), "picture size as a percent of its natural size; default fit inside the margins"),
            Field("washout", Boolean(), "fade the picture the way Word's washout does, default true"),
            Field("color", HexColor(), "text color, default light gray"),
            Field("section", Number(minimum=0, integer=True), "section index; default every section"),
        )),
        Record("add_comment", "start a comment thread on a paragraph, or on exact text inside it; the document text is untouched", (
            TARGET_BLOCK,
            Field("text", Text(non_empty=True), "comment text", required=True),
            Field("find", Text(non_empty=True), "exact text inside the block the comment marks; default the whole paragraph"),
            Field("occurrence", Number(minimum=1, integer=True), "which occurrence of find, default 1"),
            Field("author", Text(), "who the comment is from; required unless a --track --author run names them"),
        )),
        Record("reply_comment", "reply in a comment's thread", (
            COMMENT_ID,
            Field("text", Text(non_empty=True), "reply text", required=True),
            Field("author", Text(), "who the comment is from; required unless a --track --author run names them"),
        )),
        Record("resolve_comment", "mark a comment's thread resolved, or reopen it", (
            COMMENT_ID,
            Field("resolved", Boolean(), "false reopens the thread, default true"),
        )),
        Record("delete_comment", "delete a comment and its anchor; deleting a thread's first comment deletes its replies", (COMMENT_ID,)),
        Record("accept_revisions", "accept tracked changes: insertions become plain text, deleted text goes, formatting stays", REVISION_SELECTOR),
        Record("reject_revisions", "reject tracked changes: inserted text goes, deleted text comes back, formatting reverts", REVISION_SELECTOR),
        Record("set_east_asia_font", "make the document's default East Asian font this one", (
            Field("font", Text(non_empty=True), f"font name such as {DOCUMENT_FONT}", required=True),
        )),
        Record("set_korean_language", "tag the document's East Asian language as Korean (ko-KR): the default, the theme font language, and every style or run that names another", ()),
        Record("update_fields_on_open", "ask Word to refresh the table of contents and other fields when the file opens", ()),
    ),
)
OPERATION_BATCH = ListOf(OPERATIONS, non_empty=True)

BROKEN_INTERNAL_REFERENCE = IssueKind("BROKEN_INTERNAL_REFERENCE", ERROR, "a link or cross-reference points at a bookmark the document does not have", "point it at an existing heading or bookmark, or remove it")
STALE_TABLE_OF_CONTENTS = IssueKind("STALE_TABLE_OF_CONTENTS", WARNING, "the table of contents does not list the headings the document has", "apply update_fields_on_open so Word refreshes it")
EAST_ASIA_FONT_MISSING = IssueKind("EAST_ASIA_FONT_MISSING", WARNING, "Korean text has no East Asian font at any level, so each reader substitutes its own", "apply set_east_asia_font")
EAST_ASIA_LANGUAGE_NOT_KOREAN = IssueKind("EAST_ASIA_LANGUAGE_NOT_KOREAN", WARNING, "Korean text is tagged with another East Asian language, so LibreOffice breaks its lines mid-word and Word picks that language's fonts", "apply set_korean_language")
TRACKED_CHANGES_PRESENT = IssueKind("TRACKED_CHANGES_PRESENT", WARNING, "the document holds tracked changes nobody has accepted or rejected", "doc read --revisions lists them; settle them with accept_revisions or reject_revisions unless the reader should see the redline")

MISSING_IMAGE = IssueKind("MISSING_IMAGE", ERROR, "a picture's image part is missing from the file, so it shows an empty frame or nothing", "delete_block when the paragraph holds only the picture, or insert_image the file again")
CHART_EMPTY = IssueKind("CHART_EMPTY", WARNING, "a chart has no number in any series, so it draws empty axes", "apply edit_chart with the categories and values")
EMPTY_HEADING = IssueKind("EMPTY_HEADING", WARNING, "a heading has no text, so the outline and the table of contents show a blank line", "apply delete_block, or set_text with the heading")
HEADING_SKIP = IssueKind("HEADING_SKIP", WARNING, "a heading is more than one level deeper than the heading before it", "apply set_style with the next level's heading style")
UNRESOLVED_COMMENTS = IssueKind("UNRESOLVED_COMMENTS", WARNING, "comment threads are still open, and the reader sees them in the margin", "doc read lists them; answer or resolve_comment each, or delete_comment")
FIELD_NOT_EVALUATED = IssueKind("FIELD_NOT_EVALUATED", WARNING, "a field holds no result, so it shows blank until Word updates fields", "apply update_fields_on_open")

CHECK_ISSUE_KINDS = (
    PLACEHOLDER_LEFT, BROKEN_INTERNAL_REFERENCE, STALE_TABLE_OF_CONTENTS, EAST_ASIA_FONT_MISSING, EAST_ASIA_LANGUAGE_NOT_KOREAN, TRACKED_CHANGES_PRESENT,
    MISSING_IMAGE, CHART_EMPTY, EMPTY_HEADING, HEADING_SKIP, UNRESOLVED_COMMENTS, FIELD_NOT_EVALUATED,
)

MERGE_ISSUE_KINDS = (UNRESOLVED_PLACEHOLDER, UNUSED_VALUE, LIST_NEEDS_A_ROW, TEMPLATE_SYNTAX_ERROR)

CHART_BLOCK_INVALID = IssueKind("CHART_BLOCK_INVALID", ERROR, "a ```chart block in the Markdown does not parse or its numbers do not line up, so nothing was written", "fix the line the message names: type:, labels: and values: (or series: name: 1, 2; other: 3, 4) with plain numbers")
IMAGE_UNAVAILABLE = IssueKind("IMAGE_UNAVAILABLE", WARNING, "a Markdown image is not a readable local file, so its alt text was written instead", "fix the image path relative to the Markdown file, or save a remote image locally first")

PDF_RENDERER_FAILED = IssueKind("PDF_RENDERER_FAILED", ERROR, "the document PDF renderer (takumi-pdf, run by bun or node) could not be installed or could not render", "check that bun or node 18 is on PATH and the network allows its first install, then rerun")
PDF_RENDERER_UNAVAILABLE = IssueKind("PDF_RENDERER_UNAVAILABLE", WARNING, "neither bun nor node 18 is installed, so the PDF was drawn by the plain fallback renderer without inline bold, links styling or page numbers", "install bun for the typeset PDF, or deliver this plainer one")

GLYPH_NOT_COVERED = IssueKind("GLYPH_NOT_COVERED", WARNING, "some characters have no glyph in any font the PDF carries, so they print as empty boxes", "replace those characters, such as an emoji or a rare Hanja, with words")

MATH_NOT_CONVERTED = IssueKind("MATH_NOT_CONVERTED", WARNING, "a $...$ or $$...$$ formula is not LaTeX the converter reads, so its source text was written as it is", "fix the LaTeX with standard commands such as \\frac, \\sqrt, \\sum, ^ and _, or write the formula in words")
EXPORT_ISSUE_KINDS = (CHART_BLOCK_INVALID, IMAGE_UNAVAILABLE, MATH_NOT_CONVERTED, PDF_RENDERER_FAILED, PDF_RENDERER_UNAVAILABLE, GLYPH_NOT_COVERED)

CHART_FENCE_KEYS = {
    "type": f"one of {', '.join(DOCUMENT_CHART_KINDS)}; the deck's stacked and donut work too",
    "title": "the chart title, with the unit",
    "labels": "category names separated by a comma and a space",
    "values": "one number per label, for a single series",
    "series": '"name: 1, 2; other: 3, 4" for several series, each with one number per label',
    "line": "series names drawn as lines over the columns",
    "legend": "yes or no",
}
CHART_KEYS = tuple(CHART_FENCE_KEYS)


def markdown_lines() -> list[str]:
    return [
        "  a ```chart fence holds one key: value per line and becomes a native Word chart:",
        *(f"    {key}: {meaning}" for key, meaning in CHART_FENCE_KEYS.items()),
        "  LaTeX in $...$, or alone on a $$...$$ line, becomes a Word equation",
        f"  any other ``` fence is a code block in {default_family(MONOSPACE).name}",
        "  links, local images, tables and nested lists keep their Markdown meaning",
    ]


GUIDE_SECTIONS = (("Markdown that doc export reads", markdown_lines),)

GUIDE_INPUTS = (
    ("doc create --spec <file>", DOCUMENT_SPECIFICATION),
    ("doc create --table <file>", TABLE_FILE),
    ("doc edit --blocks <file>", BLOCK_LIST),
    ("doc apply <file.docx> <ops.json>", OPERATION_BATCH),
    ("doc merge <template.docx> <values.json> <output.docx>: values", MERGE_VALUES),
)
GUIDE_ISSUES = (
    ("doc export", EXPORT_ISSUE_KINDS),
    ("doc validate", VALIDATE_ISSUE_KINDS + (EAST_ASIA_FONT_MISSING,)),
    ("doc check", CHECK_ISSUE_KINDS),
    ("doc apply", OPERATION_ISSUE_KINDS),
    ("doc merge", MERGE_ISSUE_KINDS),
    ("doc render", PREVIEW_ISSUE_KINDS),
)
