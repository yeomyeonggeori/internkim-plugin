from __future__ import annotations

from dataclasses import dataclass
import functools

from PIL import ImageFont

from fonts.registry import BOLD_WEIGHT, REGULAR_WEIGHT, resolved_face
from core.text_script import has_east_asian, is_ideograph


MEASURE_SIZE = 200


@dataclass(frozen=True)
class FontFace:
    path: str
    index: int
    family: str
    substituted: bool
    bold: bool = False


@functools.lru_cache(maxsize=None)
def font_face(family: str, bold: bool, east_asian: bool) -> FontFace:
    resolved = resolved_face(family, BOLD_WEIGHT if bold else REGULAR_WEIGHT)
    return FontFace(str(resolved.path), 0, resolved.typeface, resolved.is_substitute, bold)


@functools.lru_cache(maxsize=None)
def loaded_font(path: str, index: int):
    return ImageFont.truetype(path, MEASURE_SIZE, index=index)


def text_width_points(face: FontFace, text: str, size: float) -> float:
    return loaded_font(face.path, face.index).getlength(text) * size / MEASURE_SIZE


def line_height_points(face: FontFace, size: float) -> float:
    ascent, descent = loaded_font(face.path, face.index).getmetrics()
    return (ascent + descent) * size / MEASURE_SIZE


def split_breakable(text: str) -> list[str]:
    pieces, current = [], ""
    for character in text:
        if character.isspace() or is_ideograph(character):
            if current:
                pieces.append(current)
            pieces.append(character)
            current = ""
            continue
        if current and has_east_asian(current) != has_east_asian(character):
            pieces.append(current)
            current = ""
        current += character
    if current:
        pieces.append(current)
    return pieces
