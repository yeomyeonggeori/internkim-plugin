from __future__ import annotations

from core.office_result import ERROR, IssueKind
from core.office_schema import Boolean, CellValue, Choice, Field, ListOf, Record, Text


COLUMN_TYPES = ("text", "date", "amount", "quantity", "percent")
ADDED_TYPES = ("percent", "amount", "quantity")
CHART_KINDS = ("line", "column", "bar", "pie")

DECLARED_COLUMN = Record("declared column", "one column of a source table", (
    Field("name", Text(non_empty=True), "the header", required=True),
    Field("type", Choice(COLUMN_TYPES), "text (default), date, amount, quantity or percent"),
    Field("role", Choice(("dimension", "measure")), "dimension: what rows are grouped by, such as a year, region or product; measure: a number that is summed. Default: amount, quantity and percent are measures, the rest dimensions"),
    Field("unit", Text(), "amount: a currency code such as USD or KRW, or the unit the source states such as 백만원; quantity: the counted unit"),
))

DECLARED_TABLE = Record("declared table", "the source data, one row per record exactly as the request or attachment gives it", (
    Field("name", Text(non_empty=True), "the data sheet's name", required=True),
    Field("columns", ListOf(DECLARED_COLUMN, non_empty=True), "the columns, in order", required=True),
    Field("rows", ListOf(ListOf(CellValue())), "the records the request's text gives, one list of cells per row in column order; null for a value the source does not give, never 0; never an attached table typed out"),
    Field("csvPath", Text(non_empty=True), "the path of an attached CSV or TSV whose header row is followed by the records, read as it is instead of rows; an attached table is always read this way"),
))

VIEW_COLUMN = Record("added column", "a column computed from the view's own cells", (
    Field("name", Text(non_empty=True), "the header", required=True),
    Field("expression", Text(non_empty=True), "measure names with + - * / and parentheses, such as (actual - budget) / budget; or percentChange(measure, dimension), change(measure, dimension) or share(measure, dimension)", required=True),
    Field("type", Choice(ADDED_TYPES), "how the result is written; percentChange and share are percent"),
))

DECLARED_VIEW = Record("declared view", "a summary the compiler writes as live formulas over a table", (
    Field("sheet", Text(non_empty=True), "the sheet it goes on; views on one sheet stack downward", required=True),
    Field("title", Text(non_empty=True), "the title row above it", required=True),
    Field("table", Text(non_empty=True), "the source table's name, default the first"),
    Field("rows", ListOf(Text(non_empty=True), non_empty=True), "one or two dimensions, one row per member", required=True),
    Field("columns", Text(non_empty=True), "a dimension whose members become columns, with measure naming the one measure shown"),
    Field("measure", Text(non_empty=True), "with columns: the measure in each cell"),
    Field("measures", ListOf(Text(non_empty=True)), "without columns: the measures shown side by side"),
    Field("totals", Boolean(), "add a total row"),
    Field("totalColumn", Boolean(), "with columns: add a column totalling each row across the members, for members that add up, such as products; not for years or quarters"),
    Field("add", ListOf(VIEW_COLUMN), "computed columns"),
))

DECLARED_CHART = Record("declared chart", "a chart of a view's member cells, without totals or added columns; with two row dimensions each label joins both members, such as 2025 1분기", (
    Field("view", Text(non_empty=True), "the view's title", required=True),
    Field("type", Choice(CHART_KINDS), "line, column, bar or pie", required=True),
    Field("title", Text(), "the chart's title"),
))

WORKBOOK_DECLARATION = Record("workbook declaration", "a workbook declared as typed source tables, views and charts; office create compiles the formulas, number formats and chart ranges", (
    Field("kind", Choice(("workbook",)), "workbook", required=True),
    Field("title", Text(), "the workbook's title"),
    Field("language", Choice(("ko", "en")), "the language of the labels the compiler writes, such as the total row's"),
    Field("tables", ListOf(DECLARED_TABLE, non_empty=True), "the source tables", required=True),
    Field("views", ListOf(DECLARED_VIEW), "the summaries"),
    Field("charts", ListOf(DECLARED_CHART), "the charts"),
))

DECLARATION_INVALID = IssueKind("DECLARATION_INVALID", ERROR, "a view, chart or expression names a table, column, dimension or measure the declaration does not have, or uses one in the wrong role", "use the names the declaration's tables give, a dimension where a dimension belongs and a measure where a measure belongs")
DECLARATION_REQUIRED = IssueKind("DECLARATION_REQUIRED", ERROR, "office create makes a new workbook only from a declaration of kind workbook; formulas, formats and charts are compiled from it, never written by hand", "write <title>.workbook.json with office guide create xlsx, reading an attached CSV or TSV through csvPath, and run office create <title>.xlsx <title>.workbook.json")
COMPILED_CELLS = IssueKind("COMPILED_CELLS", ERROR, "the edit changes cells compiled from a declaration", "change the declaration and run office create again")
