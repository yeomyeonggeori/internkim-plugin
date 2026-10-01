from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    format_name: str
    verb: str
    script: str
    summary: str
    needs_packages: bool = True

    @property
    def words(self) -> list[str]:
        return [self.format_name, self.verb] if self.verb else [self.format_name]

    @property
    def name(self) -> str:
        return " ".join(self.words)


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
    Command("doc", "export", "doc/export_document.py", "write a .docx or .pdf from a Markdown source"),
    Command("doc", "create", "doc/create_docx.py", "build a .docx from blocks or a JSON spec"),
    Command("doc", "edit", "doc/edit_docx.py", "append blocks to a .docx"),
    Command("doc", "read", "doc/read_docx.py", "list a .docx's blocks, headers, footers and comments by index"),
    Command("doc", "apply", "doc/apply_docx.py", "apply a batch of edits to a .docx, all or none, with --dry-run"),
    Command("doc", "merge", "doc/merge_docx.py", "fill a .docx template's {{ placeholders }} from a values file"),
    Command("doc", "render", "doc/render_docx.py", "lay out a .docx page by page as preview HTML to look at"),
    Command("doc", "check", "doc/check_docx.py", "find placeholders left, broken cross-references, a stale contents list and missing East Asian fonts"),
    Command("doc", "validate", "doc/validate_docx.py", "check a .docx for required text, fonts and layout"),
    Command("pdf", "create", "pdf/create_pdf.py", "lay out a PDF from blocks or a JSON spec"),
    Command("pdf", "edit", "pdf/edit_pdf.py", "append a section page to a PDF"),
    Command("pdf", "read", "pdf/read_pdf.py", "list a PDF's text by page, with page sizes and which pages have extractable text"),
    Command("pdf", "render", "pdf/render_pdf.py", "render PDF pages to PNG files and a contact sheet to look at"),
    Command("pdf", "validate", "pdf/validate_pdf.py", "check a PDF for pages, extractable text and fonts"),
    Command("sheet", "create", "sheet/create_xlsx.py", "build an .xlsx from rows or a JSON spec"),
    Command("sheet", "edit", "sheet/edit_xlsx.py", "append rows to an .xlsx"),
    Command("sheet", "read", "sheet/read_xlsx.py", "list a workbook's sheets, charts and features, and a range's values, formulas, column stats or formats"),
    Command("sheet", "apply", "sheet/apply_xlsx.py", "apply a batch of edits to a workbook, all or none, with --dry-run"),
    Command("sheet", "check", "sheet/check_xlsx.py", "find computed formula errors, missing sheets, broken names, numbers too wide for their column, charts without data and template placeholders"),
    Command("sheet", "merge", "sheet/merge_xlsx.py", "fill an .xlsx template's {{ placeholders }} from a values file"),
    Command("sheet", "render", "sheet/render_xlsx.py", "lay out each sheet as printed pages of preview HTML to look at"),
    Command("sheet", "validate", "sheet/validate_xlsx.py", "check an .xlsx for frozen headers, filters and blank headers"),
    Command("deck", "check", "deck/check_deck.py", "check slides.html for layout, chart, image, placeholder, slide-count and palette defects without rendering, or a .pptx for overflow, off-slide and overlapping shapes, with an HTML preview to look at"),
    Command("deck", "build", "deck/build_deck.py", "check slides.html, then render it to PDF (default), PPTX or HTML with review evidence", needs_packages=False),
    Command("deck", "validate", "deck/validate_pptx.py", "check a .pptx for design warnings"),
    Command("deck", "read", "deck/read_pptx.py", "list a .pptx's slides with each shape's index, kind, box, text and style, tables, charts and notes"),
    Command("deck", "apply", "deck/apply_pptx.py", "apply a batch of edits to a .pptx, all or none, with --dry-run, and report the layout problems they leave"),
    Command("deck", "merge", "deck/merge_pptx.py", "fill a .pptx template's {{ placeholders }} from a values file, repeating table rows per list item"),
    Command("deck", "restore", "deck/restore_source.py", "recover controller-free slides.html from a delivered deck", needs_packages=False),
    Command("deck", "accept", "deck/accept_review.py", "check review-decision.json against the review evidence", needs_packages=False),
    Command("deck", "image", "deck/fetch_image.py", "download a public-domain photo for a search query", needs_packages=False),
    Command("paperwork", "render", "paperwork/render_paperwork.py", "render a company form to PDF on letterhead"),
    Command("paperwork", "fill", "paperwork/fill_template.py", "fill a standard contract template to .docx"),
    Command("convert", "", "convert/convert_file.py", "convert a file to another format, such as docx to md, pdf to docx, or xlsx to csv"),
    Command("paperwork", "check", "paperwork/check_amounts.py", "report row amounts, totals, VAT and the amount in words of a priced form, never rewriting it", needs_packages=False),
)


def find_command(words: list[str]) -> Command | None:
    return next((command for command in COMMANDS if words[:len(command.words)] == command.words), None)


def find_format(name: str) -> Format | None:
    return next((office_format for office_format in FORMATS if office_format.name == name), None)
