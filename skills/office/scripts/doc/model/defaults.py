from __future__ import annotations

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Twips

from fonts.registry import MONOSPACE, SANS_BODY, default_family
from doc.model.settings import insert_setting
from core.page_sizes import DEFAULT_PAPER


KOREAN_LANGUAGE = "ko-KR"
DOCUMENT_FONT = default_family(SANS_BODY).name
CODE_FONT = default_family(MONOSPACE).name
DEFAULT_MARGIN_INCHES = 1.0
HEADING_STYLE_NAMES = ["Title"] + [f"Heading {level}" for level in range(1, 10)]
THEME_FONT_ATTRIBUTES = ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme")


def apply_korean_defaults(document: Document, font_name: str) -> None:
    set_default_east_asia_language(document)
    set_theme_font_language(document)
    for style_name in ["Normal"] + HEADING_STYLE_NAMES:
        if style_name in document.styles:
            name_fonts(document.styles[style_name].element.get_or_add_rPr(), font_name)


def default_run_properties(document: Document):
    styles = document.styles.element
    defaults = styles.find(qn("w:docDefaults"))
    if defaults is None:
        defaults = OxmlElement("w:docDefaults")
        styles.insert(0, defaults)
    run_default = defaults.find(qn("w:rPrDefault"))
    if run_default is None:
        run_default = OxmlElement("w:rPrDefault")
        defaults.insert(0, run_default)
    run_properties = run_default.find(qn("w:rPr"))
    if run_properties is None:
        run_properties = OxmlElement("w:rPr")
        run_default.append(run_properties)
    return run_properties


def set_default_east_asia_language(document: Document) -> None:
    run_properties = default_run_properties(document)
    language = run_properties.find(qn("w:lang"))
    if language is None:
        language = OxmlElement("w:lang")
        run_properties.append(language)
    language.set(qn("w:eastAsia"), KOREAN_LANGUAGE)


def set_theme_font_language(document: Document) -> None:
    settings = document.settings.element
    language = settings.find(qn("w:themeFontLang"))
    if language is None:
        language = OxmlElement("w:themeFontLang")
        insert_setting(settings, language)
    language.set(qn("w:eastAsia"), KOREAN_LANGUAGE)


def name_fonts(run_properties, font_name: str) -> None:
    run_fonts = run_properties.get_or_add_rFonts()
    for attribute in THEME_FONT_ATTRIBUTES:
        run_fonts.attrib.pop(qn(f"w:{attribute}"), None)
    run_fonts.set(qn("w:ascii"), font_name)
    run_fonts.set(qn("w:hAnsi"), font_name)
    run_fonts.set(qn("w:eastAsia"), font_name)


def set_page(section, margin_inches: float | None = None, is_landscape: bool = False) -> None:
    width, height = (Twips(length) for length in DEFAULT_PAPER.twips)
    section.page_width, section.page_height = (height, width) if is_landscape else (width, height)
    section.orientation = WD_ORIENT.LANDSCAPE if is_landscape else WD_ORIENT.PORTRAIT
    margin = Inches(DEFAULT_MARGIN_INCHES if margin_inches is None else margin_inches)
    section.top_margin = margin
    section.right_margin = margin
    section.bottom_margin = margin
    section.left_margin = margin


def usable_width_inches(section) -> float:
    return (section.page_width - section.left_margin - section.right_margin) / Inches(1)
