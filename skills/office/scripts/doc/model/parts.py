from __future__ import annotations

from docx.opc.packuri import PackURI
from docx.opc.part import Part
from lxml import etree


def related_part(document, relationship_type: str) -> Part | None:
    try:
        return document.part.part_related_by(relationship_type)
    except KeyError:
        return None


def create_part(document, relationship_type: str, part_name: str, content_type: str, root) -> Part:
    part = Part(PackURI(part_name), content_type, serialized(root), document.part.package)
    document.part.relate_to(part, relationship_type)
    return part


def read_root(part: Part):
    return etree.fromstring(part.blob)


def write_root(part: Part, root) -> None:
    part._blob = serialized(root)


def serialized(root) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
