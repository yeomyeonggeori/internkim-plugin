#!/usr/bin/env python3
from docx_operations import DOCX_OPERATIONS, load_editing, save_editing
from office_operations import apply_parser, run_apply
from office_result import Result, run_command


def main() -> Result:
    parser = apply_parser("Apply a batch of edits to a .docx: all of them or none. office guide doc lists the operations.")
    return run_apply(parser.parse_args(), DOCX_OPERATIONS, load_editing, save_editing)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
