#!/usr/bin/env python3
from __future__ import annotations

import os

from office_operations import apply_batch, apply_parser, read_batch, save_atomically
from office_result import Result, run_command
from pptx_layout_audit import audit_presentation, substitutions
from pptx_operations import PPTX_OPERATIONS, save_editing
from pptx_targets import PptxEditing, load_editing


def main() -> Result:
    arguments = apply_parser(
        "Apply a batch of edits to a .pptx: all of them or none. office guide deck lists the operations. "
        "The result reports text that overflows its box, shapes off the slide and overlaps on every slide the batch changed, "
        "each with an operation that fixes it.",
        "pptx",
    ).parse_args()
    operations = read_batch(PPTX_OPERATIONS, arguments.ops)
    editing = load_editing(arguments.path)
    changes = apply_batch(PPTX_OPERATIONS, editing, operations)
    audited = edited_slides_by_number(editing)
    audit = audit_presentation(editing.presentation, audited)
    issues = tuple(audit.issues)
    details = {"dryRun": arguments.dry_run, "changes": changes, "auditedSlides": [number for number, _ in audited], "fontsMeasuredWith": substitutions(audit.faces)}
    if arguments.dry_run:
        return Result(summary=f"dry run: {len(changes)} operations would apply to {arguments.path}", issues=issues, details=details)
    output_path = os.path.expanduser(arguments.output or arguments.path)
    save_atomically(lambda temporary_path: save_editing(editing, temporary_path), output_path)
    return Result(summary=f"applied {len(changes)} operations to {output_path}", output_path=output_path, issues=issues, details=details)


def edited_slides_by_number(editing: PptxEditing) -> list[tuple[int, object]]:
    edited = {id(slide._element) for slide in editing.edited_slides}
    return [(number, slide) for number, slide in enumerate(editing.presentation.slides, start=1) if id(slide._element) in edited]


if __name__ == "__main__":
    raise SystemExit(run_command(main))
