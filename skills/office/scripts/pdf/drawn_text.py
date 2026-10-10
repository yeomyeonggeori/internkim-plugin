from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path

import pypdfium2
import pypdfium2.raw as pdfium

from core.office_result import Issue
from pdf.pdf_definitions import TEXT_NOT_DRAWN


MINIMUM_INK_SPREAD = 16
THIN_GLYPH_PIXELS = 3
THIN_GLYPH_PADDING = 2
MAXIMUM_REPORTED_WORDS = 6
PAINTING_RENDER_MODES = frozenset((
    pdfium.FPDF_TEXTRENDERMODE_FILL, pdfium.FPDF_TEXTRENDERMODE_STROKE, pdfium.FPDF_TEXTRENDERMODE_FILL_STROKE,
    pdfium.FPDF_TEXTRENDERMODE_FILL_CLIP, pdfium.FPDF_TEXTRENDERMODE_STROKE_CLIP, pdfium.FPDF_TEXTRENDERMODE_FILL_STROKE_CLIP,
))


@dataclass(frozen=True)
class UndrawnCharacter:
    page: int
    character: str
    word: str


def text_not_drawn_issues(pdf_path: Path) -> list[Issue]:
    undrawn = undrawn_characters(pdf_path)
    pages = sorted({character.page for character in undrawn})
    return [TEXT_NOT_DRAWN.issue(page_message(page, [character for character in undrawn if character.page == page]), f"page {page}") for page in pages]


def page_message(page: int, undrawn: list[UndrawnCharacter]) -> str:
    words = list(dict.fromkeys(f'"{character.word}" draws nothing for "{character.character}"' for character in undrawn))
    return f"page {page}: " + "; ".join(words[:MAXIMUM_REPORTED_WORDS])


def undrawn_characters(pdf_path: Path) -> list[UndrawnCharacter]:
    document = pypdfium2.PdfDocument(str(pdf_path))
    try:
        return [character for index in range(len(document)) for character in page_undrawn_characters(document[index], index + 1)]
    finally:
        document.close()


def page_undrawn_characters(page, number: int) -> list[UndrawnCharacter]:
    image = page.render(scale=1).to_pil().convert("L")
    height = page.get_height()
    text_page = page.get_textpage()
    text = text_page.get_text_range()
    undrawn = []
    for index in range(text_page.count_chars()):
        character = text_page.get_text_range(index, 1)
        if not character.strip() or not is_painted(text_page, index):
            continue
        low, high = image.crop(within_image(pixel_box(text_page.get_charbox(index), height), image.size)).getextrema()
        if high - low < MINIMUM_INK_SPREAD:
            undrawn.append(UndrawnCharacter(number, character, word_around(text, index)))
    return undrawn


def is_painted(text_page, index: int) -> bool:
    text_object = pdfium.FPDFText_GetTextObject(text_page.raw, index)
    if not text_object or pdfium.FPDFTextObj_GetTextRenderMode(text_object) not in PAINTING_RENDER_MODES:
        return False
    red, green, blue, alpha = (ctypes.c_uint() for _ in range(4))
    if not pdfium.FPDFText_GetFillColor(text_page.raw, index, red, green, blue, alpha):
        return True
    return alpha.value > 0


def pixel_box(charbox: tuple[float, float, float, float], page_height: float) -> tuple[int, int, int, int]:
    left, bottom, right, top = charbox
    pixel_left, pixel_top = int(left), int(page_height - top)
    pixel_right, pixel_bottom = max(pixel_left + 1, int(right + 0.999)), max(pixel_top + 1, int(page_height - bottom + 0.999))
    horizontal = THIN_GLYPH_PADDING if pixel_right - pixel_left < THIN_GLYPH_PIXELS else 0
    vertical = THIN_GLYPH_PADDING if pixel_bottom - pixel_top < THIN_GLYPH_PIXELS else 0
    return pixel_left - horizontal, pixel_top - vertical, pixel_right + horizontal, pixel_bottom + vertical


def within_image(box: tuple[int, int, int, int], size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    left, top = min(max(box[0], 0), width - 1), min(max(box[1], 0), height - 1)
    return left, top, min(max(box[2], left + 1), width), min(max(box[3], top + 1), height)


def word_around(text: str, index: int) -> str:
    start = index
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    end = index + 1
    while end < len(text) and not text[end].isspace():
        end += 1
    return text[start:end]
