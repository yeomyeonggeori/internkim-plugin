from __future__ import annotations

import pathlib

from deck.deck_definitions import SLIDE_BLANK
from deck.review.geometry_checks import geometry_warnings
from core.office_result import Issue


def review_slides(image_paths: list[pathlib.Path], page_pixels: list[dict[str, object]], slide_texts: list[dict[str, object]], geometry: list[dict[str, object]] | None) -> list[dict[str, object]]:
    return [
        review_slide(
            image_paths[index] if index < len(image_paths) else None,
            page_pixels[index] if index < len(page_pixels) else None,
            index + 1,
            slide_text,
            geometry[index] if geometry is not None and index < len(geometry) else None,
        )
        for index, slide_text in enumerate(slide_texts)
    ]


def review_slide(path: pathlib.Path | None, pixels: dict[str, object] | None, index: int, slide_text: dict[str, object], measured: dict[str, object] | None) -> dict[str, object]:
    warnings = slide_warnings(pixels, measured) if path is not None else []
    return {
        "index": index,
        "filename": path.name if path is not None else "",
        "hasRenderEvidence": path is not None,
        "contentDensity": (pixels or {}).get("density", 0.0),
        "expectedVisibleText": slide_text["expectedVisibleText"],
        "textPreview": slide_text["textPreview"],
        "passed": path is not None and pixels is not None and not warnings,
        "geometry": measured,
        "warnings": warnings,
    }


def slide_warnings(pixels: dict[str, object] | None, measured: dict[str, object] | None) -> list[Issue]:
    is_blank = pixels is not None and pixels.get("bounds") is None
    return ([SLIDE_BLANK.issue("slide render appears blank")] if is_blank else []) + geometry_warnings(measured)
