from __future__ import annotations

from dataclasses import dataclass

from office_render import LIBREOFFICE_ISSUE_KINDS
from office_result import ERROR, WARNING, IssueKind


@dataclass(frozen=True)
class Route:
    source: str
    target: str
    note: str
    needs_libreoffice: bool = False


ROUTES = (
    Route("md", "docx", "headings, lists, tables, links and local images; Korean fonts set"),
    Route("md", "html", "one self-contained page; local images embedded"),
    Route("md", "pdf", "same as doc export --format pdf"),
    Route("docx", "md", "final text with tracked changes accepted; images saved beside the output; comments, notes, fields and layout dropped"),
    Route("docx", "html", "one self-contained page; same content as docx to md"),
    Route("docx", "pdf", "laid out by LibreOffice", needs_libreoffice=True),
    Route("html", "docx", "headings, paragraphs, lists, tables, bold, italic, links and images"),
    Route("html", "md", "same content as html to docx"),
    Route("html", "pdf", "laid out by LibreOffice", needs_libreoffice=True),
    Route("pdf", "docx", "text PDFs only: paragraphs, headings by font size, lists, ruled tables, images and two-column reading order; page layout is reflowed"),
    Route("pdf", "md", "same content as pdf to docx"),
    Route("xlsx", "csv", "cached values; one file per sheet unless --sheet picks one; UTF-8 with BOM so Excel reads Korean"),
    Route("xlsx", "tsv", "same as xlsx to csv, tab-separated"),
    Route("xlsx", "pdf", "laid out by LibreOffice", needs_libreoffice=True),
    Route("csv", "xlsx", "typed cells, styled header, frozen header row and filter, as sheet create"),
    Route("tsv", "xlsx", "same as csv to xlsx"),
    Route("xls", "xlsx", "converted by LibreOffice", needs_libreoffice=True),
    Route("ods", "xlsx", "converted by LibreOffice", needs_libreoffice=True),
    Route("pptx", "pdf", "laid out by LibreOffice; a deck built from slides.html already has its PDF", needs_libreoffice=True),
    Route("doc", "docx", "converted by LibreOffice", needs_libreoffice=True),
    Route("odt", "docx", "converted by LibreOffice", needs_libreoffice=True),
    Route("rtf", "docx", "converted by LibreOffice", needs_libreoffice=True),
)
EXTENSION_ALIASES = {"markdown": "md", "htm": "html", "xlsm": "xlsx"}

UNSUPPORTED_CONVERSION = IssueKind("UNSUPPORTED_CONVERSION", ERROR, "no route converts the input's format to the output's", "pick an output extension office guide convert lists for this input")
CONVERSION_APPROXIMATED = IssueKind("CONVERSION_APPROXIMATED", WARNING, "the output keeps the content but not everything the source had; the message says what changed", "render the output and compare it with the source before delivering")
PAGE_WITHOUT_TEXT = IssueKind("PAGE_WITHOUT_TEXT", WARNING, "a PDF page has no text layer, so it was kept as a picture whose words cannot be edited", "say which pages are pictures; reading their text needs OCR")
FORMULA_VALUE_MISSING = IssueKind("FORMULA_VALUE_MISSING", WARNING, "a formula cell has no saved value, so its CSV cell is empty", "run sheet apply with recalculate, then convert again")

CONVERT_ISSUE_KINDS = (UNSUPPORTED_CONVERSION, CONVERSION_APPROXIMATED, PAGE_WITHOUT_TEXT, FORMULA_VALUE_MISSING, *LIBREOFFICE_ISSUE_KINDS)


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
