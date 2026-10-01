from __future__ import annotations

from dataclasses import dataclass
import functools
import shutil
import subprocess

from PIL import ImageFont
from pptx.oxml.ns import qn

from pptx_fonts import PAPERLOGY_FONT_PATH, deck_face_paths, deck_faces
from pptx_geometry import EMU_PER_POINT, Box
from pptx_style import DEFAULT_SIZE, PERCENT_SCALE, ParagraphLevel, has_east_asian, is_east_asian, paragraph_chain, run_style


MEASURE_SIZE = 200
DEFAULT_INSETS = {"lIns": 91440, "rIns": 91440, "tIns": 45720, "bIns": 45720}
FALLBACK_REGULAR = PAPERLOGY_FONT_PATH / "Paperlogy-4Regular.ttf"
FALLBACK_BOLD = PAPERLOGY_FONT_PATH / "Paperlogy-7Bold.ttf"
FONT_MATCH_TIMEOUT_SECONDS = 10
METRIC_SUBSTITUTES = {
    "calibri": ("Carlito",),
    "cambria": ("Caladea",),
    "arial": ("Liberation Sans", "Arimo"),
    "helvetica": ("Liberation Sans", "Arimo"),
    "times new roman": ("Liberation Serif", "Tinos"),
    "courier new": ("Liberation Mono", "Cousine"),
}
GENERIC_LATIN_SUBSTITUTES = ("Liberation Sans", "Arimo", "Arial", "DejaVu Sans")


@dataclass(frozen=True)
class FontFace:
    path: str
    index: int
    family: str
    substituted: bool
    bold: bool = False


@dataclass(frozen=True)
class Atom:
    text: str
    width: float
    line_height: float
    is_space: bool
    is_ideograph: bool = False


@dataclass(frozen=True)
class TextFit:
    needed_height: int
    available_height: int
    widest_line: int
    available_width: int
    faces: frozenset

    @property
    def height_overflow(self) -> int:
        return self.needed_height - self.available_height

    @property
    def width_overflow(self) -> int:
        return self.widest_line - self.available_width


@functools.lru_cache(maxsize=None)
def font_face(family: str, bold: bool, east_asian: bool) -> FontFace:
    bundled = bundled_deck_face(family, bold)
    if bundled is not None:
        return bundled
    requested = matched_font(family, bold, east_asian)
    if requested is not None and not requested.substituted:
        return requested
    for substitute in METRIC_SUBSTITUTES.get(family.casefold(), ()) + (() if east_asian else GENERIC_LATIN_SUBSTITUTES):
        candidate = matched_font(substitute, bold, east_asian)
        if candidate is not None and not candidate.substituted:
            return FontFace(candidate.path, candidate.index, candidate.family, True, bold)
    if requested is not None:
        return requested
    return FontFace(str(FALLBACK_BOLD if bold else FALLBACK_REGULAR), 0, "Paperlogy", True, bold)


def bundled_deck_face(family: str, bold: bool) -> FontFace | None:
    paths = deck_face_paths()
    weight = next((weight for weight, face in deck_faces().items() if face.family.casefold() == family.casefold()), None)
    if weight is None:
        return None
    return FontFace(str(paths[weight]), 0, deck_faces()[weight].family, False, bold)


def matched_font(family: str, bold: bool, east_asian: bool) -> FontFace | None:
    command = shutil.which("fc-match")
    if command is None:
        return None
    pattern = f"{family}:weight={'bold' if bold else 'regular'}{':lang=ko' if east_asian else ''}"
    completed = subprocess.run([command, "-f", "%{file}|%{index}|%{family}", pattern], capture_output=True, text=True, timeout=FONT_MATCH_TIMEOUT_SECONDS)
    path, _, rest = completed.stdout.partition("|")
    index, _, families = rest.partition("|")
    if completed.returncode != 0 or not path:
        return None
    names = {name.strip().casefold() for name in families.split(",")}
    return FontFace(path, int(index or 0), families.split(",")[0], family.casefold() not in names, bold)


@functools.lru_cache(maxsize=None)
def loaded_font(path: str, index: int):
    return ImageFont.truetype(path, MEASURE_SIZE, index=index)


def text_width_points(face: FontFace, text: str, size: float) -> float:
    return loaded_font(face.path, face.index).getlength(text) * size / MEASURE_SIZE


def line_height_points(face: FontFace, size: float) -> float:
    ascent, descent = loaded_font(face.path, face.index).getmetrics()
    return (ascent + descent) * size / MEASURE_SIZE


def measure_text(context, shape_element, box: Box, size_factor: float = 1.0) -> TextFit | None:
    body = shape_element.find(qn("p:txBody"))
    if body is None or not "".join(node.text or "" for node in body.iter(qn("a:t"))).strip():
        return None
    body_properties = body.find(qn("a:bodyPr"))
    if body_properties.get("vert", "horz") not in ("horz", ""):
        return None
    insets = {name: int(body_properties.get(name, default)) for name, default in DEFAULT_INSETS.items()}
    font_scale, spacing_reduction = autofit_scale(body_properties)
    font_scale *= size_factor
    available_width = box.w - insets["lIns"] - insets["rIns"]
    wraps = body_properties.get("wrap", "square") != "none"
    faces = set()
    needed, widest = 0.0, 0.0
    for paragraph in body.findall(qn("a:p")):
        height, width = paragraph_extent(context, shape_element, paragraph, available_width / EMU_PER_POINT, wraps, font_scale, spacing_reduction, faces)
        needed += height
        widest = max(widest, width)
    return TextFit(round(needed * EMU_PER_POINT), box.h - insets["tIns"] - insets["bIns"], round(widest * EMU_PER_POINT), available_width, frozenset(faces))


def wraps(element) -> bool:
    return element.find(f"{qn('p:txBody')}/{qn('a:bodyPr')}").get("wrap", "square") != "none"


def grows_with_text(element) -> bool:
    return element.find(f"{qn('p:txBody')}/{qn('a:bodyPr')}/{qn('a:spAutoFit')}") is not None


def grown_box(element, box: Box, fit: TextFit | None) -> Box:
    if fit is None or not grows_with_text(element):
        return box
    width = box.w + max(0, fit.width_overflow) if not wraps(element) else box.w
    return Box(box.x, box.y, width, box.h + max(0, fit.height_overflow))


def largest_text_size(context, shape_element) -> float:
    sizes = [
        run_style(context, shape_element, paragraph, run.find(qn("a:rPr"))).size.value
        for paragraph in shape_element.iter(qn("a:p"))
        for run in paragraph.iter(qn("a:r"))
    ]
    return max(sizes, default=DEFAULT_SIZE)


def autofit_scale(body_properties) -> tuple[float, float]:
    normal = body_properties.find(qn("a:normAutofit"))
    if normal is None:
        return 1.0, 0.0
    return int(normal.get("fontScale", PERCENT_SCALE)) / PERCENT_SCALE, int(normal.get("lnSpcReduction", "0")) / PERCENT_SCALE


def paragraph_extent(context, shape_element, paragraph, available: float, wraps: bool, font_scale: float, spacing_reduction: float, faces: set) -> tuple[float, float]:
    chain = paragraph_chain(context, shape_element, paragraph)
    margin = paragraph_value(chain, "marL", 0) / EMU_PER_POINT
    indent = paragraph_value(chain, "indent", 0) / EMU_PER_POINT
    atoms = paragraph_atoms(context, shape_element, paragraph, font_scale, faces)
    lines = break_lines(atoms, available - margin - indent, available - margin, wraps)
    spacing = line_spacing(chain, spacing_reduction)
    first_size = atoms[0].line_height if atoms else 0.0
    heights = [scaled_line_height(line, spacing) for line in lines]
    widths = [margin + (indent if index == 0 else 0) + line_width(line) for index, line in enumerate(lines)]
    before = paragraph_spacing(chain, "a:spcBef", first_size)
    after = paragraph_spacing(chain, "a:spcAft", first_size)
    return before + sum(heights) + after, max(widths, default=0.0)


def paragraph_value(chain: list[ParagraphLevel], attribute: str, default: int) -> int:
    for level in chain:
        value = level.paragraph_properties.get(attribute)
        if value is not None:
            return int(value)
    return default


def line_spacing(chain: list[ParagraphLevel], spacing_reduction: float) -> tuple[str, float]:
    for level in chain:
        spacing = level.paragraph_properties.find(qn("a:lnSpc"))
        if spacing is None:
            continue
        if spacing.find(qn("a:spcPts")) is not None:
            return "points", int(spacing.find(qn("a:spcPts")).get("val")) / 100
        if spacing.find(qn("a:spcPct")) is not None:
            return "factor", int(spacing.find(qn("a:spcPct")).get("val")) / PERCENT_SCALE - spacing_reduction
    return "factor", 1.0 - spacing_reduction


def scaled_line_height(line: list[Atom], spacing: tuple[str, float]) -> float:
    mode, amount = spacing
    natural = max((atom.line_height for atom in line), default=0.0)
    return amount if mode == "points" else natural * amount


def paragraph_spacing(chain: list[ParagraphLevel], tag: str, size: float) -> float:
    for level in chain:
        spacing = level.paragraph_properties.find(qn(tag))
        if spacing is None:
            continue
        if spacing.find(qn("a:spcPts")) is not None:
            return int(spacing.find(qn("a:spcPts")).get("val")) / 100
        if spacing.find(qn("a:spcPct")) is not None:
            return size * int(spacing.find(qn("a:spcPct")).get("val")) / PERCENT_SCALE
    return 0.0


def paragraph_atoms(context, shape_element, paragraph, font_scale: float, faces: set) -> list[Atom]:
    atoms = []
    for child in paragraph:
        if child.tag == qn("a:br"):
            atoms.append(Atom("\n", 0.0, 0.0, False))
        elif child.tag in (qn("a:r"), qn("a:fld")):
            atoms.extend(run_atoms(context, shape_element, paragraph, child, font_scale, faces))
    if not any(atom.text.strip() for atom in atoms):
        style = run_style(context, shape_element, paragraph, paragraph.find(qn("a:endParaRPr")))
        face = font_face(style.latin_font.value, style.bold.value, False)
        atoms.append(Atom("", 0.0, line_height_points(face, style.size.value * font_scale), False))
    return atoms


def run_atoms(context, shape_element, paragraph, run, font_scale: float, faces: set) -> list[Atom]:
    text = run.findtext(qn("a:t")) or ""
    style = run_style(context, shape_element, paragraph, run.find(qn("a:rPr")))
    size = style.size.value * font_scale
    atoms = []
    for piece in split_breakable(text):
        typeface = style.font_for(piece).value
        face = font_face(typeface, style.bold.value, has_east_asian(piece))
        faces.add((typeface, face))
        width = text_width_points(face, piece, size) + style.character_spacing.value * font_scale * len(piece)
        atoms.append(Atom(piece, width, line_height_points(face, size), piece.isspace(), len(piece) == 1 and is_east_asian(piece) and not is_hangul(piece)))
    return atoms


def split_breakable(text: str) -> list[str]:
    pieces, current = [], ""
    for character in text:
        if character.isspace() or is_east_asian(character) and not is_hangul(character):
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


def is_hangul(character: str) -> bool:
    code = ord(character)
    return 0xAC00 <= code <= 0xD7AF or 0x1100 <= code <= 0x11FF or 0x3130 <= code <= 0x318F


def break_lines(atoms: list[Atom], first_width: float, other_width: float, wraps: bool) -> list[list[Atom]]:
    lines, line = [], []
    for atom in atoms:
        if atom.text == "\n":
            lines.append(line or [Atom("", 0.0, atom.line_height, False)])
            line = []
            continue
        line.append(atom)
        limit = first_width if not lines else other_width
        if not wraps or atom.is_space or line_width(line) <= limit:
            continue
        cut = last_break(line)
        if cut:
            lines.append(line[:cut])
            line = line[cut:]
    lines.append(line)
    return [entry for entry in lines if entry] or [[]]


def last_break(line: list[Atom]) -> int:
    for index in range(len(line) - 1, 0, -1):
        previous, atom = line[index - 1], line[index]
        if not atom.is_space and (previous.is_space or previous.is_ideograph or atom.is_ideograph):
            return index
    return 0


def line_width(line: list[Atom]) -> float:
    return sum(atom.width for atom in trimmed(line))


def trimmed(line: list[Atom]) -> list[Atom]:
    end = len(line)
    while end and line[end - 1].is_space:
        end -= 1
    return line[:end]
