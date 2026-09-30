from __future__ import annotations

import os
from pathlib import Path

from office_result import BOLD_FONT_UNAVAILABLE, Issue
from skill_runtime import SKILL_CACHE_DIRECTORY_NAME, cache_home_path, find_bold_face


def register_regular_and_bold(pdf, family: str, regular_path) -> list[Issue]:
    pdf.add_font(family, "", str(regular_path))
    bold_face = find_bold_face(regular_path)
    if bold_face is None:
        pdf.add_font(family, "B", str(regular_path))
        return [BOLD_FONT_UNAVAILABLE.issue(f"no bold face found beside {regular_path}; headings render without bold", str(regular_path))]
    pdf.add_font(family, "B", str(font_file_for_face(*bold_face)))
    return []


def font_file_for_face(font_path: Path, face_index: int) -> Path:
    if face_index == 0:
        return font_path
    extracted_path = cache_home_path(os.environ) / SKILL_CACHE_DIRECTORY_NAME / "fonts" / f"{font_path.stem}-face{face_index}.ttf"
    if not extracted_path.exists():
        extract_face(font_path, face_index, extracted_path)
    return extracted_path


def extract_face(font_path: Path, face_index: int, target_path: Path) -> None:
    from fontTools.ttLib import TTFont

    target_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = target_path.with_name(f"{target_path.name}.{os.getpid()}.partial")
    TTFont(str(font_path), fontNumber=face_index).save(str(partial_path))
    partial_path.replace(target_path)
