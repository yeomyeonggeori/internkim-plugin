from __future__ import annotations

from dataclasses import dataclass
import functools
import html

from fonts.registry import DECK, REGULAR_WEIGHT, SANS_BODY, BundledFamily, BundledFace, bundled_family, default_family, stand_in_family
from fonts.truetype import TrueTypeFace, read_truetype_face


GENERIC_FAMILY_NAMES = {"serif", "sans-serif", "monospace", "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded", "-apple-system", "blinkmacsystemfont", "cursive", "fantasy", "emoji", "math", "fangsong"}
SYNTHETIC_BOLD_WEIGHT = 600
FONT_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"
EMBEDDED_FONT_SLOTS = {"regular": "p:regular", "bold": "p:bold", "italic": "p:italic", "bold italic": "p:boldItalic"}


@dataclass(frozen=True)
class RunFont:
    latin: str
    east_asian: str
    bold: bool
    embedded_face: TrueTypeFace | None


@dataclass(frozen=True)
class EmbeddedFont:
    face: TrueTypeFace
    part_name: str
    relationship_id: str


def run_font(family: str, weight: int) -> RunFont:
    bundled = deck_family(family)
    face = office_face(bundled, bundled.face(weight)) if bundled is not None else None
    if face is None:
        name = bundled.name if bundled is not None else family
        return RunFont(name, name, weight >= SYNTHETIC_BOLD_WEIGHT, None)
    return RunFont(face.family, face.family, embedded_slot(face) == "p:bold", face)


def deck_family(family: str) -> BundledFamily | None:
    if family.strip().casefold() not in GENERIC_FAMILY_NAMES:
        return bundled_family(family)
    substitute = stand_in_family(family)
    return default_family(DECK) if substitute.role == SANS_BODY else substitute


def default_run_font() -> RunFont:
    return run_font(default_family(DECK).name, REGULAR_WEIGHT)


@functools.lru_cache(maxsize=None)
def office_face(family: BundledFamily, face: BundledFace) -> TrueTypeFace | None:
    read = read_truetype_face(family.path(face))
    return read if read.has_truetype_outlines else None


def embedded_slot(face: TrueTypeFace) -> str:
    return EMBEDDED_FONT_SLOTS.get(face.subfamily.casefold(), "p:regular")


def embedded_fonts(faces: list[TrueTypeFace], first_relationship_number: int) -> tuple[EmbeddedFont, ...]:
    embeddable = [face for face in faces if face.allows_embedding]
    return tuple(
        EmbeddedFont(face, f"ppt/fonts/font{index}.fntdata", f"rId{first_relationship_number + index - 1}")
        for index, face in enumerate(embeddable, start=1)
    )


def embedded_font_list_xml(fonts: tuple[EmbeddedFont, ...]) -> str:
    if not fonts:
        return ""
    families: dict[str, list[EmbeddedFont]] = {}
    for font in fonts:
        families.setdefault(font.face.family, []).append(font)
    return f"<p:embeddedFontLst>{''.join(embedded_family_xml(members) for members in families.values())}</p:embeddedFontLst>"


def embedded_family_xml(members: list[EmbeddedFont]) -> str:
    first = members[0].face
    slots = {embedded_slot(font.face): font.relationship_id for font in members}
    slot_xml = "".join(f'<{slot} r:id="{slots[slot]}"/>' for slot in EMBEDDED_FONT_SLOTS.values() if slot in slots)
    return (
        "<p:embeddedFont>"
        f'<p:font typeface="{html.escape(first.family)}" panose="{first.panose.hex().upper()}" pitchFamily="2" charset="{first.signed_charset}"/>'
        f"{slot_xml}</p:embeddedFont>"
    )


def font_relationships_xml(fonts: tuple[EmbeddedFont, ...]) -> str:
    return "".join(
        f'<Relationship Id="{font.relationship_id}" Type="{FONT_RELATIONSHIP_TYPE}" Target="{font.part_name.removeprefix("ppt/")}"/>'
        for font in fonts
    )
