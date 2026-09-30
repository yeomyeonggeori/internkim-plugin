from office_operations import OPERATION_ISSUE_KINDS
from office_result import ERROR, WARNING, IssueKind
from office_schema import AnyOf, Boolean, CellValue, Choice, Field, ListOf, MapOf, Number, Record, Text, Variant
from text_checks import TEXT_CHECK_ISSUE_KINDS


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

PAGE = Record("page", "page setup", (
    Field("orientation", Choice(("portrait", "landscape")), "default portrait"),
    Field("marginInches", Number(minimum=0), "every margin, default 0.8"),
))

DOCUMENT_SPECIFICATION = Record("document", "the --spec file of doc create", (
    Field("title", Text(), "centered title above the first block"),
    Field("fontName", Text(non_empty=True), "font for body and headings, default 맑은 고딕"),
    Field("fontSize", Number(minimum=1), "body size in points, default 10.5"),
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
    *TEXT_CHECK_ISSUE_KINDS,
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
INSERT_AFTER = Field("after", Number(minimum=-1, integer=True), "insert after this block index from doc read; -1 inserts at the start")
INSERT_BEFORE = Field("before", BLOCK_INDEX, "insert before this block index; give after or before, not both")
TARGET_BLOCK = Field("block", BLOCK_INDEX, "block index from doc read", required=True)
TABLE_BLOCK = Field("block", BLOCK_INDEX, "index of a table block from doc read", required=True)
ROW_INDEX = Number(minimum=0, integer=True)

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
            Field("text", Text(), "paragraph text", required=True),
            Field("style", Text(non_empty=True), "paragraph style name, default Normal"),
        )),
        Record("insert_heading", "insert a heading", (
            INSERT_AFTER,
            INSERT_BEFORE,
            Field("text", Text(), "heading text", required=True),
            Field("level", Number(1, 9, integer=True), "heading depth, default 1"),
        )),
        Record("insert_list", "insert list items", (
            INSERT_AFTER,
            INSERT_BEFORE,
            Field("items", ListOf(Text(non_empty=True), non_empty=True), "one entry per item", required=True),
            Field("numbered", Boolean(), "numbered instead of bulleted"),
        )),
        Record("insert_table", "insert a table", (
            INSERT_AFTER,
            INSERT_BEFORE,
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
        Record("set_header", "replace a section's header text", (
            Field("text", Text(), "header text", required=True),
            Field("section", Number(minimum=0, integer=True), "section index, default 0"),
        )),
        Record("set_footer", "replace a section's footer text", (
            Field("text", Text(), "footer text", required=True),
            Field("section", Number(minimum=0, integer=True), "section index, default 0"),
        )),
        Record("add_comment", "attach a review comment to a paragraph", (
            TARGET_BLOCK,
            Field("text", Text(non_empty=True), "comment text", required=True),
            Field("author", Text(), "author name"),
        )),
        Record("set_east_asia_font", "make the document's default East Asian font this one", (
            Field("font", Text(non_empty=True), "font name such as 맑은 고딕", required=True),
        )),
        Record("update_fields_on_open", "ask Word to refresh the table of contents and other fields when the file opens", ()),
    ),
)
OPERATION_BATCH = ListOf(OPERATIONS, non_empty=True)

MERGE_VALUES = MapOf(AnyOf((CellValue(), ListOf(CellValue()), MapOf(CellValue(), key="name"), ListOf(MapOf(CellValue(), key="name"))), name="a cell, a list, an object, or a list of objects"), key="placeholder name")

PLACEHOLDER_LEFT = IssueKind("PLACEHOLDER_LEFT", ERROR, "template placeholder syntax or a merge field is still in the text", "replace it with the real value")
BROKEN_INTERNAL_REFERENCE = IssueKind("BROKEN_INTERNAL_REFERENCE", ERROR, "a link or cross-reference points at a bookmark the document does not have", "point it at an existing heading or bookmark, or remove it")
STALE_TABLE_OF_CONTENTS = IssueKind("STALE_TABLE_OF_CONTENTS", WARNING, "the table of contents does not list the headings the document has", "apply update_fields_on_open so Word refreshes it")
EAST_ASIA_FONT_MISSING = IssueKind("EAST_ASIA_FONT_MISSING", WARNING, "Korean text has no East Asian font at any level, so each reader substitutes its own", "apply set_east_asia_font")
TRACKED_CHANGES_PRESENT = IssueKind("TRACKED_CHANGES_PRESENT", WARNING, "the document holds tracked insertions or deletions, which doc apply neither reads nor edits", "accept or reject them in Word before editing")

CHECK_ISSUE_KINDS = (PLACEHOLDER_LEFT, BROKEN_INTERNAL_REFERENCE, STALE_TABLE_OF_CONTENTS, EAST_ASIA_FONT_MISSING, TRACKED_CHANGES_PRESENT)

UNRESOLVED_PLACEHOLDER = IssueKind("UNRESOLVED_PLACEHOLDER", ERROR, "the template uses a placeholder the values file does not give", "add the value to the values file")
UNUSED_VALUE = IssueKind("UNUSED_VALUE", WARNING, "the values file gives a name the template never uses", "check the name's spelling against the template")
TEMPLATE_SYNTAX_ERROR = IssueKind("TEMPLATE_SYNTAX_ERROR", ERROR, "the template's placeholder syntax does not parse", "fix the {{ }} or {% %} tag the message names")

MERGE_ISSUE_KINDS = (UNRESOLVED_PLACEHOLDER, UNUSED_VALUE, TEMPLATE_SYNTAX_ERROR)

IMAGE_UNAVAILABLE = IssueKind("IMAGE_UNAVAILABLE", WARNING, "a Markdown image is not a readable local file, so its alt text was written instead", "fix the image path relative to the Markdown file, or save a remote image locally first")

EXPORT_ISSUE_KINDS = (IMAGE_UNAVAILABLE,)

GUIDE_INPUTS = (
    ("doc create --spec <file>", DOCUMENT_SPECIFICATION),
    ("doc create --table <file>", TABLE_FILE),
    ("doc edit --blocks <file>", BLOCK_LIST),
    ("doc apply <file.docx> <ops.json>", OPERATION_BATCH),
    ("doc merge <template.docx> <values.json> <output.docx>: values", MERGE_VALUES),
)
GUIDE_ISSUES = (
    ("doc export", EXPORT_ISSUE_KINDS),
    ("doc validate", VALIDATE_ISSUE_KINDS),
    ("doc check", CHECK_ISSUE_KINDS),
    ("doc apply", OPERATION_ISSUE_KINDS),
    ("doc merge", MERGE_ISSUE_KINDS),
)
