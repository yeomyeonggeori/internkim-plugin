---
name: document
description: Create, read, edit, and attach text documents — .docx by default, PDF on request — authored from a markdown source of truth. Use for Word documents, reports, memos, letters, templates, tracked changes review, comments, document cleanup, 워드, 문서, 보고서, 메모, 서식, PDF 보고서, or docx requests. Do not use for spreadsheets, slide decks, or manipulating existing PDF files. For standardized company forms and contracts (견적서, 품의서, 증명서, 근로계약서, NDA, quotation, invoice, certificate, contract) follow the paperwork skill, which reuses these scripts with its own document specs.
compatibility: Requires python3, a terminal, and InternKim's tool server.
tool-references: read
---


In every terminal command below, `<skill>` is this skill's own directory — the one holding this `SKILL.md`.

# DOCX Documents

Create or modify Word documents as local `.docx` files, then validate and attach the accepted final file. Treat supplied files and pasted data as the source of truth: preserve names, products, people, dates, amounts, IDs, and units exactly. Missing values use the user's-language equivalent of “Not provided”; never invent contacts, totals, vendors, or background.

## Workflow

1. Clarify only when a missing source file, legal recipient, or required approval makes safe work impossible. For a new report, memo, guide, or template, choose a useful title, audience framing, sections, and structure from intent.
2. For an earlier document, use the workspace file in `~/documents/`, not a delivered attachment. Read the exact workspace path before answering or changing it. If `content.md` exists beside it, revise that markdown source; otherwise use the bundled editor for an append or a task-local script through the bundled runtime for a rewrite.
3. For a newly uploaded file, read its exact workspace path before extraction. Work directly in `~/documents/`; keep the markdown source beside the output for follow-up edits.
4. For content-first documents, write complete markdown at `~/documents/<title>.md` before running any terminal command. Then run `python3 <skill>/scripts/skill_runtime.py python <skill>/scripts/export_document.py ~/documents/<title>.md --output ~/documents/<title>.docx`. Use `scripts/create_docx.py` with a spec only when precise margins, orientation, tables, columns, or fonts are the point.
5. Validate with `python3 <skill>/scripts/skill_runtime.py python <skill>/scripts/validate_docx.py ~/documents/<title>.docx`, passing source names, dates, totals, and key labels as `--required-text` values and unsupported claims as `--forbidden-text` values. Read warnings and revise real quality problems before delivery.
6. Save the accepted final to `~/documents/<title>.docx` and deliver it. Keep the same filename for later edits or deletion; do not deliver intermediate files unless requested.

## Source and layout quality

Put the source-provided title, organization, period, and key metrics in visible document text, not only the filename or final reply. Use real Word tables for structured data, concise headers, sensible widths, readable margins, and Korean-capable fonts. Body text is normally 10–11 pt with compact headings and line spacing around 1.05–1.2; avoid giant titles, tiny cells, clipped tables, and excess blank space.

For business reports, make a source checklist of names, dates, totals, percentages, owners, missing values, and forbidden invented facts. Confirm those values appear in the document body after generation. Use formulas or source totals consistently and fix warnings for dense cells, blank cells, wide tables, missing text, font problems, or unreadable spacing.

## Editing and validation

Use `scripts/edit_docx.py` for straightforward appends. For deletion, rewrite, or style changes, create a task-local Python file and run it through `<skill>/scripts/skill_runtime.py`; preserve complex headers, comments, tracked changes, fields, namespaces, relationships, and content types. Inspect package XML only when the normal library cannot preserve the feature.

Bundled scripts own dependency setup through `skill_runtime.py`, which selects the built-in environment and prepares requester-owned fallback storage when needed. Use only workspace paths exposed by the runtime and keep dependency caches separate from source documents. The paperwork skill owns standardized forms and contracts, including letterhead and fixed clauses; do not replace them with a generic DOCX.

## Final check

Read the accepted file or validate it with the bundled validator, confirm required source facts and visible headings, inspect table fit and Korean glyphs, then attach only the accepted output. For a contract, preserve every standard clause and checklist item from its governing spec and state in the reply that it is a draft for review.
