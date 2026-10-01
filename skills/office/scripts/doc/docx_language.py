from __future__ import annotations

from docx.oxml.ns import qn

from doc_definitions import EAST_ASIA_FONT_MISSING
from docx_blocks import element_text
from docx_defaults import KOREAN_LANGUAGE, set_default_east_asia_language, set_theme_font_language
from docx_styles import run_styles
from office_result import Issue
from text_checks import contains_korean


DEFAULT_EAST_ASIA_FONT = "맑은 고딕"


def east_asia_language_of(properties) -> str | None:
    language = properties.find(qn("w:lang")) if properties is not None else None
    return language.get(qn("w:eastAsia")) if language is not None else None


def effective_east_asia_language(run, document) -> str | None:
    holders = [run.find(qn("w:rPr"))] + [style.find(qn("w:rPr")) for style in run_styles(run, document)] + [document.styles.element.find(f"{qn('w:docDefaults')}/{qn('w:rPrDefault')}/{qn('w:rPr')}")]
    return next((language for language in map(east_asia_language_of, holders) if language), None)


def make_east_asia_language_korean(document) -> int:
    set_default_east_asia_language(document)
    set_theme_font_language(document)
    retagged = [
        language
        for language in (*document.styles.element.iter(qn("w:lang")), *document.element.body.iter(qn("w:lang")))
        if language.get(qn("w:eastAsia")) not in (None, KOREAN_LANGUAGE)
    ]
    for language in retagged:
        language.set(qn("w:eastAsia"), KOREAN_LANGUAGE)
    return len(retagged)


def east_asia_font_issues(document) -> list[Issue]:
    if default_east_asia_font_is_set(document):
        return []
    runs = [run for run in document.element.body.iter(qn("w:r")) if contains_korean(element_text(run))]
    unfonted = [run for run in runs if not run_names_east_asia_font(run, document)]
    if not unfonted:
        return []
    return [EAST_ASIA_FONT_MISSING.issue(f"{len(unfonted)} runs of Korean text have no East Asian font", "document", fix=[{"op": "set_east_asia_font", "font": DEFAULT_EAST_ASIA_FONT}])]


def default_east_asia_font_is_set(document) -> bool:
    fonts = document.styles.element.find(f"{qn('w:docDefaults')}/{qn('w:rPrDefault')}/{qn('w:rPr')}/{qn('w:rFonts')}")
    return names_east_asia_font(fonts)


def names_east_asia_font(run_fonts) -> bool:
    return run_fonts is not None and bool(run_fonts.get(qn("w:eastAsia")) or run_fonts.get(qn("w:eastAsiaTheme")))


def run_names_east_asia_font(run, document) -> bool:
    run_properties = run.find(qn("w:rPr"))
    if run_properties is not None and names_east_asia_font(run_properties.find(qn("w:rFonts"))):
        return True
    return any(style_names_east_asia_font(style) for style in run_styles(run, document))


def style_names_east_asia_font(style) -> bool:
    run_properties = style.find(qn("w:rPr"))
    return run_properties is not None and names_east_asia_font(run_properties.find(qn("w:rFonts")))
