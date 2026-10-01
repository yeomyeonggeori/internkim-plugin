from __future__ import annotations

from office_result import ERROR, WARNING, IssueKind
from office_schema import Boolean, CellValue, Field, ListOf, Number, Record, Text
from fonts.pdf_registration import FONT_NAME_MEANING, FONT_PATH_MEANING
from text_checks import TEXT_CHECK_ISSUE_KINDS


TABLE = Record("table", "a bordered table with a shaded header row, wrapped to the page width", (
    Field("headers", ListOf(CellValue(), non_empty=True), "header cells", required=True),
    Field("rows", ListOf(ListOf(CellValue())), "body rows; missing cells print empty"),
))

SECTION = Record("section", "a heading followed by paragraphs, bullets, then an optional table", (
    Field("title", Text(), "section heading"),
    Field("paragraphs", ListOf(Text(non_empty=True)), "body paragraphs"),
    Field("bullets", ListOf(Text(non_empty=True)), "bullet items"),
    Field("table", TABLE, "a table after the text"),
))

PDF_SPECIFICATION = Record("document", "the --spec file of pdf create", (
    Field("title", Text(), "large title with a rule under it"),
    Field("subtitle", Text(), "smaller line under the title"),
    Field("format", Text(non_empty=True), "page size fpdf2 knows, such as A4, A3, Letter; default A4"),
    Field("marginMillimeters", Number(minimum=0), "every margin, default 18"),
    Field("fontPath", Text(), FONT_PATH_MEANING),
    Field("fontName", Text(), FONT_NAME_MEANING),
    Field("pageNumbers", Boolean(), "centered page numbers in the footer, default true"),
    Field("sections", ListOf(SECTION), "the content"),
))

PDF_ENCRYPTED = IssueKind("PDF_ENCRYPTED", WARNING, "the PDF is encrypted", "deliver an unencrypted copy unless the user asked for protection")
NO_TEXT_LAYER = IssueKind("NO_TEXT_LAYER", ERROR, "no text can be extracted from the PDF", "write the content as text, not as images")
TEXT_TOO_SHORT = IssueKind("TEXT_TOO_SHORT", ERROR, "extracted text is shorter than --minimum-text-length", "check that every section of the source made it in")
TOO_FEW_PAGES = IssueKind("TOO_FEW_PAGES", ERROR, "the PDF has fewer pages than --min-pages", "add the missing content")
TOO_MANY_PAGES = IssueKind("TOO_MANY_PAGES", ERROR, "the PDF has more pages than --max-pages", "tighten the layout or cut content the user did not ask for")
REQUIRED_FONT_MISSING = IssueKind("REQUIRED_FONT_MISSING", ERROR, "no font name contains --required-font-substring", "embed the required font")
NO_FONT_RESOURCES = IssueKind("NO_FONT_RESOURCES", WARNING, "no page declares a font resource", "check whether the text was drawn as images")
KOREAN_FONT_NOT_EMBEDDED = IssueKind("KOREAN_FONT_NOT_EMBEDDED", ERROR, "the PDF has Korean text but embeds no font", "embed a Korean-capable font so every reader shows the glyphs")

PAGE_NOT_IN_DOCUMENT = IssueKind("PAGE_NOT_IN_DOCUMENT", ERROR, "--pages names a page the PDF does not have", "run pdf read to see the page count, then pass pages inside it")

OCR_DOWNLOAD_SIZE = "about 150 MB"
PAGE_WITHOUT_TEXT = IssueKind("PAGE_WITHOUT_TEXT", WARNING, "a PDF page has no text layer: it is a scan or a picture", f"rerun the command with --ocr to read those pages' text (the first OCR run downloads the engine, {OCR_DOWNLOAD_SIZE}), or render them with pdf render --pages and read each PNG with your own image tool")
PAGE_READ_BY_OCR = IssueKind("PAGE_READ_BY_OCR", WARNING, "the text of a page without a text layer was read from its image by OCR: a space between words can be missing and a character can be misread", "tell the user which pages came from OCR, and confirm names, amounts and dates that matter with them before relying on them")
OCR_UNAVAILABLE = IssueKind("OCR_UNAVAILABLE", WARNING, "the OCR engine could not be installed or run, so pages without a text layer were not read", "say which pages could not be read and why; the message names what failed, usually no network on the first OCR run")

RENDER_ISSUE_KINDS = (PAGE_NOT_IN_DOCUMENT,)
READ_ISSUE_KINDS = (PAGE_WITHOUT_TEXT, PAGE_READ_BY_OCR, OCR_UNAVAILABLE)

VALIDATE_ISSUE_KINDS = (
    PDF_ENCRYPTED,
    NO_TEXT_LAYER,
    TEXT_TOO_SHORT,
    TOO_FEW_PAGES,
    TOO_MANY_PAGES,
    *TEXT_CHECK_ISSUE_KINDS,
    REQUIRED_FONT_MISSING,
    NO_FONT_RESOURCES,
    KOREAN_FONT_NOT_EMBEDDED,
)

GUIDE_INPUTS = (
    ("pdf create --spec <file>", PDF_SPECIFICATION),
    ("pdf edit --section <file>", SECTION),
)
GUIDE_ISSUES = (
    ("pdf read", READ_ISSUE_KINDS),
    ("pdf render", RENDER_ISSUE_KINDS),
    ("pdf validate", VALIDATE_ISSUE_KINDS),
)


def page_reading_suggestion(pdf_path, pages: str, rerun_command: str | None) -> str:
    rendering = f"run office pdf render {pdf_path} --pages {pages} --scale 2 and read each page PNG with your own image tool"
    if rerun_command is None:
        return f"{rendering}, or tell the user these pages could not be read"
    return f"rerun with --ocr to read their text: {rerun_command} --ocr (the first OCR run downloads the engine, {OCR_DOWNLOAD_SIZE}); or {rendering}"
