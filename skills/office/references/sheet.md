# Spreadsheets

Create or modify local workbooks (.xlsx, .xlsm, .csv, .tsv). SKILL.md's rules for source truth, totals, earlier files, naming and verification apply here; never invent prices or taxes either.

| Job | Command |
| --- | --- |
| CSV or TSV to a workbook | `<skill>/scripts/office create ~/documents/<title>.xlsx <data.csv>` types the cells and freezes and filters the header; then `office apply` |
| New workbook | `office create ~/documents/<title>.xlsx <title>.workbook.json`, a declaration: `references/schemas.md` |
| See an existing workbook | `office read <file>`, then `--sheet`, `--range`, `--stats` for column totals, `--where error` or `--where formula` |
| Change it, or append rows | `office apply <file> ops.json`; `append_rows` writes under the last filled row |
| Verify | `office check`, then `office render`, whose `details.pageContents` names each page's sheet, cells and charts, whole or cut, for a check without looking at images |
| Work no operation covers | a task-local script run through `office python` |

`<skill>/scripts/office guide xlsx` is a short index of the commands, the operation names, how the commands treat formulas, dates, CSV values and edits, and the issue codes. Then read only what the job needs: `office guide apply xlsx <op>` for each operation you write, and `office guide create xlsx` when you write a declaration. Do not copy the guide into a reply.

## Workflow

1. Clarify only missing columns, source data, formulas or format choices that change the structure. Preview a newly uploaded file before extraction.
2. Bring a CSV or TSV in with `office create`, never a parser of your own, then `office read` it and compare its row and column counts with the source; never drop rows or columns. Put rows you cannot repair confidently in an `Issues` sheet.
3. Work in `~/documents/`. Write each formula's references for the row it lands in, counting a heading row.
4. Run `office check` and fix what it reports; each issue says how, and an issue such as `NUMBER_TOO_WIDE` carries the exact operations in its `fix`. Then `office read` the ranges that hold totals and compare them with the source.
5. Deliver source CSVs only when requested.

## Workbook quality

Use clear sheet names, a summary sheet apart from the detail rows, number formats on every numeric column, and formulas such as SUMIFS and XLOOKUP over the detail when the workbook must stay live. Keep a visible source total when one is given. `office create` freezes each table's header and filters it; keep both. In a user's workbook keep formulas, styles, sheet names and macros unless asked otherwise.
