# PDF

Read, extract, merge, split, lightly edit, or create layout-critical PDFs in `~/documents`, when placement carries meaning. When it does not, write the content as Markdown and run `<skill>/scripts/office create ~/documents/<title>.pdf ~/documents/<title>.md`; the `.pdf` extension is what makes it a PDF. When the layout belongs to a company form, fill it with `office merge <jurisdiction>/<form>`. SKILL.md's rules for source truth, totals, earlier files, naming, and verification apply here.

## Workflow

1. For an earlier or uploaded PDF, run `<skill>/scripts/office read <file>` first: text, tables and size per page, and which pages are scans without text. For those, rerun with `--ocr`: it reads their text and tables from the page image and marks them `readByOcr`. OCR can drop a space or misread a character, so confirm names and amounts from those pages with the user. `office convert <file.pdf> <file.docx|md|xlsx> --ocr` does the same while converting.
2. For a short source-backed PDF of headings, paragraphs, bullets and tables, use `office create <title>.pdf <spec>.json`; `<skill>/scripts/office guide create pdf` lists its fields. Merge and split with pypdf in a task-local script run through `office python`.
3. Check with `<skill>/scripts/office check ~/documents/<title>.pdf`, passing the source facts as `--required-text`, and fix its failures before delivery.

Put source facts in extractable PDF text, not in images.

## Layout quality

Use readable margins, wrapped text, clear headings, real tables, and consistent page numbering. Keep table text concise, split very wide tables, and avoid giant titles, clipped cells, tiny text, and blank space.

## Editing

To append a section page, `office apply` an `append_section` operation. To rework a PDF's words, `<skill>/scripts/office convert <file.pdf> <file.docx>`, or `<file.pptx>` for one slide per page, and edit that. For custom layout, write the page as HTML and CSS and draw it in a task-local script run through `office python`, passing a `DocumentPdfRequest` to `render.renderer.render_document_pdf`, which draws with the shipped fonts; preserve existing pages, metadata, encryption state, and source facts unless the user requests a change.

## Final check

Check the PDF and confirm every required source value is extractable. Then run `<skill>/scripts/office render <file>` and look at `contact-sheet.png`, and at any page it shows a problem on, in `page-NNN.png`: clipped cells, overflow, missing Korean glyphs, blank pages. `office render --help` shows how to pick pages and enlarge small text.
