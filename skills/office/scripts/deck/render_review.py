#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import pathlib
import sys
import typing

from contact_sheet import write_contact_sheets
from content_warnings import (
    apply_emoji_icon_warning,
    apply_language_mismatch_warning,
    apply_missing_required_text_warning,
    apply_missing_speaker_notes_warning,
    apply_unsourced_current_date_warning,
)
from design_tokens import read_design_tokens
from design_warnings import annotate_design_revision_need, apply_deck_design_warnings, calculate_visual_quality_score, unique_design_warnings
from office_result import INVALID_ARGUMENTS, Issue, OfficeFailure, Result, run_command
from fit_review import DESIGN_REVIEW_PROMPT, attach_fit_review_metadata, create_fit_reviews
from geometry_checks import apply_geometry_not_measured_warning, read_geometry
from footer_warnings import apply_footer_baseline_warning, apply_unpinned_footer_warning
from review_report import write_review_outputs
from slide_images import rendered_slide_image_paths
from slide_render_checks import review_slides
from slide_source import read_optional_text, split_slide_sources
from slide_structure import read_slide_texts
from source_context import inspect_source_context


VISUAL_QUALITY_SCORE_MINIMUM = 82
REVIEW_DETAIL_FIELDS = (
    "passed",
    "qualityGatePassed",
    "staticGatePassed",
    "visualQualityScore",
    "visualQualityScoreMinimum",
    "visualEvidenceReliable",
    "needsDesignRevision",
    "renderSource",
    "slideCount",
    "renderedSlideCount",
    "geometryMeasured",
)


def main() -> Result:
    arguments = parse_arguments(sys.argv)
    if not arguments:
        raise OfficeFailure(INVALID_ARGUMENTS.issue("usage: render_review.py <source> <deck-name> <review-dir>"))
    report, issues = build_review_report(arguments["sourcePath"], arguments["deckName"], arguments["reviewDirectoryPath"])
    write_review_outputs(arguments["reviewDirectoryPath"], report)
    return Result(
        summary=review_summary(report),
        output_path=str(arguments["reviewDirectoryPath"] / "slide-review.json"),
        issues=tuple(issues),
        details={field: report[field] for field in REVIEW_DETAIL_FIELDS},
    )


def parse_arguments(raw_arguments: list[str]) -> typing.Optional[dict[str, object]]:
    if len(raw_arguments) != 4:
        return None
    return {
        "sourcePath": pathlib.Path(raw_arguments[1]),
        "deckName": raw_arguments[2],
        "reviewDirectoryPath": pathlib.Path(raw_arguments[3]),
    }


def build_review_report(source_path: pathlib.Path, deck_name: str, review_directory_path: pathlib.Path) -> tuple[dict[str, object], list[Issue]]:
    image_paths = rendered_slide_image_paths(review_directory_path, deck_name)
    render_source = read_render_source(review_directory_path, image_paths)
    source_text = source_path.read_text(encoding="utf-8")
    design_document_text = read_optional_text(source_path.parent / "DESIGN.md")
    required_text_ledger = read_optional_text(source_path.parent / "required-visible-text.txt")
    design = read_design_tokens(design_document_text)
    slide_count = max(len(split_slide_sources(source_text)), len(image_paths))
    source_context = inspect_source_context(source_text, design_document_text, slide_count)
    slide_texts = read_slide_texts(source_text, slide_count)
    geometry = read_geometry(review_directory_path)
    slides = review_slides(image_paths, design, slide_texts, geometry)
    apply_deck_warnings(slides, slide_texts, source_text, source_context, render_source, required_text_ledger, geometry)
    design_warnings = unique_design_warnings(slides)
    issues = located_review_issues(slides)
    replace_warnings_with_messages(slides)
    contact_sheets = write_contact_sheets(review_directory_path, image_paths)
    fit_reviews = create_fit_reviews(contact_sheets, slides)
    report = quality_gate_fields(slides, design_warnings, render_source) | {
        "reviewUnavailable": slide_count == 0,
        "renderSource": render_source,
        "designWarnings": [warning.message for warning in design_warnings],
        "sourceContext": source_context,
        "source": source_path.name,
        "deckName": deck_name,
        "slideCount": slide_count,
        "renderedSlideCount": len(image_paths),
        "geometryMeasured": geometry is not None,
        "design": design,
        "designReviewPrompt": DESIGN_REVIEW_PROMPT,
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
    source_context: dict[str, object],
    render_source: str,
    required_text_ledger: str,
    geometry: list[dict[str, object]] | None,
) -> None:
    apply_deck_design_warnings(slides, source_context, render_source)
    apply_geometry_not_measured_warning(slides, geometry)
    apply_language_mismatch_warning(slides, slide_texts)
    apply_unsourced_current_date_warning(slides, slide_texts, required_text_ledger)
    apply_emoji_icon_warning(slides, slide_texts)
    apply_missing_required_text_warning(slides, slide_texts, required_text_ledger)
    apply_footer_baseline_warning(slides)
    apply_unpinned_footer_warning(slides, source_text)
    apply_missing_speaker_notes_warning(slides, source_text)
    annotate_design_revision_need(slides)


def quality_gate_fields(slides: list[dict[str, object]], design_warnings: list[Issue], render_source: str) -> dict[str, object]:
    visual_evidence_reliable = render_source == "browser"
    visual_quality_score = calculate_visual_quality_score(design_warnings)
    static_gate_passed = visual_quality_score >= VISUAL_QUALITY_SCORE_MINIMUM
    quality_gate_passed = (
        all(slide["passed"] for slide in slides)
        and len(slides) > 0
        and visual_evidence_reliable
        and static_gate_passed
    )
    return {
        "passed": quality_gate_passed,
        "qualityGatePassed": quality_gate_passed,
        "staticGatePassed": static_gate_passed,
        "visualQualityScore": visual_quality_score,
        "visualQualityScoreMinimum": VISUAL_QUALITY_SCORE_MINIMUM,
        "visualEvidenceReliable": visual_evidence_reliable,
        "needsDesignRevision": bool(design_warnings) or not static_gate_passed,
    }


def read_render_source(review_directory_path: pathlib.Path, image_paths: list[pathlib.Path]) -> str:
    source_path = review_directory_path / "render-source.txt"
    if source_path.exists():
        value = source_path.read_text(encoding="utf-8").strip()
        if value:
            return value
    if image_paths:
        return "browser"
    return "unavailable"


def review_summary(report: dict[str, object]) -> str:
    gate = "passed" if report["staticGatePassed"] else "failed"
    return (
        f"reviewed {report['slideCount']} slides: static design gate {gate} "
        f"(visual quality score {report['visualQualityScore']}, minimum {report['visualQualityScoreMinimum']}), "
        f"render source {report['renderSource']}"
    )


if __name__ == "__main__":
    raise SystemExit(run_command(main))
