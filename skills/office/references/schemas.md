# Documents From Schemas

A schema says what a document holds. Its given fields are the only values you write: the facts the request and its attachments state. The runtime fills the rest. It writes the requester, today's date, the company letterhead, seal, bank account and the registered document number, and `merge` computes amounts, tax, totals and amounts in words. You never write a layout, a date of issue, an author or a total.

## Fill one

1. Pick the schema: `<skill>/scripts/office guide schema` lists them. `report` is for reports, status updates, memos and postmortems, `letter` for a letter or notice on letterhead, and `kr/quote`, `intl/invoice`, `kr/meeting-minutes` are company forms. A company form without a schema still uses `references/paperwork.md`.
2. Run `<skill>/scripts/office guide <schema>`. It prints the given fields as JSON Schema.
3. For a company form or a letter, call `company_info_get` for the document's language and, for a company form, `company_document_register`; `merge` prints the letterhead from the profile the first answers and the number the second returns. Never copy either into the values.
4. Write the values as one JSON object at `~/documents/<title>.values.json`. Copy names, figures and dates exactly as the request writes them; dates are `YYYY-MM-DD`, numbers are plain numbers.
5. A value the document needs that the request and attachments do not state is `null`, never a guess, a placeholder word or a value from an example. Leave out an optional field that does not apply.
6. Run `<skill>/scripts/office merge <schema> ~/documents/<title>.values.json <output>`, where `<output>` is `<storageDirectory>/<title>.pdf` for a company form, the directory its registration returned, and `~/documents/<title>.<pdf|docx>` otherwise. An error names the field path and what it takes; fix that field and run it again. Deliver the file at the path merge wrote; a copy elsewhere is not delivered.
7. Deliver the file without `render` or `check`; code drew the layout, and the host checks the values you wrote against the request when you finish. The result's `details.blanks` lists every blank field, each drawn as a blank line: name exactly those, and say the person can fill them in by hand or send the values for you to complete the same file. `details.emptyOptional` lists optional fields left empty, such as a spec column; mention them as empty, not as blanks. Name no blank and no file the result does not list.
8. When the host names a value the request does not support, change only that value in the values file, or set it to `null` so it becomes a blank, and run the same `merge` to the same file.

## Complete or correct it

When the person sends a missing value or a correction, change only those fields in the same values file and run the same `merge` to the same output. The file keeps its document number and date.

## Reports and letters

`report` and `letter` hold sections of blocks you choose from: `paragraph`, `items`, `table`, `fields` and `chart`. Write a section, item, row or paragraph only for content the request gives. A table's cells follow its columns' types, and `totals` adds the sum row.

## Workbooks

A new workbook is a declaration at `~/documents/<title>.workbook.json`, built with `<skill>/scripts/office create ~/documents/<title>.xlsx ~/documents/<title>.workbook.json`. `office guide create xlsx` lists its fields. Declare each source table's columns with a type and a role, a dimension such as year, region or product, or a measure that is summed. An attached CSV or TSV is read through `csvPath`, the attachment's path, never typed into rows; `create` refuses typed rows while an attached table is unread. Rows from the request's own text are given exactly as it writes them, with `null` for a value not given, never 0. Then declare views: `rows` and `columns` name dimensions, `measure` or `measures` what the cells sum, `totals` adds a total row, and `add` adds computed columns such as `percentChange(revenue, year)`, `share(revenue, region)` or `(actual - budget) / budget`. A chart names a view. You never write a formula or a cell reference; the compiler writes them, with number formats from each column's unit. The result's `details.views` shows each view as it displays, and `details.blanks` the missing inputs; check those instead of reading the file back, and quote every figure the reply names from `details.views` as it displays there, never a sum or ratio you work out yourself. A sum missing an input adds the values given, is marked `*`, and the note under its view names what is missing; a share of a marked sum is marked too, and a comparison or variance between cells that do not cover the same records stays blank, with a note under the view naming the member that covers less, such as `2026 (3 of 4 Quarter)`. To change or complete the workbook, change the declaration and run the same `create` to the same file; `apply` refuses to change a compiled cell. Change a user's existing workbook with `references/sheet.md`.
