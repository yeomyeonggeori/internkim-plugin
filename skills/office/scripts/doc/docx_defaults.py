from __future__ import annotations

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.shared import Inches, Mm


KOREAN_LANGUAGE = "ko-KR"
DEFAULT_MARGIN_INCHES = 1.0
A4_WIDTH = Mm(210)
A4_HEIGHT = Mm(297)
HEADING_STYLE_NAMES = ["Title"] + [f"Heading {level}" for level in range(1, 10)]
THEME_FONT_ATTRIBUTES = ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme")


def apply_korean_defaults(document: Document, font_name: str) -> None:
    set_default_east_asia_language(document)
    set_theme_font_language(document)
    for style_name in ["Normal"] + HEADING_STYLE_NAMES:
        if style_name in document.styles:
            name_fonts(document.styles[style_name].element.get_or_add_rPr(), font_name)


def set_default_east_asia_language(document: Document) -> None:
    language = document.styles.element.find(f"{qn('w:docDefaults')}/{qn('w:rPrDefault')}/{qn('w:rPr')}/{qn('w:lang')}")
    language.set(qn("w:eastAsia"), KOREAN_LANGUAGE)


def set_theme_font_language(document: Document) -> None:
    document.settings.element.find(qn("w:themeFontLang")).set(qn("w:eastAsia"), KOREAN_LANGUAGE)


def name_fonts(run_properties, font_name: str) -> None:
    run_fonts = run_properties.get_or_add_rFonts()
    for attribute in THEME_FONT_ATTRIBUTES:
        run_fonts.attrib.pop(qn(f"w:{attribute}"), None)
    run_fonts.set(qn("w:ascii"), font_name)
    run_fonts.set(qn("w:hAnsi"), font_name)
    run_fonts.set(qn("w:eastAsia"), font_name)


def set_page(section, margin_inches: float | None = None, is_landscape: bool = False) -> None:
    section.page_width, section.page_height = (A4_HEIGHT, A4_WIDTH) if is_landscape else (A4_WIDTH, A4_HEIGHT)
    section.orientation = WD_ORIENT.LANDSCAPE if is_landscape else WD_ORIENT.PORTRAIT
    margin = Inches(DEFAULT_MARGIN_INCHES if margin_inches is None else margin_inches)
    section.top_margin = margin
    section.right_margin = margin
    section.bottom_margin = margin
    section.left_margin = margin


def usable_width_inches(section) -> float:
    return (section.page_width - section.left_margin - section.right_margin) / Inches(1)
