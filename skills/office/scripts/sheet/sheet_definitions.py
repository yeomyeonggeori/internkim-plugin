from office_result import ERROR, WARNING, IssueKind
from office_schema import Boolean, CellValue, Field, ListOf, MapOf, Number, Record, Text


ROWS = ListOf(ListOf(CellValue()))

SHEET = Record("sheet", "one worksheet; the first row, or the row after the heading, is the header", (
    Field("title", Text(non_empty=True), "sheet name, cut to 31 characters", required=True),
    Field("heading", Text(), "bold title row above the table"),
    Field("rows", ROWS, "rows in order; text starting with = is a formula"),
    Field("csvPath", Text(non_empty=True), "read the rows from this CSV or TSV file instead of rows"),
    Field("delimiter", Text(non_empty=True), "csvPath delimiter, default comma; \\t for tab"),
    Field("freezePanes", Text(), "top-left unfrozen cell, default the cell under the header; empty text freezes nothing"),
    Field("autoFilter", Boolean(), "filter over the table, default true"),
    Field("columnWidths", MapOf(Number(minimum=0), key="column letter"), "width per column, at least 4"),
    Field("numberFormats", MapOf(Text(non_empty=True), key="column letter"), "Excel number format per column"),
))

WORKBOOK_SPECIFICATION = Record("workbook", "the --spec file of sheet create", (
    Field("title", Text(), "workbook title stored as document metadata; a visible title is a heading or row you write"),
    Field("sheets", ListOf(SHEET, non_empty=True), "the worksheets", required=True),
))

HEADER_NOT_FROZEN = IssueKind("HEADER_NOT_FROZEN", WARNING, "the header row is not frozen", "freeze the pane under the header row")
AUTO_FILTER_MISSING = IssueKind("AUTO_FILTER_MISSING", WARNING, "the table has no auto filter", "add a filter over the header and data rows")
BLANK_HEADER_CELLS = IssueKind("BLANK_HEADER_CELLS", WARNING, "header cells are blank", "name every column")
FORMULA_ERROR_MARKER = IssueKind("FORMULA_ERROR_MARKER", ERROR, "a cell holds #REF!, #VALUE! or #DIV/0!", "fix the formula's references or its inputs")

VALIDATE_ISSUE_KINDS = (
    HEADER_NOT_FROZEN,
    AUTO_FILTER_MISSING,
    BLANK_HEADER_CELLS,
    FORMULA_ERROR_MARKER,
)

GUIDE_INPUTS = (
    ("sheet create --spec <file>", WORKBOOK_SPECIFICATION),
    ("sheet edit --rows <file>", ROWS),
)
GUIDE_ISSUES = (("sheet validate", VALIDATE_ISSUE_KINDS),)
