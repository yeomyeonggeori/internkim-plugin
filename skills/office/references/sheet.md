# Spreadsheets

Create or modify local workbooks (.xlsx, .xlsm, .csv, .tsv). SKILL.md's rules for source truth, totals, earlier files, naming, and verification apply here; never invent prices or taxes either.

## Workflow

1. Clarify only missing columns, source data, formulas, or format choices that affect structure. Preview a newly uploaded file before extraction.
2. Work in `~/documents/`. Use `sheet create` for a new workbook and `sheet edit` to append rows. For an earlier workbook, run `<skill>/scripts/office sheet read <file>` for its sheets, panes, filters, tables, charts, merged cells and defined names, add `--sheet`, `--range A1:F40` and `--where formula` to see one range's values and formulas side by side, then change it with `sheet apply <file> <ops.json>`. `<skill>/scripts/office guide sheet` lists every spec field and operation; do not copy the schema into a reply.
3. Parse CSV and TSV with Python's `csv`, preserve malformed data for review, and never silently drop rows or columns. Put uncertain rows in a separate `Issues` sheet when they cannot be repaired confidently.
4. Run `<skill>/scripts/office sheet check ~/documents/<title>.xlsx` and then `sheet validate`. Check reports computed formula errors, missing sheets, broken defined names, numbers too wide for their column, placeholders left, and formulas that could not be computed. Validate reports a header row that is not frozen, a missing filter, and blank headers. Fix what they report, then read the totals against the source.
5. Deliver source CSVs only when requested.

## Workbook quality

Use clear sheet names, readable widths, frozen header rows, professional number formats, and filters on every row-and-column table. Keep summary and detail views separate for budgets, operations, and finance. Use formulas when the workbook must stay interactive, and preserve a visible source total when provided.

Formulas are stored exactly as written, so write every reference for the row and column it lands in, counting any title or heading row you add. After `sheet create`, `sheet edit` and `sheet apply`, each formula cell also carries the value it computes, so readers that do not recalculate show numbers. A formula the scripts cannot compute keeps no value and is reported as `FORMULA_NOT_EVALUATED` with its cells; Excel calculates it on open. The scripts add no rows of their own: the spec `title` is document metadata only, and a title meant to be visible goes in a row or `heading` you write. CSV and `--row` values become numbers when they are plain integers or decimals and dates when they are `YYYY-MM-DD`; values such as `007`, `+82`, `1,500`, or more than 15 digits stay text.

Preserve formulas, styles, sheet names, and macros during edits unless the user asks otherwise.

## Editing

With no path, `sheet edit` targets the newest workbook; name an older file by its explicit workspace path.

`sheet apply` writes cells and ranges (text starting with `=` is a formula unless `type` is `text`), formats ranges, sets column widths, freezes panes, sets the filter, adds and renames sheets, inserts and deletes rows and columns, and adds bar, line and pie charts. The operations run in order and each sees what the ones before it left, and the file is written whole or not at all; `--dry-run` lists the changes first and `--output` leaves the source alone. Inserting, deleting and renaming rewrite every formula reference, absolute and cross-sheet ones included, along with defined names, filters, merged ranges and chart series, so never patch those by hand. A reference into a deleted row becomes `#REF!`, which `sheet check` then reports. Macros in an .xlsm stay. Work no operation covers goes in a task-local script run through `office python`.

## Final check

Run `sheet check`, then `sheet read` the ranges that hold totals and compare them with the source. A `NUMBER_TOO_WIDE` issue carries the `set_column_width` operation that fixes it. Confirm filters, frozen panes, blank required cells and visible source facts before attaching the workbook.
