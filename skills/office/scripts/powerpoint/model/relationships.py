from __future__ import annotations

import re

from pptx.opc.constants import RELATIONSHIP_TYPE
from pptx.opc.package import XmlPart


RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SHARED_RELATIONSHIP_TYPES = {
    RELATIONSHIP_TYPE.IMAGE,
    RELATIONSHIP_TYPE.MEDIA,
    RELATIONSHIP_TYPE.VIDEO,
    RELATIONSHIP_TYPE.AUDIO,
    RELATIONSHIP_TYPE.SLIDE_LAYOUT,
    RELATIONSHIP_TYPE.SLIDE_MASTER,
    RELATIONSHIP_TYPE.SLIDE,
    RELATIONSHIP_TYPE.NOTES_MASTER,
    RELATIONSHIP_TYPE.HANDOUT_MASTER,
    RELATIONSHIP_TYPE.THEME,
    "http://schemas.microsoft.com/office/2007/relationships/media",
    "http://schemas.microsoft.com/office/2007/relationships/hdphoto",
}
NOT_COPIED_RELATIONSHIP_TYPES = {
    RELATIONSHIP_TYPE.NOTES_SLIDE,
    RELATIONSHIP_TYPE.COMMENTS,
    "http://schemas.microsoft.com/office/2018/10/relationships/comments",
}
PART_NUMBER_PATTERN = re.compile(r"\d+(?=\.[^./]+$)")


def relationship_ids(element) -> list[str]:
    identifiers = []
    for node in element.iter():
        identifiers.extend(value for name, value in node.attrib.items() if name.startswith("{" + RELATIONSHIP_NAMESPACE + "}"))
    return identifiers


def drop_unreferenced(part, relationship_id: str) -> None:
    if relationship_id in relationship_ids(part._element):
        return
    if relationship_id in part.rels:
        part.rels.pop(relationship_id)


def rewrite_relationship_ids(element, mapping: dict[str, str]) -> None:
    for node in element.iter():
        for name, value in node.attrib.items():
            if name.startswith("{" + RELATIONSHIP_NAMESPACE + "}") and value in mapping:
                node.set(name, mapping[value])


def carry_relationships(source_part, target_part, element, skipped_types=frozenset()) -> None:
    mapping = {}
    for relationship_id in dict.fromkeys(relationship_ids(element)):
        if relationship_id not in source_part.rels:
            continue
        relationship = source_part.rels[relationship_id]
        if relationship.reltype in skipped_types:
            continue
        mapping[relationship_id] = carried_relationship(target_part, relationship)
    rewrite_relationship_ids(element, mapping)


def carried_relationship(target_part, relationship) -> str:
    if relationship.is_external:
        return target_part.relate_to(relationship.target_ref, relationship.reltype, is_external=True)
    if relationship.reltype in SHARED_RELATIONSHIP_TYPES:
        return target_part.relate_to(relationship.target_part, relationship.reltype)
    return target_part.relate_to(cloned_part(relationship.target_part), relationship.reltype)


def cloned_part(part):
    package = part.package
    partname = package.next_partname(partname_template(part.partname))
    clone = type(part).load(partname, part.content_type, package, part.blob)
    mapping = {relationship_id: carried_relationship(clone, relationship) for relationship_id, relationship in list(part.rels.items())}
    if isinstance(clone, XmlPart):
        rewrite_relationship_ids(clone._element, mapping)
    return clone


def partname_template(partname: str) -> str:
    template = partname.replace("%", "%%")
    if PART_NUMBER_PATTERN.search(template):
        return PART_NUMBER_PATTERN.sub("%d", template, count=1)
    stem, dot, extension = template.rpartition(".")
    return f"{stem}%d{dot}{extension}"
