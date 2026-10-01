from __future__ import annotations

from dataclasses import dataclass, field
import functools

from fontTools.ttLib import TTFont

from office_preview import points_to_pixels
from pptx_text_measure import FontFace, font_face, has_east_asian, is_east_asian, is_hangul, split_breakable, text_width_points


DEFAULT_FAMILY = "Malgun Gothic"
KOREAN_FALLBACK_FAMILY = "Korean Fallback"


@dataclass(frozen=True)
class FontRequest:
    latin: str
    east_asia: str
    size: float
    bold: bool = False

    def family_for(self, text: str) -> str:
        return self.east_asia if has_east_asian(text) else self.latin


@dataclass
class FontRegistry:
    used: dict = field(default_factory=dict)

    def face(self, family: str, bold: bool, east_asian: bool) -> FontFace:
        chosen = font_face(family, bold, east_asian)
        registered = KOREAN_FALLBACK_FAMILY if east_asian and chosen.substituted else family
        self.used.setdefault((registered, 700 if bold else 400), chosen)
        return chosen

    def korean_family(self) -> str:
        return KOREAN_FALLBACK_FAMILY if self.face(DEFAULT_FAMILY, False, True).substituted else DEFAULT_FAMILY

    def width(self, request: FontRequest, text: str) -> float:
        return sum(self.script_width(request, piece) for piece in script_runs(text))

    def script_width(self, request: FontRequest, text: str) -> float:
        family = request.family_for(text)
        return points_to_pixels(text_width_points(self.face(family, request.bold, has_east_asian(text)), text, request.size))

    def line_height(self, request: FontRequest, text: str = "가") -> float:
        family = request.family_for(text)
        face = self.face(family, request.bold, has_east_asian(text))
        return points_to_pixels(request.size * line_height_ratio(face.path, face.index))

    def preview_fonts(self) -> list[dict]:
        return [
            {"family": family, "path": face.path, "index": face.index, "weight": weight}
            for (family, weight), face in sorted(self.used.items())
        ]


@functools.lru_cache(maxsize=None)
def line_height_ratio(path: str, index: int) -> float:
    font = TTFont(path, fontNumber=index, lazy=True)
    units = font["head"].unitsPerEm
    metrics = font["OS/2"] if "OS/2" in font else None
    if metrics is not None and metrics.usWinAscent + metrics.usWinDescent > 0:
        return (metrics.usWinAscent + metrics.usWinDescent) / units
    header = font["hhea"]
    return (header.ascent - header.descent + header.lineGap) / units


def script_runs(text: str) -> list[str]:
    runs: list[str] = []
    for character in text:
        if runs and has_east_asian(runs[-1][-1]) == has_east_asian(character):
            runs[-1] += character
        else:
            runs.append(character)
    return runs


def breakable_pieces(text: str) -> list[str]:
    return split_breakable(text)


def is_ideograph(piece: str) -> bool:
    return len(piece) == 1 and is_east_asian(piece) and not is_hangul(piece)


def css_font_family(*families: str | None) -> str:
    names = dict.fromkeys(name for name in (*families, KOREAN_FALLBACK_FAMILY) if name)
    return ", ".join(f'"{name}"' for name in names)
