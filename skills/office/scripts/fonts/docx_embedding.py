from __future__ import annotations

from dataclasses import dataclass
import io
import pathlib
import posixpath
import uuid
import zipfile

from lxml import etree

from fonts.registry import FAMILIES, MONOSPACE, SERIF_BODY, BundledFamily, BundledFace, face_facts
from fonts.truetype import HANGUL_CHARSET


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCUMENT_RELATIONSHIPS_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_RELATIONSHIPS_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/content-types"
OFFICE_DOCUMENT_RELATIONSHIP = f"{DOCUMENT_RELATIONSHIPS_NAMESPACE}/officeDocument"
FONT_TABLE_RELATIONSHIP = f"{DOCUMENT_RELATIONSHIPS_NAMESPACE}/fontTable"
SETTINGS_RELATIONSHIP = f"{DOCUMENT_RELATIONSHIPS_NAMESPACE}/settings"
FONT_RELATIONSHIP = f"{DOCUMENT_RELATIONSHIPS_NAMESPACE}/font"
RELATIONSHIP_ID = f"{{{DOCUMENT_RELATIONSHIPS_NAMESPACE}}}id"
FONT_KEY = f"{{{WORD_NAMESPACE}}}fontKey"
OBFUSCATED_FONT_EXTENSION = "odttf"
OBFUSCATED_FONT_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.obfuscatedFont"
OBFUSCATED_BYTE_COUNT = 32
RUN_FONT_ATTRIBUTES = ("ascii", "hAnsi", "eastAsia", "cs")
EMBED_ELEMENTS = {"regular": "embedRegular", "bold": "embedBold", "italic": "embedItalic", "bold italic": "embedBoldItalic"}
FONT_CHILD_ORDER = ("altName", "panose1", "charset", "family", "notTrueType", "pitch", "sig", *EMBED_ELEMENTS.values())
SETTINGS_BEFORE_EMBEDDING = ("writeProtection", "view", "zoom", "removePersonalInformation", "removeDateAndTime", "doNotDisplayPageBoundaries", "displayBackgroundShape", "printPostScriptOverText", "printFractionalCharacterWidth", "printFormsData")
FONT_FAMILY_CLASSES = {SERIF_BODY: "roman", MONOSPACE: "modern"}
DEFAULT_CHARSET = 0
FONT_KEY_NAMESPACE = uuid.UUID("6f1d3a2e-6c1b-4b0a-9a39-2b4c1f0e7d55")
PRINTABLE_ASCII = "".join(chr(code) for code in range(0x20, 0x7F))
KS_X_1001_HANGUL = "".join(bytes((lead, trail)).decode("euc-kr") for lead in range(0xB0, 0xC9) for trail in range(0xA1, 0xFF))
EDITING_CHARACTERS = frozenset(PRINTABLE_ASCII + KS_X_1001_HANGUL)


@dataclass(frozen=True)
class NamedFace:
    name: str
    element: str
    family: BundledFamily
    face: BundledFace

    @property
    def key(self) -> str:
        return "{" + str(uuid.uuid5(FONT_KEY_NAMESPACE, f"{self.family.directory}/{self.face.file_name}")).upper() + "}"


@dataclass
class Package:
    members: list[zipfile.ZipInfo]
    parts: dict[str, bytes]

    def xml(self, name: str):
        return etree.fromstring(self.parts[name])

    def write(self, name: str, data: bytes) -> None:
        if name not in self.parts:
            self.members.append(zipfile.ZipInfo(name))
        self.parts[name] = data

    def write_xml(self, name: str, root) -> None:
        self.write(name, etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True))


def save_document(document, path) -> None:
    document.save(path)
    embed_named_fonts(pathlib.Path(path))


def embed_named_fonts(path: pathlib.Path) -> None:
    package = read_package(path)
    document_name = related_part(package, "", OFFICE_DOCUMENT_RELATIONSHIP)
    font_table_name = related_part(package, document_name, FONT_TABLE_RELATIONSHIP) if document_name else None
    faces = [face for name in named_fonts(package) for face in named_faces(name)]
    if font_table_name is None or not faces:
        return
    original = dict(package.parts)
    characters = document_characters(package)
    font_table = package.xml(font_table_name)
    added = [write_embedded_face(package, font_table_name, font_table, face, embedding_data(face, characters)) for face in faces]
    if any(added):
        package.write_xml(font_table_name, font_table)
    add_obfuscated_font_content_type(package)
    require_embedding_setting(package, related_part(package, document_name, SETTINGS_RELATIONSHIP))
    if package.parts != original:
        write_package(path, package)


def read_package(path: pathlib.Path) -> Package:
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        return Package(members, {member.filename: archive.read(member) for member in members})


def write_package(path: pathlib.Path, package: Package) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for member in package.members:
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, package.parts[member.filename])
    path.write_bytes(buffer.getvalue())


def relationships_name(part_name: str) -> str:
    directory, file_name = posixpath.split(part_name)
    return posixpath.join(directory, "_rels", f"{file_name}.rels")


def relationships(package: Package, source_name: str) -> list:
    rels_name = relationships_name(source_name)
    if rels_name not in package.parts:
        return []
    return list(package.xml(rels_name).iter(f"{{{PACKAGE_RELATIONSHIPS_NAMESPACE}}}Relationship"))


def related_part(package: Package, source_name: str, relationship_type: str) -> str | None:
    for relationship in relationships(package, source_name):
        if relationship.get("Type") == relationship_type and relationship.get("TargetMode") != "External":
            return resolved_target(source_name, relationship.get("Target"))
    return None


def resolved_target(source_name: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_name), target))


def word_parts(package: Package) -> list:
    return [package.xml(name) for name, data in package.parts.items() if name.endswith(".xml") and WORD_NAMESPACE.encode() in data]


def named_fonts(package: Package) -> list[str]:
    names: dict[str, None] = {}
    for root in word_parts(package):
        for run_fonts in root.iter(f"{{{WORD_NAMESPACE}}}rFonts"):
            names.update(dict.fromkeys(value for attribute in RUN_FONT_ATTRIBUTES if (value := run_fonts.get(f"{{{WORD_NAMESPACE}}}{attribute}"))))
    return list(names)


def document_characters(package: Package) -> frozenset[str]:
    return frozenset("".join(text.text or "" for root in word_parts(package) for text in root.iter(f"{{{WORD_NAMESPACE}}}t")))


def named_faces(name: str) -> list[NamedFace]:
    chosen: dict[str, NamedFace] = {}
    for family in FAMILIES:
        for face in family.faces:
            facts = face_facts(family, face)
            element = EMBED_ELEMENTS.get(facts.style.casefold())
            if element and facts.can_embed_in_office and name.casefold() in {candidate.casefold() for candidate in facts.family_names}:
                chosen.setdefault(element, NamedFace(name, element, family, face))
    return list(chosen.values())


def embedding_data(face: NamedFace, characters: frozenset[str]) -> bytes:
    return subset_data(face.family.path(face.face), "".join(sorted(EDITING_CHARACTERS | characters)))


def subset_data(source: pathlib.Path, text: str) -> bytes:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    options = subset.Options()
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.layout_features = ["*"]
    options.notdef_outline = True
    options.hinting = True
    options.drop_tables += ["FFTM"]
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text)
    output = io.BytesIO()
    with TTFont(str(source), recalcTimestamp=False) as font:
        subsetter.subset(font)
        font.save(output)
    return output.getvalue()


def write_embedded_face(package: Package, font_table_name: str, font_table, face: NamedFace, data: bytes) -> bool:
    entry = font_entry(font_table, face.name)
    if entry is None:
        entry = new_font_entry(font_table, face)
    embed = entry.find(f"{{{WORD_NAMESPACE}}}{face.element}")
    is_new = embed is None
    if is_new:
        embed = etree.SubElement(entry, f"{{{WORD_NAMESPACE}}}{face.element}")
        embed.set(RELATIONSHIP_ID, add_font_relationship(package, font_table_name))
        embed.set(FONT_KEY, face.key)
        entry[:] = sorted(entry, key=child_position)
    package.write(font_part_name(package, font_table_name, embed.get(RELATIONSHIP_ID)), obfuscated(data, embed.get(FONT_KEY)))
    return is_new


def child_position(child) -> int:
    name = etree.QName(child).localname
    return FONT_CHILD_ORDER.index(name) if name in FONT_CHILD_ORDER else len(FONT_CHILD_ORDER)


def font_entry(font_table, name: str):
    return next((entry for entry in font_table.iter(f"{{{WORD_NAMESPACE}}}font") if entry.get(f"{{{WORD_NAMESPACE}}}name") == name), None)


def new_font_entry(font_table, face: NamedFace):
    facts = face_facts(face.family, face.face)
    entry = etree.SubElement(font_table, f"{{{WORD_NAMESPACE}}}font")
    entry.set(f"{{{WORD_NAMESPACE}}}name", face.name)
    values = (
        ("panose1", facts.panose),
        ("charset", f"{HANGUL_CHARSET if facts.is_korean else DEFAULT_CHARSET:02X}"),
        ("family", FONT_FAMILY_CLASSES.get(face.family.role, "swiss")),
        ("pitch", "fixed" if facts.is_fixed_pitch else "variable"),
    )
    for name, value in values:
        etree.SubElement(entry, f"{{{WORD_NAMESPACE}}}{name}").set(f"{{{WORD_NAMESPACE}}}val", value)
    return entry


def add_font_relationship(package: Package, font_table_name: str) -> str:
    rels_name = relationships_name(font_table_name)
    existing = relationships(package, font_table_name)
    root = package.xml(rels_name) if rels_name in package.parts else etree.Element(f"{{{PACKAGE_RELATIONSHIPS_NAMESPACE}}}Relationships", nsmap={None: PACKAGE_RELATIONSHIPS_NAMESPACE})
    relationship_id = first_unused({relationship.get("Id") for relationship in existing}, lambda number: f"rIdEmbeddedFont{number}")
    taken_parts = set(package.parts) | {resolved_target(font_table_name, relationship.get("Target")) for relationship in existing}
    part_name = first_unused(taken_parts, lambda number: posixpath.join(posixpath.dirname(font_table_name), "fonts", f"font{number}.{OBFUSCATED_FONT_EXTENSION}"))
    relationship = etree.SubElement(root, f"{{{PACKAGE_RELATIONSHIPS_NAMESPACE}}}Relationship")
    relationship.set("Id", relationship_id)
    relationship.set("Type", FONT_RELATIONSHIP)
    relationship.set("Target", posixpath.relpath(part_name, posixpath.dirname(font_table_name)))
    package.write_xml(rels_name, root)
    return relationship_id


def first_unused(taken: set[str], name_for) -> str:
    number = 1
    while name_for(number) in taken:
        number += 1
    return name_for(number)


def font_part_name(package: Package, font_table_name: str, relationship_id: str) -> str:
    target = next(relationship.get("Target") for relationship in relationships(package, font_table_name) if relationship.get("Id") == relationship_id)
    return resolved_target(font_table_name, target)


def obfuscated(data: bytes, key: str) -> bytes:
    key_bytes = bytes.fromhex(key.strip("{}").replace("-", ""))[::-1]
    head = bytes(byte ^ key_bytes[index % len(key_bytes)] for index, byte in enumerate(data[:OBFUSCATED_BYTE_COUNT]))
    return head + data[OBFUSCATED_BYTE_COUNT:]


def add_obfuscated_font_content_type(package: Package) -> None:
    root = package.xml("[Content_Types].xml")
    defaults = {element.get("Extension", "").casefold() for element in root.iter(f"{{{CONTENT_TYPES_NAMESPACE}}}Default")}
    if OBFUSCATED_FONT_EXTENSION in defaults:
        return
    default = etree.Element(f"{{{CONTENT_TYPES_NAMESPACE}}}Default")
    default.set("Extension", OBFUSCATED_FONT_EXTENSION)
    default.set("ContentType", OBFUSCATED_FONT_CONTENT_TYPE)
    root.insert(0, default)
    package.write_xml("[Content_Types].xml", root)


def require_embedding_setting(package: Package, settings_name: str | None) -> None:
    if settings_name is None or settings_name not in package.parts:
        return
    settings = package.xml(settings_name)
    if settings.find(f"{{{WORD_NAMESPACE}}}embedTrueTypeFonts") is not None:
        return
    position = next((index for index, child in enumerate(settings) if etree.QName(child).localname not in SETTINGS_BEFORE_EMBEDDING), len(settings))
    settings.insert(position, etree.Element(f"{{{WORD_NAMESPACE}}}embedTrueTypeFonts"))
    package.write_xml(settings_name, settings)
