from __future__ import annotations

import functools
import os
from pathlib import Path

from fonts.registry import BOLD_WEIGHT, FAMILIES, REGULAR_WEIGHT, SANS_BODY, default_family, resolved_face
from office_result import BOLD_FONT_UNAVAILABLE, Issue


BUNDLED_FAMILY_NAMES = ", ".join(family.name for family in FAMILIES)
FONT_NAME_MEANING = f"bundled family to draw with ({BUNDLED_FAMILY_NAMES}), default {default_family(SANS_BODY).name}; with fontPath, the name that file is registered under"
FONT_PATH_MEANING = "TTF or TTC file to embed instead of a bundled family; a Bold file beside it is used for bold"
FALLBACK_PREFIX = "Fallback "


def register_document_font(pdf, font_name: str, font_path: Path | None, text: str, bundled_name: str | None = None) -> list[Issue]:
    regular_path = font_path or resolved_face(bundled_name or font_name, REGULAR_WEIGHT).path
    if font_path is not None:
        issues = register_font_file(pdf, font_name, font_path)
    else:
        pdf.add_font(font_name, "", str(regular_path))
        pdf.add_font(font_name, "B", str(resolved_face(bundled_name or font_name, BOLD_WEIGHT).path))
        issues = []
    register_fallback_fonts(pdf, uncovered_characters(text, regular_path))
    return issues


def register_fallback_fonts(pdf, missing: frozenset[int]) -> None:
    names = []
    for family in FAMILIES:
        covered = missing & covered_characters(family.path(family.face(REGULAR_WEIGHT)))
        if not covered:
            continue
        name = f"{FALLBACK_PREFIX}{family.name}"
        pdf.add_font(name, "", str(family.path(family.face(REGULAR_WEIGHT))))
        pdf.add_font(name, "B", str(family.path(family.face(BOLD_WEIGHT))))
        names.append(name)
        missing -= covered
    if names:
        pdf.set_fallback_fonts(names, exact_match=False)


def uncovered_characters(text: str, font_path: Path) -> frozenset[int]:
    return frozenset(ord(character) for character in text if not character.isspace()) - covered_characters(font_path)


@functools.lru_cache(maxsize=None)
def covered_characters(font_path: Path) -> frozenset[int]:
    from fontTools.ttLib import TTFont

    with TTFont(str(font_path), fontNumber=0, lazy=True) as font:
        return frozenset(font.getBestCmap())


def register_font_file(pdf, family: str, regular_path: Path) -> list[Issue]:
    pdf.add_font(family, "", str(regular_path))
    bold_path = bold_sibling(regular_path)
    if bold_path is None:
        pdf.add_font(family, "B", str(regular_path))
        return [BOLD_FONT_UNAVAILABLE.issue(f"no bold face found beside {regular_path}; headings render without bold", str(regular_path))]
    pdf.add_font(family, "B", str(bold_path))
    return []


def bold_sibling(regular_path: Path) -> Path | None:
    stem = regular_path.stem
    bold_stems = [f"{stem}Bold", f"{stem}-Bold"]
    if "Regular" in stem:
        bold_stems.insert(0, stem.replace("Regular", "Bold"))
    candidates = (regular_path.with_name(bold_stem + regular_path.suffix) for bold_stem in bold_stems)
    return next((path for path in candidates if path.exists()), None)


def extract_face(font_path: Path, face_index: int, target_path: Path) -> None:
    from fontTools.ttLib import TTFont

    target_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = target_path.with_name(f"{target_path.name}.{os.getpid()}.partial")
    TTFont(str(font_path), fontNumber=face_index).save(str(partial_path))
    partial_path.replace(target_path)
