#!/usr/bin/env python3
from __future__ import annotations

from core.office_arguments import route_arguments
from core.office_operations import Review, run_apply
from core.office_result import Result, run_command
from sheet.compiled_cells import compiled_cells_beside
from sheet.operations.operation_set import SHEET_OPERATIONS, load_editing, save_editing


def main() -> Result:
    arguments = route_arguments("apply", "xlsx")
    compiled = compiled_cells_beside(arguments.file)
    if compiled is None:
        return run_apply(arguments, SHEET_OPERATIONS, lambda path: load_editing(path, arguments.allow_loss), save_editing)
    before = {}

    def load(path: str):
        editing = load_editing(path, arguments.allow_loss)
        before.update(compiled.values(editing.workbook))
        return editing

    def review(editing) -> Review:
        compiled.require_unchanged(before, editing.workbook)
        return Review()

    return run_apply(arguments, SHEET_OPERATIONS, load, save_editing, review)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
