# PDF

Read, extract, merge, split, lightly edit, or create layout-critical PDFs in `~/documents`. Reach for this when placement carries meaning. When it does not, write the content and export it with `doc export`; when the layout belongs to someone else's letterhead or contract template, fill that template with paperwork rather than redrawing it. SKILL.md's rules for source truth, totals, earlier files, naming, and verification apply here.

## Workflow

1. For an earlier PDF, append a section page with `pdf edit`; preview a newly uploaded file before extraction.
2. For a short source-backed PDF, use `pdf create`; use a spec, or a task-local script run through `office python`, only when tables or precise placement require it. Reading, extracting, merging, and splitting use pypdf in a task-local script.
3. Validate with `<skill>/scripts/office pdf validate ~/documents/<title>.pdf`: it checks page count, extractable text, required and forbidden facts, encryption, embedded fonts, and Korean-capable fonts. Revise missing text, overflow, glyph, or layout failures before delivery.

Put source facts in extractable PDF text, not in images.

## Layout quality

Use readable margins, wrapped text, clear headings, real tables, and consistent page numbering when appropriate. Keep table text concise, split very wide tables, and avoid giant title blocks, clipped cells, tiny text, and excess blank space.

## Editing

For ordinary edits, use `pdf edit` and save in place. For custom layout, write a task-local script and run it through `office python`; preserve existing pages, metadata, encryption state, and source facts unless the user requests a change.

## Final check

Reopen or validate the PDF, confirm all required source values are extractable, inspect page fit and Korean glyphs, then deliver the accepted output.
