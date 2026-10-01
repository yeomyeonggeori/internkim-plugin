from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from deck.deck_definitions import PPTX_NOT_RENDERED
from render.office_preview import drawn_page_details
from core.office_result import Result
from deck.pptx_layout_audit import audit_presentation, substitutions
from deck.pptx_preview import preview_document
from deck.pptx_slide_selection import select_slides
from render.renderer import RenderFailed, RendererUnavailable, draw_preview


PREVIEW_NAME = "preview.html"
SLIDE_SELECTOR = "section[data-slide]"
BOLD_WEIGHT = 700
REGULAR_WEIGHT = 400


def check_presentation(source_path: Path, slide_selection: str, output_directory: str, preview: bool) -> Result:
    presentation = Presentation(str(source_path))
    slides = list(presentation.slides)
    numbers = select_slides(slide_selection, len(slides))
    audit = audit_presentation(presentation, [(number, slides[number - 1]) for number in numbers])
    issues = list(audit.issues)
    details = {"checkedSlides": numbers, "fontsMeasuredWith": substitutions(audit.faces)}
    if preview:
        directory = Path(output_directory).expanduser() if output_directory else source_path.with_name(f"{source_path.stem}-check")
        preview_details, preview_issues = write_preview(presentation, numbers, directory)
        details.update(preview_details)
        issues.extend(preview_issues)
    return Result(summary=f"checked {len(numbers)} slides of {source_path}: {len(audit.issues)} layout issues", output_path=str(source_path), issues=tuple(issues), details=details)


def write_preview(presentation, numbers: list[int], directory: Path) -> tuple[dict, list]:
    preview = preview_document(presentation, numbers)
    directory.mkdir(parents=True, exist_ok=True)
    preview_path = directory / PREVIEW_NAME
    preview_path.write_text(preview.html, encoding="utf-8")
    fonts = preview_fonts(preview.faces)
    details = {"preview": str(preview_path), "previewFonts": fonts}
    try:
        rendered = draw_preview(preview_path, SLIDE_SELECTOR, fonts)
    except (RendererUnavailable, RenderFailed) as reason:
        return details | {"seen": False}, [PPTX_NOT_RENDERED.issue(f"the preview of {len(numbers)} slides was written as HTML to {preview_path}, and no image of it was drawn: {reason}", str(preview_path))]
    return details | drawn_page_details(rendered), []


def preview_fonts(faces: frozenset) -> list[dict]:
    files = {(face.family, face.path, face.index, BOLD_WEIGHT if face.bold else REGULAR_WEIGHT) for _, face in faces}
    return [{"family": family, "path": path, "index": index, "weight": weight} for family, path, index, weight in sorted(files)]
