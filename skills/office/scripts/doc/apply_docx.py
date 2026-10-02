#!/usr/bin/env python3
from __future__ import annotations

from doc.docx_tracking import DEFAULT_TRACKING_AUTHOR
from doc.docx_editing import load_editing, save_editing
from doc.docx_operations import DOCX_OPERATIONS
from core.office_arguments import route_arguments
from core.office_operations import run_apply
from core.office_result import Result, run_command


def main() -> Result:
    arguments = route_arguments("apply", "docx", author=DEFAULT_TRACKING_AUTHOR)
    tracking_author = (arguments.author.strip() or DEFAULT_TRACKING_AUTHOR) if arguments.track else None
    return run_apply(arguments, DOCX_OPERATIONS, lambda path: load_editing(path, tracking_author), save_editing)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
