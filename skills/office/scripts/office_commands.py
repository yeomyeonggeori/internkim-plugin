from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    format_name: str
    verb: str
    script: str
    summary: str
    details: str = ""
    needs_packages: bool = True

    @property
    def words(self) -> list[str]:
        return [self.format_name, self.verb] if self.verb else [self.format_name]

    @property
    def name(self) -> str:
        return " ".join(self.words)

    @property
    def description(self) -> str:
        sentence = self.summary[0].upper() + self.summary[1:] + "."
        return f"{sentence} {self.details}" if self.details else sentence


@dataclass(frozen=True)
class Format:
    name: str
    summary: str
    definitions_script: str


FORMATS = (
    Format("doc", "Word documents (.docx), and PDFs exported from Markdown", "doc/doc_definitions.py"),
    Format("pdf", "PDF files", "pdf/pdf_definitions.py"),
    Format("sheet", "workbooks (.xlsx)", "sheet/sheet_definitions.py"),
    Format("deck", "slide decks built from slides.html, and .pptx files to read, edit and check", "deck/deck_definitions.py"),
    Format("paperwork", "Korean company forms and contracts on letterhead", "paperwork/paperwork_definitions.py"),
    Format("convert", "conversions between office formats", "convert/convert_definitions.py"),
)

COMMANDS = (
    Command("doc", "export", "doc/export_document.py", "write a .docx or .pdf from a Markdown source", "Links, local images and nested lists are kept."),
    Command("doc", "create", "doc/create_docx.py", "build a .docx from blocks or a JSON spec", "office guide doc describes the spec."),
    Command("doc", "edit", "doc/edit_docx.py", "append blocks to a .docx", "Edits the file in place."),
    Command("doc", "read", "doc/read_docx.py", "list a .docx's blocks, headers, footers and comments by index", "Charts come with their data, and tracked changes are listed. Block indexes, chart indexes, comment ids and revision ids are what doc apply takes; block text reads as if every tracked change were accepted."),
    Command("doc", "apply", "doc/apply_docx.py", "apply a batch of edits to a .docx, all or none, with --dry-run", "office guide doc lists the operations."),
    Command("doc", "merge", "doc/merge_docx.py", "fill a .docx template's {{ placeholders }} from a values file", "{% %} tags work too, and a table row that names {{ items.field }} for a list repeats once per item. Refuses to write when a placeholder has no value."),
    Command("doc", "render", "doc/render_docx.py", "lay out a .docx page by page and draw page images, contact sheets and a PDF to look at", "It draws page size and margins, styles, numbering, tables, pictures, headers, footers and footnotes."),
    Command("doc", "check", "doc/check_docx.py", "find placeholders left, broken references, a stale contents list, missing fonts or pictures, empty charts or headings, open comments and blank fields", "It also flags a wrong East Asian language and tracked changes. Issues suggest a doc apply operation where one fixes them."),
    Command("doc", "validate", "doc/validate_docx.py", "check a .docx for required text, fonts and layout"),
    Command("pdf", "create", "pdf/create_pdf.py", "lay out a PDF from blocks or a JSON spec", "office guide pdf describes the spec."),
    Command("pdf", "edit", "pdf/edit_pdf.py", "append a section page to a PDF", "Edits the file in place."),
    Command("pdf", "read", "pdf/read_pdf.py", "list a PDF's text by page, with page sizes and which pages have extractable text", "Each page also gives the rows of every table found on it, ruled or laid out in aligned columns."),
    Command("pdf", "render", "pdf/render_pdf.py", "render PDF pages to PNG files and a contact sheet to look at"),
    Command("pdf", "validate", "pdf/validate_pdf.py", "check a PDF for pages, extractable text and fonts"),
    Command("sheet", "create", "sheet/create_xlsx.py", "build an .xlsx from rows or a JSON spec", "office guide sheet describes the spec."),
    Command("sheet", "edit", "sheet/edit_xlsx.py", "append rows to an .xlsx", "Edits the file in place."),
    Command("sheet", "read", "sheet/read_xlsx.py", "list a workbook's sheets, charts and features, and a range's values, formulas, column stats or formats", "Each sheet comes with its dimensions, panes, filter, tables and merged cells, and the workbook with its defined names."),
    Command("sheet", "apply", "sheet/apply_xlsx.py", "apply a batch of edits to a workbook, all or none, with --dry-run", "office guide sheet lists the operations."),
    Command("sheet", "check", "sheet/check_xlsx.py", "find computed formula errors, missing sheets, broken names, numbers too wide for their column, numbers, dates and formulas stored as text, charts without data and template placeholders", "It also compares stored formula values with computed ones, and flags unknown functions and pivots with empty values."),
    Command("sheet", "merge", "sheet/merge_xlsx.py", "fill an .xlsx template's {{ placeholders }} from a values file", "A cell that is one placeholder takes the value's type; a row that names {{ items.field }} for a list repeats once per item, moving the rows below down and growing ranges that end on it, and an empty list leaves it blank. Refuses to write when a placeholder has no value."),
    Command("sheet", "render", "sheet/render_xlsx.py", "lay out each sheet as printed pages and draw page images, contact sheets and a PDF to look at", "It draws the print area, page setup and scaling, column widths, row heights, merges, number formats as displayed, fonts, fills, borders, conditional colors, charts and pictures."),
    Command("sheet", "validate", "sheet/validate_xlsx.py", "check an .xlsx for frozen headers, filters and blank headers"),
    Command("deck", "check", "deck/check_deck.py", "check slides.html for layout, chart, image, placeholder, slide-count and palette defects without rendering, or a .pptx for overflow, off-slide and overlapping shapes, with slide images and contact sheets to look at", "slides.html is checked without rendering, and deck build runs this first. A .pptx's text is measured with the deck's fonts, each issue names an operation deck apply accepts, and the preview is drawn from the same geometry, styles and fonts."),
    Command("deck", "build", "deck/build_deck.py", "check slides.html, then render it to PDF (default), PPTX or HTML with review evidence", "It draws without a browser into build/<name>.pdf (or .pptx, .html) with review images, geometry and an acceptance verdict.", needs_packages=False),
    Command("deck", "read", "deck/read_pptx.py", "list a .pptx's slides with each shape's index, kind, box, text and style, tables, charts and notes", "Each shape has the index deck apply takes (3.1 is the second shape inside group 3), its id, name, kind, placeholder type, box in EMU and in percent of the slide, and its text with the effective font, size, bold and color. Shapes are listed back to front; links, transitions, comments and sections appear where the deck has them."),
    Command("deck", "apply", "deck/apply_pptx.py", "apply a batch of edits to a .pptx, all or none, with --dry-run, and report the layout problems they leave", "office guide deck lists the operations. Overflowing text, shapes off the slide and overlaps are reported on every slide the batch changed, each with an operation that fixes it."),
    Command("deck", "merge", "deck/merge_pptx.py", "fill a .pptx template's {{ placeholders }} from a values file, repeating table rows per list item", "Refuses to write when a placeholder has no value."),
    Command("deck", "restore", "deck/restore_source.py", "recover the small authored slides.html from a delivered deck .html", "The kit, viewer and vendored fonts are removed, and inlined images and fonts point back at their files.", needs_packages=False),
    Command("deck", "image", "deck/fetch_image.py", "download up to three public-domain photos for an English search query, with each one's size, ratio, licence and source", "Photos are CC0 or public domain, saved as <output>, <output stem>-2 and -3 in the output's format, each with its creator."),
    Command("paperwork", "render", "paperwork/render_paperwork.py", "render a company form to PDF on letterhead", "A contract renders to .docx; office guide paperwork describes both."),
    Command("paperwork", "fill", "paperwork/fill_template.py", "fill a standard contract template to .docx", "office guide paperwork lists each template's fields."),
    Command("convert", "", "convert/convert_file.py", "convert a file to another format, such as docx to md, pdf to docx, or xlsx to csv", "The input and output extensions pick the route; office guide convert lists every route."),
    Command("paperwork", "check", "paperwork/check_amounts.py", "report row amounts, totals, VAT and the amount in words of a priced form, never rewriting it", "office guide paperwork lists the rules.", needs_packages=False),
)


def find_command(words: list[str]) -> Command | None:
    return next((command for command in COMMANDS if words[:len(command.words)] == command.words), None)


def find_format(name: str) -> Format | None:
    return next((office_format for office_format in FORMATS if office_format.name == name), None)
