#!/usr/bin/env python3
from pptx import Presentation

from office_result import OfficeArgumentParser, Result, run_command
from pptx_content import frame_text, notes_text, shape_kind


def main() -> Result:
    arguments = parse_arguments()
    presentation = Presentation(arguments.presentation_path)
    slides = [describe_slide(slide, number) for number, slide in enumerate(presentation.slides, start=1)]
    details = {
        "slideCount": len(slides),
        "layouts": [layout.name for layout in presentation.slide_layouts],
        "slides": slides,
    }
    return Result(summary=f"read {len(slides)} slides from {arguments.presentation_path}", output_path=arguments.presentation_path, details=details)


def describe_slide(slide, number: int) -> dict:
    return {
        "slide": number,
        "layout": slide.slide_layout.name,
        "shapes": [describe_shape(shape, index) for index, shape in enumerate(slide.shapes)],
        "notes": notes_text(slide),
    }


def describe_shape(shape, index: int) -> dict:
    kind = shape_kind(shape)
    description = {"index": index, "name": shape.name, "kind": kind}
    if kind == "table":
        description["rows"] = [[frame_text(cell.text_frame) for cell in row.cells] for row in shape.table.rows]
    if shape.has_text_frame:
        description["text"] = frame_text(shape.text_frame)
    return description


def parse_arguments():
    parser = OfficeArgumentParser(description="Read a .pptx as numbered slides with layout name, indexed shapes with their text, and speaker notes. Slide numbers and shape indexes are what deck apply takes.")
    parser.add_argument("presentation_path")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
