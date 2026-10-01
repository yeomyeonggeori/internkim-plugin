# Word Documents

Create or modify Word documents as local `.docx` files, PDF on request, authored from a Markdown source of truth. SKILL.md's rules for source truth, earlier files, naming, and verification apply here.

## Workflow

1. Clarify only when a missing source file, legal recipient, or required approval makes safe work impossible. For a new report, memo, guide, or template, choose a useful title, audience framing, sections, and structure from intent.
2. For an earlier document, revise `content.md` when it exists beside the file and export again. Otherwise run `<skill>/scripts/office doc read <file>`, then change the file with `doc apply <file> <ops.json>`: one batch of operations, every block index taken from that read, applied whole or not at all. Pass `--dry-run` first when the batch is long. `doc edit` only appends.
3. For a newly uploaded file, read its exact workspace path before extraction, work directly in `~/documents/`, and keep the Markdown source beside the output for follow-up edits.
4. For content-first documents, write complete Markdown at `~/documents/<title>.md` before running any terminal command. Then run `<skill>/scripts/office doc export ~/documents/<title>.md --output ~/documents/<title>.docx`; links, local images, and nested lists carry over. Use `doc create` with a spec only when precise margins, orientation, tables, columns, or fonts are the point; `<skill>/scripts/office guide doc` lists every spec field and block type.
5. Validate with `<skill>/scripts/office doc validate ~/documents/<title>.docx`, passing source names, dates, totals, and key labels as `--required-text` values and unsupported claims as `--forbidden-text` values.

## Source and layout quality

Use real Word tables for structured data, concise headers, sensible widths, readable margins, and Korean-capable fonts. Body text is normally 10–11 pt with compact headings and line spacing around 1.05–1.2; avoid giant titles, tiny cells, clipped tables, and blank space.

For business reports, make a source checklist of names, dates, totals, percentages, owners, missing values, and forbidden invented facts, and confirm those values appear in the document body after generation. Fix warnings for dense cells, blank cells, wide tables, missing text, font problems, or unreadable spacing.

## Editing

`doc apply` edits the file in place, and `office guide doc` lists every operation. Parts no operation touches keep their XML. When the reader should see what changed, as in a contract under negotiation, pass `--track`: edits are written as tracked changes under `--author`. `doc read` shows comment threads and `--revisions` lists tracked changes; settle those with `accept_revisions` or `reject_revisions`. Work no operation covers goes in a task-local script run through `office python`.

## Templates

A user's template with `{{ name }}` placeholders is filled with `<skill>/scripts/office doc merge`, `deck merge` or `sheet merge <template> <values.json> <output>`. It refuses to write while any placeholder has no value and warns about values the template never uses, usually a misspelled name.

## Final check

Run `doc check` for placeholders left, broken cross-references, a stale table of contents, missing East Asian fonts, and Korean text tagged with another East Asian language; each issue suggests the `doc apply` operation that fixes it. Confirm required source facts and visible headings. Before attaching, look at the pages from `<skill>/scripts/office doc render <file.docx>`, or `pdf render` for a PDF; on `PAGES_NOT_RENDERED`, say the layout was not seen. For a contract, preserve every standard clause and checklist item from its governing spec.
