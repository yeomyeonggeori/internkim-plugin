from office_result import ERROR, WARNING, IssueKind
from office_schema import AnyOf, CellValue, Choice, Field, ListOf, MapOf, Number, Record, Text, Variant
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

GUIDE_INPUTS = (
    ("doc create --spec <file>", DOCUMENT_SPECIFICATION),
    ("doc create --table <file>", TABLE_FILE),
    ("doc edit --blocks <file>", BLOCK_LIST),
)
GUIDE_ISSUES = (("doc validate", VALIDATE_ISSUE_KINDS),)
