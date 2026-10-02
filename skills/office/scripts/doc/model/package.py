from __future__ import annotations

import io
import posixpath
from urllib.parse import unquote
import zipfile

from docx import Document
from lxml import etree


RELATIONSHIPS_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
RELATIONSHIP_TAG = f"{{{RELATIONSHIPS_NAMESPACE}}}Relationship"


def open_document(path: str):
    with zipfile.ZipFile(path) as archive:
        repaired = without_dangling_relationships(archive)
    if repaired is None:
        return Document(path)
    return Document(io.BytesIO(repaired))


def without_dangling_relationships(archive: zipfile.ZipFile) -> bytes | None:
    members = set(archive.namelist())
    rewritten = {}
    for name in members:
        if not name.endswith(".rels"):
            continue
        root = etree.fromstring(archive.read(name))
        dangling = [relationship for relationship in root.iter(RELATIONSHIP_TAG) if is_dangling(relationship, name, members)]
        for relationship in dangling:
            root.remove(relationship)
        if dangling:
            rewritten[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    if not rewritten:
        return None
    return repackaged(archive, rewritten)


def is_dangling(relationship, relationships_name: str, members: set[str]) -> bool:
    if relationship.get("TargetMode") == "External":
        return False
    target = target_member(relationship.get("Target") or "", relationships_name)
    return target not in members and unquote(target) not in members


def target_member(target: str, relationships_name: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    source_directory = posixpath.dirname(posixpath.dirname(relationships_name))
    return posixpath.normpath(posixpath.join(source_directory, target))


def repackaged(archive: zipfile.ZipFile, rewritten: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
        for member in archive.infolist():
            output.writestr(member, rewritten.get(member.filename, archive.read(member.filename)))
    return buffer.getvalue()
