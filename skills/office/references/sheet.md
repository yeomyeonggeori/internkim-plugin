# Spreadsheets

Create or modify local workbooks (.xlsx, .xlsm, .csv, .tsv). SKILL.md's rules for source truth, totals, earlier files, naming and verification apply here; never invent prices or taxes either.

`<skill>/scripts/office guide sheet` lists every spec field, operation and issue, and how the commands treat formulas, CSV values and edits. Read it before writing a spec or operations, and do not copy it into a reply.

| Job | Command |
| --- | --- |
| New workbook | `sheet create ~/documents/<title>.xlsx --spec spec.json`: sheets with `rows` or `csvPath`, then `operations` for formats, rules, charts and pivots |
| Append rows | `sheet edit <file> --rows rows.json`; with no path it targets the newest workbook |
| See an existing workbook | `sheet read <file>`, then `--sheet`, `--range`, `--stats` for column totals, `--where error` or `--where formula` |
| Change it | `sheet apply <file> ops.json` |
| Verify | `sheet check`, then `sheet validate` |
| Work no operation covers | a task-local script run through `office python` |

## Workflow

1. Clarify only missing columns, source data, formulas or format choices that change the structure. Preview a newly uploaded file before extraction.
2. Parse CSV and TSV with Python's `csv`, preserve malformed data for review, and never silently drop rows or columns. Put rows you cannot repair confidently in an `Issues` sheet.
3. Work in `~/documents/`. Write each formula's references for the row it lands in, counting a heading row.
4. Run `sheet check` and `sheet validate` and fix what they report; each issue says how, and `NUMBER_TOO_WIDE` carries the exact operation. Then `sheet read` the ranges that hold totals and compare them with the source.
5. Deliver source CSVs only when requested.

## Workbook quality

Use clear sheet names, a summary sheet apart from the detail rows, number formats on every numeric column, and formulas such as SUMIFS and XLOOKUP over the detail when the workbook must stay live. Keep a visible source total when one is given. `sheet create` freezes each table's header and filters it; keep both. In a user's workbook keep formulas, styles, sheet names and macros unless asked otherwise.
