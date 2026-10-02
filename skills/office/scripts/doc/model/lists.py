from __future__ import annotations

from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn


LIST_LEVEL_COUNT = 3
LIST_PARAGRAPH_STYLE = "List Paragraph"
INDENT_TWIPS = 360
BULLET_SYMBOLS = ("•", "◦", "▪")
NUMBER_FORMATS = (("decimal", "%1."), ("lowerLetter", "%2."), ("lowerRoman", "%3."))
BULLET_DEFINITION_NAME = "office-bullets"
NUMBER_DEFINITION_NAME = "office-numbers"


def start_list(document: Document, is_numbered: bool) -> int:
    numbering = document.part.numbering_part.element
    abstract_id = definition_id(numbering, is_numbered)
    number = numbering.add_num(abstract_id)
    if is_numbered:
        for level in range(LIST_LEVEL_COUNT):
            number.add_lvlOverride(ilvl=level).add_startOverride(1)
    return number.numId


def add_list_paragraph(document: Document, list_id: int, level: int):
    paragraph = document.add_paragraph(style=LIST_PARAGRAPH_STYLE)
    number_properties = paragraph._p.get_or_add_pPr().get_or_add_numPr()
    number_properties.get_or_add_ilvl().val = min(level, LIST_LEVEL_COUNT - 1)
    number_properties.get_or_add_numId().val = list_id
    return paragraph


def definition_id(numbering, is_numbered: bool) -> int:
    name = NUMBER_DEFINITION_NAME if is_numbered else BULLET_DEFINITION_NAME
    for definition in numbering.findall(qn("w:abstractNum")):
        named = definition.find(qn("w:name"))
        if named is not None and named.get(qn("w:val")) == name:
            return int(definition.get(qn("w:abstractNumId")))
    identifier = 1 + max(int(definition.get(qn("w:abstractNumId"))) for definition in numbering.findall(qn("w:abstractNum")))
    definition = parse_xml(definition_xml(identifier, name, is_numbered))
    numbering.findall(qn("w:abstractNum"))[-1].addnext(definition)
    return identifier


def definition_xml(identifier: int, name: str, is_numbered: bool) -> str:
    levels = "".join(level_xml(level, is_numbered) for level in range(LIST_LEVEL_COUNT))
    return f'<w:abstractNum {nsdecls("w")} w:abstractNumId="{identifier}"><w:multiLevelType w:val="hybridMultilevel"/><w:name w:val="{name}"/>{levels}</w:abstractNum>'


def level_xml(level: int, is_numbered: bool) -> str:
    number_format, text = NUMBER_FORMATS[level] if is_numbered else ("bullet", BULLET_SYMBOLS[level])
    left = INDENT_TWIPS * (level + 2)
    return (
        f'<w:lvl w:ilvl="{level}"><w:start w:val="1"/><w:numFmt w:val="{number_format}"/><w:lvlText w:val="{text}"/>'
        f'<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="{left}" w:hanging="{INDENT_TWIPS}"/></w:pPr></w:lvl>'
    )
