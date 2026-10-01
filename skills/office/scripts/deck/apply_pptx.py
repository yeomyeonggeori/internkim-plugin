#!/usr/bin/env python3
from __future__ import annotations

from office_operations import apply_parser, run_apply
from office_result import Result, run_command
from pptx_operations import PPTX_OPERATIONS, save_editing
from pptx_targets import load_editing


def main() -> Result:
    parser = apply_parser("Apply a batch of edits to a .pptx: all of them or none. office guide deck apply lists the operations.")
    return run_apply(parser.parse_args(), PPTX_OPERATIONS, load_editing, save_editing)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
