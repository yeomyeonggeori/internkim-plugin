#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from office_result import OfficeArgumentParser, Result, run_command
from deck_definitions import PPTX_NOT_RENDERED, PPTX_RENDER_FAILED
from pptx_layout_audit import audit_presentation, substitutions
from office_render import RenderFailure, soffice_command
from pptx_render import render_presentation
from pptx_slide_selection import select_slides


def main() -> Result:
    arguments = parse_arguments()
    source_path = Path(arguments.presentation_path).expanduser()
    presentation = Presentation(str(source_path))
    slides = list(presentation.slides)
    numbers = select_slides(arguments.slides, len(slides))
    audit = audit_presentation(presentation, [(number, slides[number - 1]) for number in numbers])
    issues = list(audit.issues)
    details = {"checkedSlides": numbers, "fontsMeasuredWith": substitutions(audit.faces)}
    if not arguments.no_render:
        render_issues, render_details = rendering(source_path, numbers, len(slides), arguments.output_directory, audit.faces)
        issues.extend(render_issues)
        details.update(render_details)
    return Result(summary=f"checked {len(numbers)} slides of {source_path}: {len(issues)} issues", output_path=str(source_path), issues=tuple(issues), details=details)


def rendering(source_path: Path, numbers: list[int], slide_count: int, output_directory: str, faces: frozenset) -> tuple[list, dict]:
    command = soffice_command()
    if command is None:
        return [PPTX_NOT_RENDERED.issue("soffice was not found, so the slides were measured and not seen", str(source_path))], {"seen": False}
    directory = Path(output_directory).expanduser() if output_directory else source_path.with_name(f"{source_path.stem}-check")
    try:
        result = render_presentation(command, source_path, directory, numbers, slide_count, faces)
    except RenderFailure as failure:
        return [PPTX_RENDER_FAILED.issue(str(failure), str(source_path))], {"seen": False}
    return [], {"seen": True, "renderedWith": "LibreOffice, with the fonts the measurement used", "slides": result.pages, "contactSheet": result.contact_sheet}


def parse_arguments():
    parser = OfficeArgumentParser(description=(
        "Check an edited .pptx: text measured with the deck's fonts that overflows its box, shapes off the slide, overlapping text and stretched pictures, "
        "each with an operation deck apply accepts. Then render the slides with LibreOffice to PNG files and a contact sheet to look at."
    ))
    parser.add_argument("presentation_path")
    parser.add_argument("--slides", default="", help="slides to check, such as 2,4-6; default every slide")
    parser.add_argument("--output-directory", default="", help="where the PNG files go, default <file name>-check beside the file")
    parser.add_argument("--no-render", action="store_true", help="measure only, without LibreOffice")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
