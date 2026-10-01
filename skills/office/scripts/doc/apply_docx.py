#!/usr/bin/env python3
from __future__ import annotations

from docx_tracking import DEFAULT_TRACKING_AUTHOR
from docx_editing import load_editing, save_editing
from docx_operations import DOCX_OPERATIONS
from office_operations import apply_parser, run_apply
from office_result import Result, run_command


def main() -> Result:
    parser = apply_parser("docx")
    parser.add_argument("--track", action="store_true", help="write text, paragraph, row and block edits as tracked changes others can accept or reject")
    parser.add_argument("--author", default=DEFAULT_TRACKING_AUTHOR, help=f"author of tracked changes, default {DEFAULT_TRACKING_AUTHOR!r}")
    arguments = parser.parse_args()
    tracking_author = (arguments.author.strip() or DEFAULT_TRACKING_AUTHOR) if arguments.track else None
    return run_apply(arguments, DOCX_OPERATIONS, lambda path: load_editing(path, tracking_author), save_editing)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
