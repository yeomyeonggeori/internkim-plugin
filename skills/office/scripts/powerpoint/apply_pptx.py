#!/usr/bin/env python3
from __future__ import annotations

from core.office_arguments import route_arguments
from core.office_operations import Review, run_apply
from core.office_result import Result, run_command
from powerpoint.layout_audit import audit_presentation, substitutions
from powerpoint.operations.operation_set import PPTX_OPERATIONS, save_editing
from powerpoint.operations.targets import PptxEditing, load_editing


def main() -> Result:
    arguments = route_arguments("apply", "pptx")
    return run_apply(arguments, PPTX_OPERATIONS, load_editing, save_editing, review_layout)


def review_layout(editing: PptxEditing) -> Review:
    audited = edited_slides_by_number(editing)
    audit = audit_presentation(editing.presentation, audited)
    return Review(tuple(audit.issues), {"auditedSlides": [number for number, _ in audited], "fontsMeasuredWith": substitutions(audit.faces)})


def edited_slides_by_number(editing: PptxEditing) -> list[tuple[int, object]]:
    edited = {id(slide._element) for slide in editing.edited_slides}
    return [(number, slide) for number, slide in enumerate(editing.presentation.slides, start=1) if id(slide._element) in edited]


if __name__ == "__main__":
    raise SystemExit(run_command(main))
