from __future__ import annotations

from dataclasses import dataclass
import functools
import html
import pathlib

from resource_inlining import PAPERLOGY_FAMILY, SKILL_ASSET_PATH, VENDORED_PAPERLOGY_FAMILY, VENDORED_PAPERLOGY_FONTS
from truetype_font import TrueTypeFace, read_truetype_face


PAPERLOGY_FONT_PATH = SKILL_ASSET_PATH / "fonts" / "paperlogy"
DECK_FAMILY_NAMES = {PAPERLOGY_FAMILY.casefold(), VENDORED_PAPERLOGY_FAMILY.casefold()}
GENERIC_FAMILY_NAMES = {"serif", "sans-serif", "system-ui", "ui-serif", "ui-sans-serif", "ui-rounded", "-apple-system", "blinkmacsystemfont", "cursive", "fantasy", "emoji", "math", "fangsong"}
MONOSPACE_FAMILY_NAMES = {"monospace", "ui-monospace"}
MONOSPACE_TYPEFACE = "Courier New"
SYNTHETIC_BOLD_WEIGHT = 600
FONT_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"


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


@functools.lru_cache(maxsize=None)
def deck_faces() -> dict[int, TrueTypeFace]:
    return {weight: read_truetype_face(path) for weight, path in deck_face_paths().items()}


def deck_face_paths() -> dict[int, pathlib.Path]:
    return {weight: PAPERLOGY_FONT_PATH / pathlib.Path(file_name).with_suffix(".ttf").name for weight, file_name in VENDORED_PAPERLOGY_FONTS}


def run_font(family: str, weight: int) -> RunFont:
    family_name = family.casefold()
    if family_name in DECK_FAMILY_NAMES or family_name in GENERIC_FAMILY_NAMES:
        face = deck_face(weight)
        return RunFont(face.family, face.family, False, face)
    if family_name in MONOSPACE_FAMILY_NAMES:
        face = deck_face(weight)
        return RunFont(MONOSPACE_TYPEFACE, face.family, weight >= SYNTHETIC_BOLD_WEIGHT, face)
    return RunFont(family, family, weight >= SYNTHETIC_BOLD_WEIGHT, None)


def deck_face(weight: int) -> TrueTypeFace:
    faces = deck_faces()
    return faces[matched_weight(weight, sorted(faces))]


def matched_weight(desired: int, available: list[int]) -> int:
    if desired in available:
        return desired
    lighter = [weight for weight in reversed(available) if weight < desired]
    heavier = [weight for weight in available if weight > desired]
    if 400 <= desired <= 500:
        up_to_medium = [weight for weight in heavier if weight <= 500]
        return (up_to_medium or lighter or heavier)[0]
    if desired < 400:
        return (lighter or heavier)[0]
    return (heavier or lighter)[0]


def embedded_fonts(faces: list[TrueTypeFace], first_relationship_number: int) -> tuple[EmbeddedFont, ...]:
    embeddable = [face for face in faces if face.allows_embedding]
    return tuple(
        EmbeddedFont(face, f"ppt/fonts/font{index}.fntdata", f"rId{first_relationship_number + index - 1}")
        for index, face in enumerate(embeddable, start=1)
    )


def embedded_font_list_xml(fonts: tuple[EmbeddedFont, ...]) -> str:
    if not fonts:
        return ""
    entries = "".join(
        "<p:embeddedFont>"
        f'<p:font typeface="{html.escape(font.face.family)}" panose="{font.face.panose.hex().upper()}" pitchFamily="2" charset="{font.face.signed_charset}"/>'
        f'<p:regular r:id="{font.relationship_id}"/>'
        "</p:embeddedFont>"
        for font in fonts
    )
    return f"<p:embeddedFontLst>{entries}</p:embeddedFontLst>"


def font_relationships_xml(fonts: tuple[EmbeddedFont, ...]) -> str:
    return "".join(
        f'<Relationship Id="{font.relationship_id}" Type="{FONT_RELATIONSHIP_TYPE}" Target="{font.part_name.removeprefix("ppt/")}"/>'
        for font in fonts
    )
