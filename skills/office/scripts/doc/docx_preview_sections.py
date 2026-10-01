from __future__ import annotations

from dataclasses import dataclass, field

from docx.oxml.ns import qn

from office_preview import PageGeometry, Preview
from units import twips_to_pixels


A4_TWIPS = (11906, 16838)
DEFAULT_MARGIN_TWIPS = 1440
DEFAULT_EDGE_DISTANCE_TWIPS = 720


@dataclass
class Section:
    elements: list = field(default_factory=list)
    properties: object = None
    continues_page: bool = False


def document_sections(body) -> list[Section]:
    sections, current = [], Section()
    for element in body:
        if element.tag == qn("w:sectPr"):
            current.properties = element
            continue
        current.elements.append(element)
        properties = element.find(f"{qn('w:pPr')}/{qn('w:sectPr')}") if element.tag == qn("w:p") else None
        if properties is not None:
            current.properties = properties
            sections.append(current)
            current = Section()
    if current.elements or current.properties is not None:
        sections.append(current)
    for previous, following in zip(sections, sections[1:]):
        following.continues_page = section_type(following.properties) == "continuous"
    return sections


def section_type(properties) -> str:
    element = properties.find(qn("w:type")) if properties is not None else None
    return element.get(qn("w:val"), "nextPage") if element is not None else "nextPage"


def page_number_start(properties) -> int | None:
    numbering = properties.find(qn("w:pgNumType")) if properties is not None else None
    start = numbering.get(qn("w:start"), "") if numbering is not None else ""
    return int(start) if start.isdigit() else None


def twips(element, name: str, default: float) -> float:
    if element is None or element.get(qn(name)) is None:
        return default
    return abs(float(element.get(qn(name))))


def section_geometry(properties, preview: Preview) -> PageGeometry:
    size = properties.find(qn("w:pgSz")) if properties is not None else None
    margins = properties.find(qn("w:pgMar")) if properties is not None else None
    columns = properties.find(qn("w:cols")) if properties is not None else None
    if columns is not None and int(columns.get(qn("w:num"), "1")) > 1:
        preview.approximate("multi-column sections shown in one column")
    width, height = twips(size, "w:w", A4_TWIPS[0]), twips(size, "w:h", A4_TWIPS[1])
    return PageGeometry(
        width=twips_to_pixels(width),
        height=twips_to_pixels(height),
        margin_top=twips_to_pixels(twips(margins, "w:top", DEFAULT_MARGIN_TWIPS)),
        margin_right=twips_to_pixels(twips(margins, "w:right", DEFAULT_MARGIN_TWIPS)),
        margin_bottom=twips_to_pixels(twips(margins, "w:bottom", DEFAULT_MARGIN_TWIPS)),
        margin_left=twips_to_pixels(twips(margins, "w:left", DEFAULT_MARGIN_TWIPS) + twips(margins, "w:gutter", 0)),
        header_distance=twips_to_pixels(twips(margins, "w:header", DEFAULT_EDGE_DISTANCE_TWIPS)),
        footer_distance=twips_to_pixels(twips(margins, "w:footer", DEFAULT_EDGE_DISTANCE_TWIPS)),
    )
