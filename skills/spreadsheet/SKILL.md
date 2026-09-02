---
name: spreadsheet
description: Create, read, edit, clean, calculate, format, and attach spreadsheet files. Use for .xlsx, .xlsm, .csv, .tsv, Excel, tables, formulas, charts, spreadsheet cleanup, 엑셀, 스프레드시트, 시트, 표, or 계산표 requests. Do not use when the primary deliverable is a Word document, PDF, slide deck, or database pipeline.
compatibility: Requires python3, uv, and network access on first run to install openpyxl.
metadata:
  kim.intern.tool-references: "shell"
---


# XLSX Spreadsheets

Create or modify local workbook artifacts, validate the accepted result, and attach the final file. Treat supplied data as the source of truth: preserve names, products, people, dates, amounts, IDs, and units exactly; never invent prices, taxes, totals, contacts, or external context. Put source titles, projects, clients, events, and periods in visible worksheet cells, and use “Not provided” for missing values.

## Workflow

1. Clarify only missing columns, source data, formulas, or format choices that affect structure.
2. For a workbook from an earlier task, use the workspace file in `~/documents/`, not a delivered attachment. Preview a newly uploaded file before extraction. Keep the same file for follow-up edits.
3. Work in `~/documents/`. Use `scripts/create_xlsx.py` for straightforward workbooks, `scripts/edit_xlsx.py` for simple appends, and a task-local Python file through `<skill>/scripts/skill_runtime.py` for charts, macros, advanced formulas, or substantial edits. The typed descriptors and scripts define exact payload fields; do not copy their schemas into this guide.
4. Parse CSV and TSV with Python's `csv`, preserve malformed data for review, and never silently drop rows or columns. Put uncertain rows in a separate `Issues` sheet when they cannot be repaired confidently.
5. Validate with `scripts/validate_xlsx.py` or by reopening the workbook. Fix warnings for missing filters, frozen headers, blank headers, broken formulas, suspicious totals, and unsupported source values before delivery.
6. Save the accepted final to `~/documents/<title>.xlsx` and deliver it. Deliver source CSVs only when requested.

## Workbook quality

Use clear sheet names, readable widths, frozen header rows, professional number formats, and filters on every row-and-column table. Keep summary and detail views separate for budgets, operations, and finance. Use formulas when the workbook must stay interactive, preserve a visible source total when provided, and verify row-level formulas reference the same row.

Treat `offRowFormulaCount` as a defect unless a formula intentionally references another sheet or aggregate range. When a heading shifts the table, inspect the generated formula references rather than assuming a helper repaired them. Preserve formulas, styles, sheet names, and macros during edits unless the user asks otherwise.

## Editing and runtime

For simple appends, the deterministic editor targets the newest workbook when no path is supplied; named older files use their explicit workspace path. For rewrites, deletions, or style changes, use task-local code through the bundled runtime and preserve workbook features. Bundled scripts own dependency setup through `skill_runtime.py`; keep caches separate from source files and do not run package installers directly.

## Final check

Reopen or validate the workbook, check dimensions, formula references, filters, frozen panes, blank required cells, totals, and visible source facts. Revise real warnings before attaching only the accepted output.
