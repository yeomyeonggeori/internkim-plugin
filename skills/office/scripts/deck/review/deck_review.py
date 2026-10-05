from __future__ import annotations

import dataclasses
import json
import pathlib

from core.office_result import Issue, Result
from deck.review.content_warnings import content_warnings
from deck.review.evidence import read_contact_sheets, read_page_pixels
from deck.review.geometry_checks import read_geometry
from deck.review.slide_checks import review_slides
from deck.review.slide_images import rendered_slide_image_paths
from deck.slide_source import split_slide_sources
from deck.slide_structure import read_slide_texts


REVIEW_FILE_NAME = "slide-review.json"


def review_deck(source_path: pathlib.Path, deck_name: str, review_directory_path: pathlib.Path) -> Result:
    image_paths = rendered_slide_image_paths(review_directory_path, deck_name)
    source_text = source_path.read_text(encoding="utf-8")
    slide_sources = split_slide_sources(source_text)
    slide_count = max(len(slide_sources), len(image_paths))
    slide_texts = read_slide_texts(source_text, slide_count)
    slides = review_slides(image_paths, read_page_pixels(review_directory_path), slide_texts, read_geometry(review_directory_path))
    issues = located_issues(slides) + content_warnings(slide_sources, slide_texts)
    report = {"source": source_path.name, "deckName": deck_name, "slideCount": slide_count, "renderedSlideCount": len(image_paths), "contactSheets": read_contact_sheets(review_directory_path), "slides": [with_messages(slide) for slide in slides]}
    review_directory_path.mkdir(parents=True, exist_ok=True)
    (review_directory_path / REVIEW_FILE_NAME).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return Result(summary=f"reviewed {slide_count} slides", output_path=str(review_directory_path / REVIEW_FILE_NAME), issues=tuple(issues), details={"slideCount": slide_count, "renderedSlideCount": len(image_paths)})


def located_issues(slides: list[dict[str, object]]) -> list[Issue]:
    return [warning if warning.location else dataclasses.replace(warning, location=f"slide {slide['index']}") for slide in slides for warning in slide["warnings"]]


def with_messages(slide: dict[str, object]) -> dict[str, object]:
    return slide | {"warnings": [warning.message for warning in slide["warnings"]]}
