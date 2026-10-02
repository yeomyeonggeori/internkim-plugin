from __future__ import annotations

from core.office_commands import CONVERSIONS, EVERY_KIND
from core.office_result import ERROR, WARNING, IssueKind
from deck.deck_definitions import NO_SLIDE_SECTIONS
from pdf.pdf_definitions import OCR_FAILED, PAGE_READ_BY_OCR, PAGE_WITHOUT_TEXT
from render.renderer import RENDER_FAILED, RENDERER_UNAVAILABLE
from sheet.sheet_definitions import SHEET_PRINTS_WIDE


UNSUPPORTED_CONVERSION = IssueKind("UNSUPPORTED_CONVERSION", ERROR, "no route converts the input's format to the output's", "pick an output extension office guide convert lists for this input")
CONVERSION_APPROXIMATED = IssueKind("CONVERSION_APPROXIMATED", WARNING, "the output keeps the content but not everything the source had; the message says what changed", "render the output and compare it with the source before delivering")
TABLE_NOT_FOUND = IssueKind("TABLE_NOT_FOUND", ERROR, "the PDF has no table, ruled or in aligned columns, to turn into sheets, so no workbook was written", "convert it to .md to read its text, or render the page and read the table from the image")
FORMULA_VALUE_MISSING = IssueKind("FORMULA_VALUE_MISSING", WARNING, "a formula cell has no saved value, so its CSV cell is empty", "apply the recalculate operation to the workbook, then convert again")

CONVERT_ISSUE_KINDS = (UNSUPPORTED_CONVERSION, CONVERSION_APPROXIMATED, PAGE_WITHOUT_TEXT, PAGE_READ_BY_OCR, OCR_FAILED, TABLE_NOT_FOUND, FORMULA_VALUE_MISSING, SHEET_PRINTS_WIDE, NO_SLIDE_SECTIONS, RENDERER_UNAVAILABLE, RENDER_FAILED)


def route_lines() -> list[str]:
    width = max(len(f"{route.source} -> {route.target}") for route in CONVERSIONS)
    return [f"  {f'{route.source} -> {route.target}'.ljust(width)}  {route.note}" for route in CONVERSIONS]


GUIDE_SECTIONS = (("convert", "Conversions (office convert <input> <output>; the extensions pick the route)", route_lines),)
GUIDE_ISSUES = (("convert", EVERY_KIND, CONVERT_ISSUE_KINDS),)
