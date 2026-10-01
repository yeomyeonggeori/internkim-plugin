from __future__ import annotations

import json
import pathlib
import shutil

from deck.editable_pptx import text_layers_path
from deck.geometry_checks import GEOMETRY_FILE_NAME
from render.renderer import CONTACT_SHEETS_FILE_NAME, PIXELS_FILE_NAME
from deck.slide_images import rendered_slide_image_paths


def clear_stale_render_evidence(review_path: pathlib.Path, deck_name: str) -> None:
    if not review_path.exists():
        return
    stale_paths = [
        *rendered_slide_image_paths(review_path, deck_name),
        *review_path.glob("contact-sheet-*.png"),
        review_path / GEOMETRY_FILE_NAME,
        review_path / PIXELS_FILE_NAME,
        review_path / CONTACT_SHEETS_FILE_NAME,
    ]
    for stale_path in stale_paths:
        if stale_path.exists():
            stale_path.unlink()
    shutil.rmtree(text_layers_path(review_path), ignore_errors=True)


def read_page_pixels(review_path: pathlib.Path) -> list[dict[str, object]]:
    pixels_path = review_path / PIXELS_FILE_NAME
    if not pixels_path.exists():
        return []
    return json.loads(pixels_path.read_text(encoding="utf-8"))["pages"]


def read_contact_sheets(review_path: pathlib.Path) -> list[dict[str, object]]:
    sheets_path = review_path / CONTACT_SHEETS_FILE_NAME
    if not sheets_path.exists():
        return []
    return json.loads(sheets_path.read_text(encoding="utf-8"))
