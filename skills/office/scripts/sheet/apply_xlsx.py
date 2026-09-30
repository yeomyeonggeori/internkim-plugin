#!/usr/bin/env python3
from __future__ import annotations

from office_operations import apply_parser, run_apply
from office_result import Result, run_command
from sheet_operations import SHEET_OPERATIONS, load_editing, save_editing


def main() -> Result:
    parser = apply_parser("Apply a batch of edits to a workbook: all of them or none. office guide sheet lists the operations.")
    return run_apply(parser.parse_args(), SHEET_OPERATIONS, load_editing, save_editing)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
