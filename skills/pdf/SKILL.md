---
name: pdf
description: Work with existing PDF files (read, extract, merge, split, edit with pypdf) and build layout-critical PDFs with fpdf2 when precise visual placement is the point. When the words matter more than where they sit — a report, a memo, a document that happens to ship as PDF — write the content as markdown and export it instead of placing it by hand. Do not lay out a standardized company letterhead form (견적서, 청구서, 발주서, 품의서, 증명서, quotation, invoice, purchase order, certificate) — fill the issuer's own template so the layout stays theirs.
compatibility: Requires python3, uv, network access on first run to install fpdf2 and pypdf, and a Korean-capable TTF or TTC font for CJK output.
---


In every terminal command below, `<skill>` is this skill's own directory — the one holding this `SKILL.md`.

# PDF

Read, extract, merge, split, lightly edit, or create layout-critical PDFs in `~/documents`, then validate and deliver only accepted final files. Reach for this skill when placement carries meaning. When it does not, write the content and export it; when the layout belongs to someone else's letterhead or contract template, fill that template rather than redrawing it.

## Workflow

1. For an earlier PDF, use the workspace file in `~/documents/`, not a delivered attachment. A simple append uses `scripts/edit_pdf.py`; preview a newly uploaded file before extraction.
2. For a short source-backed PDF, use `scripts/create_pdf.py`; use a spec or task-local Python only when tables or precise placement require it. Run all generation and validation through `<skill>/scripts/skill_runtime.py`; bundled scripts own dependency setup.
3. Save the final PDF to `~/documents/<title>.pdf` and deliver it. Preserve the same name for follow-up edits and do not deliver intermediate files.

## Source truth and validation

Supplied files and pasted data are the source of truth. Preserve names, products, people, dates, amounts, IDs, and units exactly, put source facts in extractable PDF text, and use “Not provided” for missing fields. For numeric documents, compute totals from source numbers in code and assert the computed total equals the source-provided total before writing the final PDF.

Validate with `validate_pdf.py` or an equivalent pypdf check for page count, extractable PDF text, required source facts, forbidden unsupported facts, encryption, embedded fonts, and Korean-capable fonts. Read warnings and revise missing text, overflow, glyph, or layout failures before delivery. Use a local Korean-capable TTF or TTC font for CJK text; never rely on built-in Latin fonts for Korean.

## Layout quality

Use readable margins, wrapped text, clear headings, real tables, and consistent page numbering when appropriate. Keep table text concise, split very wide tables, and avoid giant title blocks, clipped cells, tiny text, and excess blank space. Use formulas or source totals consistently and keep output content separate from dependency caches.

## Editing and runtime

For ordinary edits, use the deterministic bundled editor and save in place. For custom layout, create a task-local script and run it through the bundled runtime; preserve existing pages, metadata, encryption state, and source facts unless the user requests a change. Do not run package installers directly or use inline shell/Python workarounds in place of bundled scripts.

## Final check

Reopen or validate the PDF, confirm all required source values are extractable, inspect page fit and Korean glyphs, then deliver only the accepted output. Report any visual uncertainty honestly.
