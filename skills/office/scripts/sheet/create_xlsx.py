#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from core.office_arguments import route_arguments
from core.office_operations import apply_batch, save_atomically
from core.office_result import OfficeFailure, Result, read_json_file, run_command
from core.source_snapshot import write_source
from schemas.known_values import load_runtime_context
from sheet.operations.operation_set import SHEET_OPERATIONS, SheetEditing, save_editing
from sheet.workbook_declaration import DECLARATION_REQUIRED


def create_declared(arguments, declaration):
    from sheet.declared_workbook import compiled_ranges, declared_workbook, show_hidden_chart_data, shown_views

    context = load_runtime_context()
    workbook, chart_operations, compiler = declared_workbook(declaration, context.attachments if context else ())
    blanks = compiler.blanks
    output_path = Path(os.path.expanduser(arguments.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    editing = SheetEditing(workbook, None)
    apply_batch(SHEET_OPERATIONS, editing, chart_operations)
    show_hidden_chart_data(workbook)
    issues = save_atomically(lambda temporary_path: save_editing(editing, temporary_path), str(output_path))
    write_source(output_path, {"declaration": str(Path(arguments.source).expanduser().resolve()), "compiled": compiled_ranges(compiler), "blanks": blanks})
    summary = f"created {output_path}" + (f"; {len(blanks)} blank input cells for the person to fill or send: {', '.join(blank['label'] for blank in blanks)}" if blanks else "; no blank cells")
    titles = [view["title"] for view in declaration.get("views") or []]
    views = shown_views(str(output_path), compiler, titles)
    return Result(summary=summary, output_path=str(output_path), issues=tuple(issues), details={"blanks": blanks, "views": views})


def main():
    arguments = route_arguments("create", "xlsx")
    source = read_json_file(arguments.source)
    if not isinstance(source, dict) or source.get("kind") != "workbook":
        raise OfficeFailure(DECLARATION_REQUIRED.issue(f"{arguments.source} is not a workbook declaration; a new workbook is compiled from one", arguments.source))
    return create_declared(arguments, source)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
