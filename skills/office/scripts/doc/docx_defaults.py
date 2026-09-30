from __future__ import annotations

from docx import Document
from docx.oxml.ns import qn


KOREAN_LANGUAGE = "ko-KR"
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
