from __future__ import annotations

import io
import re
import zipfile

from lxml import etree


CONTENT_TYPES_NAME = "[Content_Types].xml"
CONTENT_TYPES_NAMESPACE = "{http://schemas.openxmlformats.org/package/2006/content-types}"
RELATIONSHIP_NAMESPACE = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DECLARATION_PATTERN = re.compile(rb"<\?xml[^>]*\?>\s*")


def preserve_unchanged_parts(original_package: bytes, rewritten_package: bytes) -> bytes:
    original = zipfile.ZipFile(io.BytesIO(original_package))
    rewritten = zipfile.ZipFile(io.BytesIO(rewritten_package))
    rewritten_names = set(rewritten.namelist())
    original_names = [info.filename for info in original.infolist() if info.filename in rewritten_names]
    added_names = [name for name in rewritten.namelist() if name not in set(original_names)]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for name in original_names:
            kept, written = original.read(name), rewritten.read(name)
            target.writestr(original.getinfo(name), kept if equivalent_parts(name, kept, written) else with_declaration_of(kept, written))
        for name in added_names:
            target.writestr(rewritten.getinfo(name), rewritten.read(name))
    return output.getvalue()


def with_declaration_of(original: bytes, rewritten: bytes) -> bytes:
    original_declaration, rewritten_declaration = DECLARATION_PATTERN.match(original), DECLARATION_PATTERN.match(rewritten)
    if original_declaration is None or rewritten_declaration is None:
        return rewritten
    return original_declaration.group(0) + rewritten[rewritten_declaration.end():]


def equivalent_parts(name: str, original: bytes, rewritten: bytes) -> bool:
    if original == rewritten:
        return True
    if name == CONTENT_TYPES_NAME:
        return content_type_entries(original) == content_type_entries(rewritten)
    if name.endswith(".rels"):
        return relationship_entries(original) == relationship_entries(rewritten)
    if name.endswith(".xml"):
        return canonical(original) == canonical(rewritten)
    return False


def parsed(data: bytes):
    return etree.fromstring(data, etree.XMLParser(resolve_entities=False))


def canonical(data: bytes) -> bytes:
    return etree.tostring(parsed(data), method="c14n")


def content_type_entries(data: bytes) -> set:
    entries = set()
    for element in parsed(data):
        if element.tag == f"{CONTENT_TYPES_NAMESPACE}Default":
            entries.add(("default", element.get("Extension", "").lower(), element.get("ContentType")))
        elif element.tag == f"{CONTENT_TYPES_NAMESPACE}Override":
            entries.add(("override", element.get("PartName", "").lower(), element.get("ContentType")))
    return entries


def relationship_entries(data: bytes) -> set:
    return {
        (element.get("Id"), element.get("Type"), element.get("Target"), element.get("TargetMode", "Internal"))
        for element in parsed(data)
        if element.tag == f"{RELATIONSHIP_NAMESPACE}Relationship"
    }
