from __future__ import annotations

import dataclasses
import pathlib

from deck.review.content_warnings import (
    apply_emoji_icon_warning,
    apply_language_mismatch_warning,
    apply_missing_speaker_notes_warning,
    apply_unsourced_current_date_warning,
)
from deck.design_tokens import read_design_tokens
from core.office_result import Issue, Result
from deck.review.fit import attach_fit_review_metadata, create_fit_reviews
from deck.review.geometry_checks import read_geometry
from deck.review.evidence import read_contact_sheets, read_page_pixels
from deck.review.report import write_review_outputs
from deck.review.slide_images import rendered_slide_image_paths
from deck.review.slide_checks import review_slides
from deck.review.title_consistency import apply_title_consistency_warning
from deck.slide_source import read_optional_text, split_slide_sources
from deck.slide_structure import read_slide_texts


REVIEW_DETAIL_FIELDS = ("slideCount", "renderedSlideCount")


def review_deck(source_path: pathlib.Path, deck_name: str, review_directory_path: pathlib.Path, required_texts: tuple[str, ...] = ()) -> Result:
    report, issues = build_review_report(source_path, deck_name, review_directory_path, required_texts)
    write_review_outputs(review_directory_path, report)
    return Result(
        summary=f"reviewed {report['slideCount']} slides",
        output_path=str(review_directory_path / "slide-review.json"),
        issues=tuple(issues),
        details={field: report[field] for field in REVIEW_DETAIL_FIELDS},
    )


def build_review_report(source_path: pathlib.Path, deck_name: str, review_directory_path: pathlib.Path, required_texts: tuple[str, ...] = ()) -> tuple[dict[str, object], list[Issue]]:
    image_paths = rendered_slide_image_paths(review_directory_path, deck_name)
    source_text = source_path.read_text(encoding="utf-8")
    design = read_design_tokens(read_optional_text(source_path.parent / "DESIGN.md"))
    slide_count = max(len(split_slide_sources(source_text)), len(image_paths))
    slide_texts = read_slide_texts(source_text, slide_count)
    geometry = read_geometry(review_directory_path)
    slides = review_slides(image_paths, read_page_pixels(review_directory_path), slide_texts, geometry)
    apply_deck_warnings(slides, slide_texts, source_text, required_texts)
    issues = located_review_issues(slides)
    replace_warnings_with_messages(slides)
    contact_sheets = read_contact_sheets(review_directory_path)
    fit_reviews = create_fit_reviews(contact_sheets, slides)
    report = {
        "reviewUnavailable": slide_count == 0,
        "source": source_path.name,
        "deckName": deck_name,
        "slideCount": slide_count,
        "renderedSlideCount": len(image_paths),
        "design": design,
        "contactSheets": attach_fit_review_metadata(contact_sheets, fit_reviews),
        "fitReviews": fit_reviews,
        "slides": slides,
    }
    return report, issues


def located_review_issues(slides: list[dict[str, object]]) -> list[Issue]:
    issues = []
    for slide in slides:
        for warning in slide["warnings"]:
            located = warning if warning.location else dataclasses.replace(warning, location=f"slide {slide['index']}")
            if located not in issues:
                issues.append(located)
    return issues


def replace_warnings_with_messages(slides: list[dict[str, object]]) -> None:
    for slide in slides:
        slide["warnings"] = [warning.message for warning in slide["warnings"]]


def apply_deck_warnings(
    slides: list[dict[str, object]],
    slide_texts: list[dict[str, object]],
    source_text: str,
    required_texts: tuple[str, ...],
) -> None:
    apply_language_mismatch_warning(slides, slide_texts)
    apply_unsourced_current_date_warning(slides, slide_texts, required_texts)
    apply_emoji_icon_warning(slides, slide_texts)
    apply_missing_speaker_notes_warning(slides, source_text)
    apply_title_consistency_warning(slides)
