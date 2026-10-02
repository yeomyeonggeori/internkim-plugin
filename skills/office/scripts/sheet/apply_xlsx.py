#!/usr/bin/env python3
from __future__ import annotations

from core.office_arguments import route_arguments
from core.office_operations import run_apply
from core.office_result import Result, run_command
from sheet.operations.operation_set import SHEET_OPERATIONS, load_editing, save_editing


def main() -> Result:
    arguments = route_arguments("apply", "xlsx")
    return run_apply(arguments, SHEET_OPERATIONS, lambda path: load_editing(path, arguments.allow_loss), save_editing)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
