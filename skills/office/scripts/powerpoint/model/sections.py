from __future__ import annotations

from lxml import etree
from pptx.oxml.ns import qn


POWERPOINT_2010_NAMESPACE = "http://schemas.microsoft.com/office/powerpoint/2010/main"
SECTION_LIST_TAG = f"{{{POWERPOINT_2010_NAMESPACE}}}sectionLst"
SECTION_TAG = f"{{{POWERPOINT_2010_NAMESPACE}}}section"
SECTION_SLIDES_TAG = f"{{{POWERPOINT_2010_NAMESPACE}}}sldIdLst"
SECTION_SLIDE_TAG = f"{{{POWERPOINT_2010_NAMESPACE}}}sldId"


def remember_section(editing, slide_identifier: str, anchor_identifier: str | None) -> None:
    editing.new_slide_anchors[slide_identifier] = anchor_identifier


def remove_from_custom_shows(presentation_element, relationship_id: str) -> None:
    for reference in [node for node in presentation_element.iter(qn("p:sld")) if node.get(qn("r:id")) == relationship_id]:
        reference.getparent().remove(reference)


def normalize_sections(editing) -> None:
    if not editing.structure_changed:
        return
    presentation_element = editing.presentation.part._element
    section_list = next(presentation_element.iter(SECTION_LIST_TAG), None)
    if section_list is None:
        return
    sections = section_list.findall(SECTION_TAG)
    if not sections:
        return
    owners = {entry.get("id"): section for section in sections for entry in section.iter(SECTION_SLIDE_TAG)}
    for slide_identifier, anchor in editing.new_slide_anchors.items():
        owners[slide_identifier] = owners.get(anchor, sections[0])
    order = [element.get("id") for element in editing.presentation.slides._sldIdLst]
    members = contiguous_members(order, owners, sections)
    for section in sections:
        write_section_slides(section, members[id(section)])


def contiguous_members(order: list[str], owners: dict, sections: list) -> dict[int, list[str]]:
    members = {id(section): [] for section in sections}
    started, current = set(), sections[0]
    for slide_identifier in order:
        owner = owners.get(slide_identifier, current)
        if owner is not current and id(owner) not in started:
            current = owner
        started.add(id(current))
        members[id(current)].append(slide_identifier)
    return members


def write_section_slides(section, slide_identifiers: list[str]) -> None:
    slides = section.find(SECTION_SLIDES_TAG)
    if slides is None:
        slides = etree.SubElement(section, SECTION_SLIDES_TAG)
    for entry in list(slides):
        slides.remove(entry)
    for slide_identifier in slide_identifiers:
        etree.SubElement(slides, SECTION_SLIDE_TAG).set("id", slide_identifier)
