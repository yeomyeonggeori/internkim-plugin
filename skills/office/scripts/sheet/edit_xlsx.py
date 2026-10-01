#!/usr/bin/env python3
from __future__ import annotations

from cell_values import typed_cell_value
from excel_functions import written_value
from office_operations import save_atomically
from office_inputs import office_file, resolve_document_path
from office_result import DOCUMENTS_FOLDER, OfficeArgumentParser, Result, read_json_file, run_command
from office_schema import require_valid
from sheet_definitions import ROWS
from sheet_operations import load_editing, save_editing
from written_cells import require_writable_rows


def main() -> Result:
    arguments = parse_arguments()
    json_rows = load_rows(arguments.rows) if arguments.rows else []
    argument_rows = [parse_row(row_string) for row_string in arguments.row]
    require_writable_rows(argument_rows, "--row")
    require_writable_rows(json_rows, "rows")
    workbook_path = resolve_document_path(arguments.workbook_path, "xlsx")
    editing = load_editing(workbook_path, arguments.allow_loss)
    worksheet = resolve_worksheet(editing.workbook, arguments.sheet)
    for row in argument_rows + json_rows:
        worksheet.append([written_value(value) for value in row])
    issues = save_atomically(lambda temporary_path: save_editing(editing, temporary_path), workbook_path)
    return Result(summary=f"appended rows to {workbook_path}", output_path=workbook_path, issues=tuple(issues))


def load_rows(rows_path: str) -> list[list]:
    rows = read_json_file(rows_path)
    require_valid(ROWS, rows, "rows")
    return rows


def parse_row(row_string: str) -> list:
    return [typed_cell_value(cell.strip()) for cell in row_string.split(",")]


def resolve_worksheet(workbook, sheet_name: str | None):
    if sheet_name is None:
        return workbook.active
    if sheet_name in workbook.sheetnames:
        return workbook[sheet_name]
    return workbook.create_sheet(title=sheet_name)


def parse_arguments():
    parser = OfficeArgumentParser(description="Append rows to an existing XLSX workbook in place.")
    parser.add_argument("workbook_path", nargs="?", type=office_file("xlsx"), help=f"Path to the .xlsx; defaults to the newest .xlsx in {DOCUMENTS_FOLDER}")
    parser.add_argument("--sheet", default=None, metavar="NAME", help="Sheet name (default: active sheet; created if missing)")
    parser.add_argument("--row", action="append", default=[], metavar="CELLS", help="Append one row; comma-separated cell values (repeatable)")
    parser.add_argument("--rows", metavar="JSON_PATH", help="JSON file with an array of row arrays")
    parser.add_argument("--allow-loss", action="store_true", help="save even when content the editor cannot carry, such as form controls, would be dropped")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
