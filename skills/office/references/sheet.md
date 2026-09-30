# Spreadsheets

Create or modify local workbooks (.xlsx, .xlsm, .csv, .tsv). SKILL.md's rules for source truth, totals, earlier files, naming, and verification apply here; never invent prices or taxes either.

## Workflow

1. Clarify only missing columns, source data, formulas, or format choices that affect structure. Preview a newly uploaded file before extraction.
2. Work in `~/documents/`. Use `sheet create` for straightforward workbooks, `sheet edit` for simple appends, and a task-local Python file run through `office python` for charts, macros, advanced formulas, or substantial edits. The commands' `--help` and typed descriptors define exact payload fields; do not copy their schemas into a reply.
3. Parse CSV and TSV with Python's `csv`, preserve malformed data for review, and never silently drop rows or columns. Put uncertain rows in a separate `Issues` sheet when they cannot be repaired confidently.
4. Validate with `<skill>/scripts/office sheet validate ~/documents/<title>.xlsx` or by reopening the workbook. Fix warnings for missing filters, frozen headers, blank headers, broken formulas, suspicious totals, and unsupported source values.
5. Deliver source CSVs only when requested.

## Workbook quality

Use clear sheet names, readable widths, frozen header rows, professional number formats, and filters on every row-and-column table. Keep summary and detail views separate for budgets, operations, and finance. Use formulas when the workbook must stay interactive, and preserve a visible source total when provided.

Formulas are stored exactly as written, so write every reference for the row and column it lands in, counting any title or heading row you add. The scripts add no rows of their own: the spec `title` is document metadata only, and a title meant to be visible goes in a row or `heading` you write. CSV and `--row` values become numbers when they are plain integers or decimals and dates when they are `YYYY-MM-DD`; values such as `007`, `+82`, `1,500`, or more than 15 digits stay text.

Preserve formulas, styles, sheet names, and macros during edits unless the user asks otherwise.

## Editing

With no path, `sheet edit` targets the newest workbook; name an older file by its explicit workspace path. For rewrites, deletions, or style changes, use task-local code through `office python` and preserve workbook features.

## Final check

Reopen or validate the workbook, check dimensions, formula references, filters, frozen panes, blank required cells, totals, and visible source facts before attaching it.
