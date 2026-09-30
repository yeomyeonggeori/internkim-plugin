# Word Documents

Create or modify Word documents as local `.docx` files, PDF on request, authored from a Markdown source of truth. SKILL.md's rules for source truth, earlier files, naming, and verification apply here.

## Workflow

1. Clarify only when a missing source file, legal recipient, or required approval makes safe work impossible. For a new report, memo, guide, or template, choose a useful title, audience framing, sections, and structure from intent.
2. For an earlier document, revise `content.md` when it exists beside the file; otherwise append with `doc edit`, or rewrite with a task-local script run through `office python`.
3. For a newly uploaded file, read its exact workspace path before extraction, work directly in `~/documents/`, and keep the Markdown source beside the output for follow-up edits.
4. For content-first documents, write complete Markdown at `~/documents/<title>.md` before running any terminal command. Then run `<skill>/scripts/office doc export ~/documents/<title>.md --output ~/documents/<title>.docx`. Use `doc create` with a spec only when precise margins, orientation, tables, columns, or fonts are the point.
5. Validate with `<skill>/scripts/office doc validate ~/documents/<title>.docx`, passing source names, dates, totals, and key labels as `--required-text` values and unsupported claims as `--forbidden-text` values.

## Source and layout quality

Use real Word tables for structured data, concise headers, sensible widths, readable margins, and Korean-capable fonts. Body text is normally 10–11 pt with compact headings and line spacing around 1.05–1.2; avoid giant titles, tiny cells, clipped tables, and excess blank space.

For business reports, make a source checklist of names, dates, totals, percentages, owners, missing values, and forbidden invented facts, and confirm those values appear in the document body after generation. Fix warnings for dense cells, blank cells, wide tables, missing text, font problems, or unreadable spacing.

## Editing

Use `doc edit` for straightforward appends. For deletion, rewrite, or style changes, write a task-local Python file and run it through `office python`; preserve complex headers, comments, tracked changes, fields, namespaces, relationships, and content types. Inspect package XML only when the normal library cannot preserve the feature.

## Final check

Confirm required source facts and visible headings, inspect table fit and Korean glyphs, then attach the accepted file. For a contract, preserve every standard clause and checklist item from its governing spec.
