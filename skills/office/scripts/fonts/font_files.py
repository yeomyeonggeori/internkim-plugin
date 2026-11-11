from __future__ import annotations

import functools
import os
from pathlib import Path

from fonts.registry import FAMILIES, SANS_BODY, default_family


BUNDLED_FAMILY_NAMES = ", ".join(family.name for family in FAMILIES)
FONT_NAME_MEANING = f"bundled family to draw with ({BUNDLED_FAMILY_NAMES}), default {default_family(SANS_BODY).name}; fontPath, when given, wins"
FONT_PATH_MEANING = "TTF or TTC file to embed instead of a bundled family; a Bold file beside it is used for bold"


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


@functools.lru_cache(maxsize=None)
def mapped_code_points(font_path: Path) -> frozenset[int]:
    from fontTools.ttLib import TTFont

    with TTFont(str(font_path), fontNumber=0, lazy=True) as font:
        return frozenset(font.getBestCmap())
