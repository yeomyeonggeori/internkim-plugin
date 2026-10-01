# PDF

Read, extract, merge, split, lightly edit, or create layout-critical PDFs in `~/documents`, when placement carries meaning. When it does not, write the content as Markdown and run `<skill>/scripts/office doc export ~/documents/<title>.md --output ~/documents/<title>.pdf`; the `.pdf` extension is what makes it a PDF. When the layout belongs to someone else's letterhead or contract template, fill that template with paperwork. SKILL.md's rules for source truth, totals, earlier files, naming, and verification apply here.

## Workflow

1. For an earlier or uploaded PDF, run `<skill>/scripts/office pdf read <file>` first: text, tables and size per page, and which pages are scans without text. For those, rerun with `--ocr`: it reads their text and tables from the page image and marks them `readByOcr`. OCR can drop a space or misread a character, so confirm names and amounts from those pages with the user. `office convert <file.pdf> <file.docx|md|xlsx> --ocr` does the same while converting.
2. For a short source-backed PDF, use `pdf create`, with a spec or a task-local script through `office python` only when tables or precise placement require it; `<skill>/scripts/office guide pdf` lists the spec fields. Merge and split with pypdf in a task-local script.
3. Validate with `<skill>/scripts/office pdf validate ~/documents/<title>.pdf`, passing the source facts as `--required-text`, and fix its failures before delivery.

Put source facts in extractable PDF text, not in images.

## Layout quality

Use readable margins, wrapped text, clear headings, real tables, and consistent page numbering. Keep table text concise, split very wide tables, and avoid giant titles, clipped cells, tiny text, and blank space.

## Editing

To append a section page, use `pdf edit` and save in place. To rework a PDF's words, `<skill>/scripts/office convert <file.pdf> <file.docx>`, or `<file.pptx>` for one slide per page, and edit that. For custom layout, write a task-local script and run it through `office python`; preserve existing pages, metadata, encryption state, and source facts unless the user requests a change.

## Final check

Validate the PDF and confirm every required source value is extractable. Then run `<skill>/scripts/office pdf render <file>` and look at `contact-sheet.png`, and at any page it shows a problem on, in `page-NNN.png`: clipped cells, overflow, missing Korean glyphs, blank pages. `pdf render --help` shows how to pick pages and enlarge small text.
