from __future__ import annotations

from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn


def paragraph_style_id(paragraph, document) -> str | None:
    style_properties = paragraph.find(qn("w:pPr"))
    style_element = style_properties.find(qn("w:pStyle")) if style_properties is not None else None
    if style_element is not None:
        return style_element.get(qn("w:val"))
    return document.styles.default(WD_STYLE_TYPE.PARAGRAPH).style_id


def style_chain(style_id: str | None, document) -> list:
    chain = []
    seen = set()
    while style_id and style_id not in seen:
        seen.add(style_id)
        style = document.styles.element.get_by_id(style_id)
        if style is None:
            break
        chain.append(style)
        based_on = style.find(qn("w:basedOn"))
        style_id = based_on.get(qn("w:val")) if based_on is not None else None
    return chain


def run_styles(run, document) -> list:
    run_properties = run.find(qn("w:rPr"))
    character_style = run_properties.find(qn("w:rStyle")) if run_properties is not None else None
    paragraph = next((ancestor for ancestor in run.iterancestors(qn("w:p"))), None)
    character_chain = style_chain(character_style.get(qn("w:val")), document) if character_style is not None else []
    paragraph_chain = style_chain(paragraph_style_id(paragraph, document), document) if paragraph is not None else []
    return character_chain + paragraph_chain
