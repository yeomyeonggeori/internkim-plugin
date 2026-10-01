from __future__ import annotations

import pathlib


FIT_REVIEW_FILE_PATTERN = "fit-review-XX.md"
FIT_REVIEW_PROMPT = (
    "Open the paired contact sheet and verify every expected visible text item is fully inside the slide frame, "
    "not clipped, hidden, or pushed past the right or bottom edge."
)


def create_fit_reviews(contact_sheets: list[dict[str, object]], slides: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        create_fit_review(sheet_index, contact_sheet, slides)
        for sheet_index, contact_sheet in enumerate(contact_sheets, start=1)
    ]


def create_fit_review(sheet_index: int, contact_sheet: dict[str, object], slides: list[dict[str, object]]) -> dict[str, object]:
    group_slides = [slides[number - 1] for number in contact_sheet["slideNumbers"] if number - 1 < len(slides)]
    return {
        "filename": f"fit-review-{sheet_index:02d}.md",
        "contactSheetFilename": contact_sheet["filename"],
        "slideNumbers": contact_sheet["slideNumbers"],
        "reviewPrompt": FIT_REVIEW_PROMPT,
        "slides": [fit_review_slide(slide) for slide in group_slides],
    }


def fit_review_slide(slide: dict[str, object]) -> dict[str, object]:
    return {
        "index": slide["index"],
        "expectedVisibleText": slide["expectedVisibleText"],
        "textCharacterCount": slide["textCharacterCount"],
        "textLineCount": slide["textLineCount"],
        "textPreview": slide["textPreview"],
        "warnings": slide["warnings"],
        "risks": slide["risks"],
        "structure": slide["structure"],
    }


def fit_review_index(fit_reviews: list[dict[str, object]]) -> dict[str, object]:
    return {
        "reviewPrompt": FIT_REVIEW_PROMPT,
        "filenamePattern": FIT_REVIEW_FILE_PATTERN,
        "groups": fit_reviews,
    }


def attach_fit_review_metadata(contact_sheets: list[dict[str, object]], fit_reviews: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        contact_sheet | {
            "fitReviewFilename": fit_review["filename"],
            "slideTextSummary": fit_review_text_summary(fit_review),
        }
        for contact_sheet, fit_review in zip(contact_sheets, fit_reviews)
    ]


def fit_review_text_summary(fit_review: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "index": slide["index"],
            "textPreview": slide["textPreview"],
            "textCharacterCount": slide["textCharacterCount"],
            "textLineCount": slide["textLineCount"],
        }
        for slide in fit_review["slides"]
    ]


def fit_review_markdown(review: dict[str, object]) -> str:
    group_number = pathlib.Path(str(review["filename"])).stem.removeprefix("fit-review-")
    lines = [
        f"# Fit Review {group_number}",
        "",
        f"- Contact sheet: {review['contactSheetFilename']}",
        f"- Slides: {', '.join(str(number) for number in review['slideNumbers'])}",
        f"- Check: {review['reviewPrompt']}",
        "",
    ]
    for slide in review["slides"]:
        lines.extend(fit_review_slide_lines(slide))
    return "\n".join(lines)


def fit_review_slide_lines(slide: dict[str, object]) -> list[str]:
    warning_text = "; ".join(slide["warnings"]) if slide["warnings"] else "none"
    return [
        f"## Slide {slide['index']}",
        "",
        f"- Text length: {slide['textCharacterCount']} chars, {slide['textLineCount']} lines",
        f"- Deterministic warnings: {warning_text}",
        "",
        "Expected visible text:",
        "",
        "```text",
        str(slide["expectedVisibleText"]) or "(no visible text extracted)",
        "```",
        "",
    ]
