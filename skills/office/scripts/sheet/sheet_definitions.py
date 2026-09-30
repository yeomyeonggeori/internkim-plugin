from __future__ import annotations

from office_operations import OPERATION_ISSUE_KINDS
from office_result import ERROR, WARNING, IssueKind
from office_schema import Boolean, CellValue, Choice, Field, ListOf, MapOf, Number, Record, Text, Variant
from text_checks import PLACEHOLDER_LEFT


ROWS = ListOf(ListOf(CellValue()))
READ_ROW_LIMIT = 500

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

SHEET_NAME = Field("sheet", Text(non_empty=True), "sheet name from sheet read, default the first sheet")
CELL_ADDRESS = Text(non_empty=True)
VALUE_TYPE = Field("type", Choice(("auto", "text")), "auto (default) stores text starting with = as a formula; text keeps it as literal text")
COUNT = Field("count", Number(minimum=1, integer=True), "how many, default 1")

OPERATIONS = Variant(
    "operation",
    "one edit of sheet apply; operations run in order and each sees the workbook the ones before it left, and the batch applies whole or not at all",
    "op",
    (
        Record("set_cell", "write one cell", (
            SHEET_NAME,
            Field("cell", CELL_ADDRESS, "cell address such as B7", required=True),
            Field("value", CellValue(), "number, text or true/false; text starting with = is a formula; omit or null to clear the cell"),
            VALUE_TYPE,
        )),
        Record("set_range", "write a block of values from its top-left cell", (
            SHEET_NAME,
            Field("cell", CELL_ADDRESS, "top-left cell address", required=True),
            Field("values", ROWS, "rows of values; each item follows set_cell's value", required=True),
            VALUE_TYPE,
        )),
        Record("format_range", "format every cell in a range; unnamed properties stay as they are", (
            SHEET_NAME,
            Field("range", CELL_ADDRESS, "range such as A1:D1, or one cell", required=True),
            Field("numberFormat", Text(non_empty=True), "Excel number format such as #,##0 or 0.0%"),
            Field("bold", Boolean(), "bold text on or off"),
            Field("fill", Text(non_empty=True), "background color as six hex digits such as DCEAF7"),
            Field("fontColor", Text(non_empty=True), "text color as six hex digits"),
            Field("alignment", Choice(("left", "center", "right")), "horizontal alignment"),
            Field("wrapText", Boolean(), "wrap long text inside the cell"),
        )),
        Record("set_column_width", "set a column's width in characters; a Korean character counts as two", (
            SHEET_NAME,
            Field("column", Text(non_empty=True), "column letter such as C", required=True),
            Field("width", Number(minimum=4), "width in characters, at least 4", required=True),
        )),
        Record("freeze_panes", "freeze the rows above and the columns left of a cell", (
            SHEET_NAME,
            Field("cell", Text(), "top-left unfrozen cell such as A2; empty text unfreezes"),
        )),
        Record("set_auto_filter", "put a filter on a range's header row", (
            SHEET_NAME,
            Field("range", Text(), "header and data range such as A1:F40; empty text removes the filter"),
        )),
        Record("add_sheet", "add an empty sheet", (
            Field("name", Text(non_empty=True), "new sheet name, at most 31 characters", required=True),
            Field("index", Number(minimum=0, integer=True), "position among the sheets, default last"),
        )),
        Record("rename_sheet", "rename a sheet and rewrite every formula, defined name and chart reference to it", (
            Field("sheet", Text(non_empty=True), "current sheet name", required=True),
            Field("name", Text(non_empty=True), "new sheet name, at most 31 characters", required=True),
        )),
        Record("insert_rows", "insert empty rows before a row; formulas, absolute references, references from other sheets, defined names, filters, merged ranges, tables and charts follow", (
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
        Record("add_chart", "add a chart of a block whose first column holds the categories and whose first row names the series", (
            SHEET_NAME,
            Field("type", Choice(("bar", "line", "pie")), "chart kind", required=True),
            Field("range", CELL_ADDRESS, "data block including its header row and category column, such as A1:C7", required=True),
            Field("title", Text(), "chart title"),
            Field("anchor", CELL_ADDRESS, "cell the chart's top-left corner sits on, default two columns right of the data"),
        )),
    ),
)
OPERATION_BATCH = ListOf(OPERATIONS, non_empty=True)

FORMULA_NOT_EVALUATED = IssueKind("FORMULA_NOT_EVALUATED", WARNING, "a formula could not be computed here, so the file holds no value for it until Excel recalculates", "read the cells the formula uses; the formula itself was kept as written")
HEADER_NOT_FROZEN = IssueKind("HEADER_NOT_FROZEN", WARNING, "the header row is not frozen", "freeze the pane under the header row")
AUTO_FILTER_MISSING = IssueKind("AUTO_FILTER_MISSING", WARNING, "the table has no auto filter", "add a filter over the header and data rows")
BLANK_HEADER_CELLS = IssueKind("BLANK_HEADER_CELLS", WARNING, "header cells are blank", "name every column")
FORMULA_ERROR = IssueKind("FORMULA_ERROR", ERROR, "a formula computes #DIV/0!, #REF!, #NAME?, #VALUE! or #N/A", "fix the formula's references or the cells it reads, with set_cell")
MISSING_SHEET_REFERENCE = IssueKind("MISSING_SHEET_REFERENCE", ERROR, "a formula reads a sheet the workbook does not have", "add the sheet, or point the formula at an existing one with set_cell")
BROKEN_DEFINED_NAME = IssueKind("BROKEN_DEFINED_NAME", ERROR, "a defined name points at #REF! or a sheet the workbook does not have", "read the workbook's defined names and recreate the reference")
NUMBER_TOO_WIDE = IssueKind("NUMBER_TOO_WIDE", ERROR, "a number is wider than its column and Excel shows it as ####", "apply the suggested set_column_width")

VALIDATE_ISSUE_KINDS = (
    HEADER_NOT_FROZEN,
    AUTO_FILTER_MISSING,
    BLANK_HEADER_CELLS,
)
CHECK_ISSUE_KINDS = (
    FORMULA_ERROR,
    MISSING_SHEET_REFERENCE,
    BROKEN_DEFINED_NAME,
    NUMBER_TOO_WIDE,
    PLACEHOLDER_LEFT,
    FORMULA_NOT_EVALUATED,
)

GUIDE_INPUTS = (
    ("sheet create --spec <file>", WORKBOOK_SPECIFICATION),
    ("sheet edit --rows <file>", ROWS),
    ("sheet apply <file.xlsx> <ops.json>", OPERATION_BATCH),
)
WRITE_ISSUE_KINDS = (FORMULA_NOT_EVALUATED,)
GUIDE_ISSUES = (("sheet create, sheet edit and sheet apply", WRITE_ISSUE_KINDS), ("sheet check", CHECK_ISSUE_KINDS), ("sheet validate", VALIDATE_ISSUE_KINDS), ("sheet apply", OPERATION_ISSUE_KINDS))
