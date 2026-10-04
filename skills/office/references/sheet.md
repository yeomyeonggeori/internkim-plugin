# Spreadsheets

Change a workbook the person already has (.xlsx, .xlsm). A new workbook, including one made from an attached CSV or TSV, is a declaration: `references/schemas.md`. SKILL.md's rules for source truth, totals, earlier files, naming and verification apply here; never invent prices or taxes either.

| Job | Command |
| --- | --- |
| See the workbook | `<skill>/scripts/office read <file>`, then `--sheet`, `--range`, `--stats` for column totals, `--where error` or `--where formula` |
| Change it, or append rows | `office apply <file> ops.json`; `append_rows` writes under the last filled row |
| Verify | `office check`, then `office render`, whose `details.pageContents` names each page's sheet, cells and charts, whole or cut, for a check without looking at images |
| Work no operation covers | a task-local script run through `office python` |

`<skill>/scripts/office guide xlsx` is a short index of the commands, the operation names, how the commands treat formulas, dates and edits, and the issue codes. Then read only what the job needs: `office guide apply xlsx <op>` for each operation you write. Do not copy the guide into a reply.

## Workflow

1. Clarify only missing columns, source data or formula choices that change the structure. Preview a newly uploaded file before editing it.
2. `office read` the sheets you change and note their row and column counts; never drop rows or columns.
3. Write each formula's references for the row it lands in, counting a heading row.
4. Run `office check` and fix what it reports; each issue says how, and an issue such as `NUMBER_TOO_WIDE` carries the exact operations in its `fix`. Then `office read` the ranges that hold totals and compare them with the source.

A workbook `office create` compiled from a declaration refuses an `apply` that changes its compiled cells (`COMPILED_CELLS`) and names the declaration: change that and run the same `create` again. Formatting those cells and writing outside them still works.

## Workbook quality

In a person's workbook keep formulas, styles, sheet names and macros unless asked otherwise, and keep a visible source total when one is given.
