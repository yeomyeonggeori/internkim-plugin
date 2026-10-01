from __future__ import annotations

from dataclasses import dataclass

from office_result import ERROR, WARNING, IssueKind
from render.renderer import RENDER_FAILED, RENDERER_UNAVAILABLE


@dataclass(frozen=True)
class Route:
    source: str
    target: str
    note: str


ROUTES = (
    Route("md", "docx", "headings, lists, tables, links and local images; Korean fonts set"),
    Route("md", "html", "one self-contained page; local images embedded"),
    Route("md", "pdf", "same as doc export --format pdf"),
    Route("docx", "pdf", "each page as doc render lays it out: page size, margins, styles, tables, pictures, headers and footers"),
    Route("xlsx", "pdf", "each visible sheet as sheet render prints it: print area, scaling, number formats, fills, borders and charts"),
    Route("pptx", "pdf", "each slide as deck check previews it: shapes, text, pictures, tables and charts"),
    Route("docx", "md", "final text with tracked changes accepted; images saved beside the output; comments, notes, fields and layout dropped"),
    Route("docx", "html", "one self-contained page; same content as docx to md"),
    Route("html", "docx", "headings, paragraphs, lists, tables, bold, italic, links and images"),
    Route("html", "md", "same content as html to docx"),
    Route("pdf", "docx", "text PDFs only: paragraphs, headings by font size, lists, ruled tables, images and two-column reading order; page layout is reflowed"),
    Route("pdf", "md", "same content as pdf to docx"),
    Route("xlsx", "csv", "cached values; one file per sheet unless --sheet picks one; UTF-8 with BOM so Excel reads Korean"),
    Route("xlsx", "tsv", "same as xlsx to csv, tab-separated"),
    Route("csv", "xlsx", "typed cells, styled header, frozen header row and filter, as sheet create"),
    Route("tsv", "xlsx", "same as csv to xlsx"),
    Route("xls", "xlsx", "values, dates and merged cells; formulas kept as their values; fonts, colors, borders and widths dropped"),
    Route("ods", "xlsx", "same as xls to xlsx"),
    Route("xlsb", "xlsx", "same as xls to xlsx; formulas kept as their saved values"),
    Route("pdf", "xlsx", "each ruled table as a sheet; a table whose header repeats on the next page continues; first row is the header when it is all text; numbers, percents and dates typed; text outside tables is left out"),
)
EXTENSION_ALIASES = {"markdown": "md", "htm": "html", "xlsm": "xlsx"}

UNSUPPORTED_CONVERSION = IssueKind("UNSUPPORTED_CONVERSION", ERROR, "no route converts the input's format to the output's", "pick an output extension office guide convert lists for this input")
CONVERSION_APPROXIMATED = IssueKind("CONVERSION_APPROXIMATED", WARNING, "the output keeps the content but not everything the source had; the message says what changed", "render the output and compare it with the source before delivering")
PAGE_WITHOUT_TEXT = IssueKind("PAGE_WITHOUT_TEXT", WARNING, "a PDF page has no text layer, so it was kept as a picture whose words cannot be edited", "say which pages are pictures; reading their text needs OCR")
TABLE_NOT_FOUND = IssueKind("TABLE_NOT_FOUND", ERROR, "the PDF has no ruled table to turn into sheets, so no workbook was written", "convert it to .md to read its text, or pdf render the page and read the table from the image")
FORMULA_VALUE_MISSING = IssueKind("FORMULA_VALUE_MISSING", WARNING, "a formula cell has no saved value, so its CSV cell is empty", "run sheet apply with recalculate, then convert again")

CONVERT_ISSUE_KINDS = (UNSUPPORTED_CONVERSION, CONVERSION_APPROXIMATED, PAGE_WITHOUT_TEXT, TABLE_NOT_FOUND, FORMULA_VALUE_MISSING, RENDERER_UNAVAILABLE, RENDER_FAILED)


def normalized_extension(extension: str) -> str:
    lowered = extension.lower().lstrip(".")
    return EXTENSION_ALIASES.get(lowered, lowered)


def find_route(source: str, target: str) -> Route | None:
    return next((route for route in ROUTES if (route.source, route.target) == (source, target)), None)


def route_lines() -> list[str]:
    width = max(len(f"{route.source} -> {route.target}") for route in ROUTES)
    return [f"  {f'{route.source} -> {route.target}'.ljust(width)}  {route.note}" for route in ROUTES]


GUIDE_INPUTS = ()
GUIDE_SECTIONS = (("Conversions (office convert <input> <output>; the extensions pick the route)", route_lines),)
GUIDE_ISSUES = (("office convert", CONVERT_ISSUE_KINDS),)
