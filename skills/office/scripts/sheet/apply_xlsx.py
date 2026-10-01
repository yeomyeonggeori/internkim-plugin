#!/usr/bin/env python3
from __future__ import annotations

from office_operations import apply_parser, run_apply
from office_result import Result, run_command
from sheet_operations import SHEET_OPERATIONS, load_editing, save_editing


def main() -> Result:
    parser = apply_parser("Apply a batch of edits to a workbook: all of them or none. office guide sheet lists the operations.")
    parser.add_argument("--allow-loss", action="store_true", help="save even when content the editor cannot carry, such as form controls, would be dropped")
    arguments = parser.parse_args()
    return run_apply(arguments, SHEET_OPERATIONS, lambda path: load_editing(path, arguments.allow_loss), save_editing)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
