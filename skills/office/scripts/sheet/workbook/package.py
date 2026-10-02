from __future__ import annotations

from dataclasses import dataclass
import os
import posixpath
import tempfile
import zipfile

from lxml import etree


MAIN_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/content-types"
WORKSHEET_RELATIONSHIP = f"{RELATIONSHIP_NAMESPACE}/worksheet"
CONTENT_TYPES_PART = "[Content_Types].xml"
WORKBOOK_PART = "xl/workbook.xml"
WORKBOOK_RELATIONSHIPS_PART = "xl/_rels/workbook.xml.rels"


def main_tag(name: str) -> str:
    return f"{{{MAIN_NAMESPACE}}}{name}"


@dataclass
class Package:
    entries: dict[str, bytes]
    infos: dict[str, zipfile.ZipInfo]

    def xml(self, part: str):
        return etree.fromstring(self.entries[part])

    def set_xml(self, part: str, root) -> None:
        self.entries[part] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

    def add(self, part: str, content: bytes) -> None:
        self.entries[part] = content
        self.infos.setdefault(part, zipfile.ZipInfo(part))


def read_package(path: str) -> Package:
    with zipfile.ZipFile(path) as archive:
        infos = {info.filename: info for info in archive.infolist()}
        return Package({name: archive.read(name) for name in infos}, infos)


def write_package(package: Package, path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    descriptor, temporary_path = tempfile.mkstemp(prefix=".office-", suffix=".xlsx", dir=directory)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary_path, "w", zipfile.ZIP_DEFLATED) as archive:
            ordered = [CONTENT_TYPES_PART] + [name for name in package.entries if name != CONTENT_TYPES_PART]
            for name in ordered:
                info = package.infos.get(name) or zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, package.entries[name])
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def part_name(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def relationships_part(part: str) -> str:
    directory, name = posixpath.split(part)
    return posixpath.join(directory, "_rels", f"{name}.rels")


def relationships(package: Package, part: str) -> list[dict]:
    rels_part = relationships_part(part)
    if rels_part not in package.entries:
        return []
    root = package.xml(rels_part)
    return [
        {"id": element.get("Id"), "type": element.get("Type"), "target": element.get("Target"), "mode": element.get("TargetMode"), "part": part_name(part, element.get("Target")) if element.get("TargetMode") != "External" else None}
        for element in root.iter(f"{{{PACKAGE_RELATIONSHIP_NAMESPACE}}}Relationship")
    ]


def worksheet_parts(package: Package) -> dict[str, str]:
    workbook = package.xml(WORKBOOK_PART)
    targets = {relationship["id"]: relationship["part"] for relationship in relationships(package, WORKBOOK_PART) if relationship["type"] == WORKSHEET_RELATIONSHIP}
    parts = {}
    for sheet in workbook.iter(main_tag("sheet")):
        target = targets.get(sheet.get(f"{{{RELATIONSHIP_NAMESPACE}}}id"))
        if target is not None:
            parts[target] = sheet.get("name")
    return parts


def add_relationship(package: Package, part: str, relationship_type: str, target: str) -> str:
    rels_part = relationships_part(part)
    if rels_part in package.entries:
        root = package.xml(rels_part)
    else:
        root = etree.Element(f"{{{PACKAGE_RELATIONSHIP_NAMESPACE}}}Relationships", nsmap={None: PACKAGE_RELATIONSHIP_NAMESPACE})
    taken = {element.get("Id") for element in root}
    identifier = next(f"rId{number}" for number in range(1, len(taken) + 2) if f"rId{number}" not in taken)
    etree.SubElement(root, f"{{{PACKAGE_RELATIONSHIP_NAMESPACE}}}Relationship", Id=identifier, Type=relationship_type, Target=target)
    package.add(rels_part, etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True))
    return identifier


def add_content_type_override(package: Package, part: str, content_type: str) -> None:
    root = package.xml(CONTENT_TYPES_PART)
    name = "/" + part
    if any(element.get("PartName") == name for element in root.iter(f"{{{CONTENT_TYPES_NAMESPACE}}}Override")):
        return
    etree.SubElement(root, f"{{{CONTENT_TYPES_NAMESPACE}}}Override", PartName=name, ContentType=content_type)
    package.set_xml(CONTENT_TYPES_PART, root)
