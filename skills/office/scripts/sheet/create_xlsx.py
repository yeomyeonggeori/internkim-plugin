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
from schemas.blank_paths import blanked, replacement_map
from sheet.declaration_claims import declaration_claims
from sheet.workbook_declaration import DECLARATION_REQUIRED


def create_declared(arguments, written, declaration_path):
    declaration = blanked(written, arguments.blank, replacement_map(arguments.replace or []))
    from sheet.declared_workbook import compiled_ranges, declared_workbook, show_hidden_chart_data, shown_views

    context = load_runtime_context()
    workbook, chart_operations, compiler = declared_workbook(declaration, context.attachments if context else ())
    blanks = compiler.blanks + left_blank(written, arguments.blank)
    output_path = Path(os.path.expanduser(arguments.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    editing = SheetEditing(workbook, None)
    apply_batch(SHEET_OPERATIONS, editing, chart_operations)
    show_hidden_chart_data(workbook)
    issues = save_atomically(lambda temporary_path: save_editing(editing, temporary_path), str(output_path))
    titles = [view["title"] for view in declaration.get("views") or []]
    views = shown_views(str(output_path), compiler, titles)
    write_source(output_path, {
        "declaration": declaration_path,
        "compiled": compiled_ranges(compiler),
        "blanks": blanks,
        "claims": declaration_claims(declaration),
        "tables": [{"name": table.name, "columns": [column.name for column in table.columns], "rowCount": len(table.rows)} for table in compiler.tables],
        "views": views,
        "charts": declaration.get("charts") or [],
    })
    summary = f"created {output_path}" + (f"; {len(blanks)} blank input cells for the person to fill or send: {', '.join(blank['label'] for blank in blanks)}" if blanks else "; no blank cells")
    return Result(summary=summary, output_path=str(output_path), issues=tuple(issues), details={"blanks": blanks, "views": views})


def left_blank(written: dict, paths: list[str]) -> list[dict]:
    places = {claim["path"]: claim["at"] for claim in declaration_claims(written)}
    return [{"field": path, "label": places.get(path, path)} for path in dict.fromkeys(paths)]


def declaration_source(arguments) -> tuple[object, str]:
    path = str(Path(arguments.source).expanduser().resolve())
    source = read_json_file(arguments.source)
    if isinstance(source, dict) and isinstance(source.get("declaration"), str) and "kind" not in source:
        return read_json_file(source["declaration"]), source["declaration"]
    return source, path


def main():
    arguments = route_arguments("create", "xlsx")
    source, declaration_path = declaration_source(arguments)
    if not isinstance(source, dict) or source.get("kind") != "workbook":
        raise OfficeFailure(DECLARATION_REQUIRED.issue(f"{arguments.source} is not a workbook declaration; a new workbook is compiled from one", arguments.source))
    return create_declared(arguments, source, declaration_path)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
