from __future__ import annotations

from core.office_commands import OCR_NEED, OCR_SETUP_COMMAND
from core.office_result import BOLD_FONT_UNAVAILABLE, ERROR, WARNING, IssueKind
from doc.doc_definitions import GLYPH_NOT_COVERED
from render.renderer import RENDER_FAILED, RENDERER_UNAVAILABLE
from core.office_schema import Boolean, CellValue, Choice, Field, ListOf, Number, Record, Text, Variant
from fonts.font_files import FONT_NAME_MEANING, FONT_PATH_MEANING
from core.text_checks import TEXT_CHECK_ISSUE_KINDS
from core.office_operations import OPERATION_ISSUE_KINDS
from core.page_selection import PAGE_NOT_IN_DOCUMENT
from core.page_sizes import DEFAULT_PAPER, PAPER_NAMES


TABLE = Record("table", "a table with a shaded header row, wrapped to the page width", (
    Field("headers", ListOf(CellValue(), non_empty=True), "header cells", required=True),
    Field("rows", ListOf(ListOf(CellValue())), "body rows; missing cells print empty"),
))

SECTION = Record("section", "a heading followed by paragraphs, bullets, then an optional table; text reads **bold**, *emphasis*, `code` and [links](url) as Markdown does", (
    Field("title", Text(), "section heading"),
    Field("paragraphs", ListOf(Text(non_empty=True)), "body paragraphs"),
    Field("bullets", ListOf(Text(non_empty=True)), "bullet items"),
    Field("table", TABLE, "a table after the text"),
))

PDF_SPECIFICATION = Record("document", "the JSON spec office create draws a .pdf from, with the look of a document made from Markdown", (
    Field("title", Text(), "large title"),
    Field("subtitle", Text(), "smaller line under the title"),
    Field("format", Choice(PAPER_NAMES), f"paper size; default {DEFAULT_PAPER.name}"),
    Field("marginMillimeters", Number(minimum=0), "every margin; by default a document's margins"),
    Field("fontPath", Text(), FONT_PATH_MEANING),
    Field("fontName", Text(), FONT_NAME_MEANING),
    Field("pageNumbers", Boolean(), "centered page numbers in the footer, default true"),
    Field("sections", ListOf(SECTION), "the content"),
))

OPERATIONS = Variant(
    "operation",
    "one edit of office apply on a .pdf; the pages the file has are kept as they are, and the batch applies whole or not at all unless --mode says otherwise",
    "op",
    (
        Record("append_section", "add pages at the end holding one section, on the paper size of the last page", SECTION.fields),
    ),
)

PDF_ENCRYPTED = IssueKind("PDF_ENCRYPTED", WARNING, "the PDF is encrypted", "deliver an unencrypted copy unless the user asked for protection")
NO_TEXT_LAYER = IssueKind("NO_TEXT_LAYER", ERROR, "no text can be extracted from the PDF", "write the content as text, not as images")
TEXT_TOO_SHORT = IssueKind("TEXT_TOO_SHORT", ERROR, "extracted text is shorter than --minimum-text-length", "check that every section of the source made it in")
TOO_FEW_PAGES = IssueKind("TOO_FEW_PAGES", ERROR, "the PDF has fewer pages than --minimum-pages", "add the missing content")
TOO_MANY_PAGES = IssueKind("TOO_MANY_PAGES", ERROR, "the PDF has more pages than --maximum-pages", "tighten the layout or cut content the user did not ask for")
REQUIRED_FONT_MISSING = IssueKind("REQUIRED_FONT_MISSING", ERROR, "no font name contains --required-font", "embed the required font")
NO_FONT_RESOURCES = IssueKind("NO_FONT_RESOURCES", WARNING, "no page declares a font resource", "check whether the text was drawn as images")
KOREAN_FONT_MISSING = IssueKind("KOREAN_FONT_MISSING", ERROR, "Korean text is drawn with a font the PDF neither embeds nor declares as Korean, so a reader shows boxes or wrong glyphs", "rebuild the PDF with office create or office convert, which embed a Korean font")
KOREAN_FONT_NOT_EMBEDDED = IssueKind("KOREAN_FONT_NOT_EMBEDDED", WARNING, "Korean text is drawn with a declared Korean font the PDF does not embed, so each reader substitutes its own", "rebuild the PDF with office create or office convert, which embed the font")


PAGE_WITHOUT_TEXT = IssueKind("PAGE_WITHOUT_TEXT", WARNING, "a PDF page has no text layer: it is a scan or a picture", f"rerun the command with --ocr to read those pages' text ({OCR_NEED}), or draw them with office render --pages and read each PNG with your own image tool")
PAGE_READ_BY_OCR = IssueKind("PAGE_READ_BY_OCR", WARNING, "the text of a page without a text layer was read from its image by OCR: a space between words can be missing and a character can be misread", "tell the user which pages came from OCR, and confirm names, amounts and dates that matter with them before relying on them")
OCR_UNAVAILABLE = IssueKind("OCR_UNAVAILABLE", WARNING, "the OCR engine is not prepared or could not run, so pages without a text layer were not read", f"say which pages could not be read and why; the message names what is missing, usually the engine that {OCR_SETUP_COMMAND} prepares")

WRITE_ISSUE_KINDS = (BOLD_FONT_UNAVAILABLE, GLYPH_NOT_COVERED, RENDERER_UNAVAILABLE, RENDER_FAILED)
RENDER_ISSUE_KINDS = (PAGE_NOT_IN_DOCUMENT,)
READ_ISSUE_KINDS = (PAGE_WITHOUT_TEXT, PAGE_READ_BY_OCR, OCR_UNAVAILABLE)

CHECK_ISSUE_KINDS = (
    PDF_ENCRYPTED,
    NO_TEXT_LAYER,
    TEXT_TOO_SHORT,
    TOO_FEW_PAGES,
    TOO_MANY_PAGES,
    *TEXT_CHECK_ISSUE_KINDS,
    REQUIRED_FONT_MISSING,
    NO_FONT_RESOURCES,
    KOREAN_FONT_MISSING,
    KOREAN_FONT_NOT_EMBEDDED,
)

GUIDE_INPUTS = (
    ("create", "pdf", "the JSON spec", PDF_SPECIFICATION),
    ("apply", "pdf", "the operations", ListOf(OPERATIONS, non_empty=True)),
)
GUIDE_ISSUES = (
    ("create", "pdf", WRITE_ISSUE_KINDS),
    ("apply", "pdf", WRITE_ISSUE_KINDS + OPERATION_ISSUE_KINDS),
    ("read", "pdf", READ_ISSUE_KINDS),
    ("render", "pdf", RENDER_ISSUE_KINDS),
    ("check", "pdf", CHECK_ISSUE_KINDS),
)


def page_reading_suggestion(pdf_path, pages: str, rerun_command: str | None) -> str:
    rendering = f"run office render {pdf_path} --pages {pages} --scale 2 and read each page PNG with your own image tool"
    if rerun_command is None:
        return f"{rendering}, or tell the user these pages could not be read"
    return f"rerun with --ocr to read their text: {rerun_command} --ocr ({OCR_NEED}); or {rendering}"
