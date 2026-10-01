# Spreadsheets

Create or modify local workbooks (.xlsx, .xlsm, .csv, .tsv). SKILL.md's rules for source truth, totals, earlier files, naming and verification apply here; never invent prices or taxes either.

A CSV or TSV becomes a workbook with `<skill>/scripts/office convert <data.csv> ~/documents/<title>.xlsx`, which types the cells and styles, freezes and filters the header; `sheet apply` then adds the summary sheet, formulas, rules and charts. No spec file is needed for that.

`<skill>/scripts/office guide sheet` is a short index of the commands, the operation names, how the commands treat formulas, dates, CSV values and edits, and the issue codes. Then read only what the job needs: `office guide sheet apply <op>` for each operation you write, and `office guide sheet create` when you write a spec. Do not copy the guide into a reply.

| Job | Command |
| --- | --- |
| CSV or TSV to a workbook | `office convert <data.csv> ~/documents/<title>.xlsx`, then `sheet apply` |
| New workbook | `sheet create ~/documents/<title>.xlsx --spec spec.json`: sheets with `rows` or `csvPath`, then `operations` for formats, rules, charts and pivots |
| Append rows | `sheet edit <file> --rows rows.json` |
| See an existing workbook | `sheet read <file>`, then `--sheet`, `--range`, `--stats` for column totals, `--where error` or `--where formula` |
| Change it | `sheet apply <file> ops.json` |
| Verify | `sheet check`, then `sheet validate`, then `sheet render`, whose `details.pageContents` names each page's sheet, cells and charts, whole or cut, for a check without looking at images |
| Work no operation covers | a task-local script run through `office python` |

## Workflow

1. Clarify only missing columns, source data, formulas or format choices that change the structure. Preview a newly uploaded file before extraction.
2. Bring a CSV or TSV in with `office convert`, never a parser of your own, then `sheet read` it and compare its row and column counts with the source; never drop rows or columns. Put rows you cannot repair confidently in an `Issues` sheet.
3. Work in `~/documents/`. Write each formula's references for the row it lands in, counting a heading row.
4. Run `sheet check` and `sheet validate` and fix what they report; each issue says how, and an issue such as `NUMBER_TOO_WIDE` carries the exact operations in its `fix`. Then `sheet read` the ranges that hold totals and compare them with the source.
5. Deliver source CSVs only when requested.

## Workbook quality

Use clear sheet names, a summary sheet apart from the detail rows, number formats on every numeric column, and formulas such as SUMIFS and XLOOKUP over the detail when the workbook must stay live. Keep a visible source total when one is given. `sheet create` freezes each table's header and filters it; keep both. In a user's workbook keep formulas, styles, sheet names and macros unless asked otherwise.
