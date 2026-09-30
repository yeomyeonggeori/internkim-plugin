from __future__ import annotations

import json
import pathlib

from fit_review import FIT_REVIEW_PROMPT, fit_review_index, fit_review_markdown


DESIGN_REVISION_NOTICE = (
    "These warnings do not fail export, but they should trigger a design pass before delivery "
    "unless the user only asked for mechanical conversion."
)


def write_review_outputs(review_directory_path: pathlib.Path, report: dict[str, object]) -> None:
    review_directory_path.mkdir(parents=True, exist_ok=True)
    for fit_review in report["fitReviews"]:
        (review_directory_path / fit_review["filename"]).write_text(fit_review_markdown(fit_review), encoding="utf-8")
    write_json(review_directory_path / "fit-review.json", fit_review_index(report["fitReviews"]))
    write_json(review_directory_path / "slide-review.json", report)
    (review_directory_path / "slide-review.md").write_text(slide_review_markdown(report), encoding="utf-8")


def write_json(path: pathlib.Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slide_review_markdown(report: dict[str, object]) -> str:
    lines = report_summary_lines(report)
    if report["needsDesignRevision"]:
        lines.extend(design_revision_lines(report["designWarnings"]))
    for slide in report["slides"]:
        lines.extend(slide_summary_lines(slide))
    return "\n".join(lines)


def report_summary_lines(report: dict[str, object]) -> list[str]:
    return [
        "# Slide Render Review",
        "",
        f"- Passed: {report['passed']}",
        f"- Quality gate passed: {report['qualityGatePassed']}",
        f"- Static gate passed: {report['staticGatePassed']}",
        f"- Visual quality score: {report['visualQualityScore']} / 100 (minimum {report['visualQualityScoreMinimum']})",
        f"- Visual evidence reliable: {report['visualEvidenceReliable']}",
        f"- Render source: {report['renderSource']}",
        f"- Needs design revision: {report['needsDesignRevision']}",
        f"- Slide count: {report['slideCount']}",
        f"- Rendered slide count: {report['renderedSlideCount']}",
        f"- Geometry: {geometry_line(report)}",
        f"- Contact sheets: {', '.join(sheet['filename'] for sheet in report['contactSheets'])}",
        f"- Fit reviews: {', '.join(review['filename'] for review in report['fitReviews'])}",
        "",
        "## Fit Review Instructions",
        "",
        FIT_REVIEW_PROMPT,
        "",
        "## Design Review Instructions",
        "",
        str(report["designReviewPrompt"]),
        "",
    ]


def geometry_line(report: dict[str, object]) -> str:
    if report["geometryMeasured"]:
        return "measured in the browser (review/geometry.json)"
    return "not measured, so overflow, overlap and stretched images were not checked"


def design_revision_lines(design_warnings: list[str]) -> list[str]:
    return [
        "## Design Revision Needed",
        "",
        DESIGN_REVISION_NOTICE,
        "",
        *(f"- {warning}" for warning in design_warnings),
        "",
    ]


def slide_summary_lines(slide: dict[str, object]) -> list[str]:
    warning_text = "; ".join(slide["warnings"]) if slide["warnings"] else "none"
    return [
        f"## Slide {slide['index']}: {slide_status(slide)}",
        "",
        *slide_file_lines(slide),
        f"- Text length: {slide['textCharacterCount']} chars, {slide['textLineCount']} lines",
        f"- Warnings: {warning_text}",
        f"- Needs design revision: {slide['needsDesignRevision']}",
        "",
    ]


def slide_status(slide: dict[str, object]) -> str:
    if slide["passed"]:
        return "PASS"
    return "WARN" if slide["hasRenderEvidence"] else "NO-RENDER"


def slide_file_lines(slide: dict[str, object]) -> list[str]:
    if not slide["hasRenderEvidence"]:
        return ["- File: (no render image; static source review only)"]
    return [f"- File: {slide['filename']}", f"- Content density: {slide['contentDensity']:.1%}"]
