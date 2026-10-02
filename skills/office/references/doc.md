# Word Documents

Create or modify Word documents as local `.docx` files, PDF on request, authored from a Markdown source of truth. The output's extension picks the format: `office create ~/documents/<title>.pdf ~/documents/<title>.md` writes the PDF from the same Markdown. SKILL.md's rules for source truth, earlier files, naming, and verification apply here.

## Workflow

1. Clarify only when a missing source, recipient, or approval makes safe work impossible. For a new report, memo, guide, or template, choose a useful title, audience framing, sections, and structure from intent.
2. For an earlier document, revise its Markdown source `<title>.md` when it exists beside the file and export again. Otherwise run `<skill>/scripts/office read <file>`, then change the file with `office apply <file> <ops.json>`: one batch of operations, every block index taken from that read, applied whole or not at all. Pass `--dry-run` first when the batch is long.
3. For a newly uploaded file, read its exact workspace path before extraction, work directly in `~/documents/`, and keep the Markdown source beside the output for follow-up edits.
4. For content-first documents, write complete Markdown at `~/documents/<title>.md` before running any terminal command. Then run `<skill>/scripts/office create ~/documents/<title>.docx ~/documents/<title>.md`. Links, images, ```chart fences and LaTeX become native Word parts; `<skill>/scripts/office guide md` lists what the Markdown may hold. Pass a JSON spec instead of Markdown only when precise margins, orientation, columns, or fonts are the point; `office guide create docx` lists its fields.
5. Check with `<skill>/scripts/office check ~/documents/<title>.docx`, passing source names, dates, totals, and key labels as `--required-text` values and unsupported claims as `--forbidden-text` values.

## Source and layout quality

Use real Word tables for structured data, with concise headers and sensible widths. Keep the body size and spacing the export sets; avoid giant titles, tiny cells, clipped tables, and blank space.

For business reports, make a source checklist of names, dates, totals, percentages, owners, missing values, and forbidden invented facts, and confirm those values appear in the document body after generation. Fix every warning `office check` reports.

## Editing

`office apply` edits the file in place, and `office guide apply docx` lists every operation. Parts no operation touches keep their XML. When the reader should see what changed, as in a contract under negotiation, pass `--track`: edits are written as tracked changes under `--author`. `office read` shows comment threads and `--revisions` lists tracked changes; settle those with `accept_revisions` or `reject_revisions`. Work no operation covers goes in a task-local script run through `office python`.

## Templates

A user's .docx, .xlsx or .pptx template with `{{ name }}` placeholders is filled with `<skill>/scripts/office merge <template> <values.json> <output>`. It refuses to write while any placeholder has no value and warns about values the template never uses, usually a misspelled name.

## Final check

Run `office check`; each issue's `fix` holds the `office apply` operations that clear it. Confirm required source facts and visible headings. Before attaching, look at the pages `<skill>/scripts/office render <file>` draws; on `PAGES_NOT_RENDERED`, say the layout was not seen. For a contract, preserve every standard clause and checklist item from its governing spec.
