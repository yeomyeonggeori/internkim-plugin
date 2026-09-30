from __future__ import annotations

from docx.oxml.ns import qn

from docx_defaults import KOREAN_LANGUAGE, set_default_east_asia_language, set_theme_font_language
from docx_styles import run_styles


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
