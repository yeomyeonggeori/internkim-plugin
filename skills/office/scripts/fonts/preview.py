from __future__ import annotations

from dataclasses import dataclass, field
import functools

from fontTools.ttLib import TTFont

from fonts.registry import SANS_BODY, default_family, resolved_face
from office_preview import points_to_pixels
from pptx_text_measure import FontFace, font_face, has_east_asian, is_east_asian, is_hangul, split_breakable, text_width_points


DEFAULT_FAMILY = default_family(SANS_BODY).name


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
        self.used.setdefault((family, 700 if bold else 400), chosen)
        return chosen

    def korean_family(self) -> str:
        self.face(DEFAULT_FAMILY, False, True)
        return DEFAULT_FAMILY

    def use(self, request: FontRequest, text: str) -> None:
        for piece in script_runs(text):
            self.face(request.family_for(piece), request.bold, has_east_asian(piece))

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
    runs: list[tuple[bool | None, str]] = []
    for character in text:
        script = None if character.isspace() else has_east_asian(character)
        if runs and (script is None or runs[-1][0] in (None, script)):
            runs[-1] = (runs[-1][0] if script is None else script, runs[-1][1] + character)
        else:
            runs.append((script, character))
    return [run for _, run in runs]


def breakable_pieces(text: str) -> list[str]:
    return split_breakable(text)


def is_ideograph(piece: str) -> bool:
    return len(piece) == 1 and is_east_asian(piece) and not is_hangul(piece)


def css_font_family(*families: str | None) -> str:
    names = dict.fromkeys(name for name in families if name)
    return ", ".join(f'"{name}"' for name in names)


def draws_scripts_apart(request: FontRequest) -> bool:
    return resolved_face(request.latin).path != resolved_face(request.east_asia).path


def script_font_family(request: FontRequest, text: str) -> str:
    return css_font_family(request.family_for(text), request.latin, request.east_asia)
