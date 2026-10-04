import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from xml.etree import ElementTree

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
MAIN_NAMESPACE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def run_office(arguments, working_directory):
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=working_directory)
    return json.loads(completed.stdout)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def stored_cells(workbook_path, part_name="xl/worksheets/sheet1.xml"):
    with zipfile.ZipFile(workbook_path) as archive:
        sheet = ElementTree.fromstring(archive.read(part_name))
    cells = {}
    for cell in sheet.iter(f"{MAIN_NAMESPACE}c"):
        formula = cell.find(f"{MAIN_NAMESPACE}f")
        value = cell.find(f"{MAIN_NAMESPACE}v")
        cells[cell.get("r")] = {
            "formula": None if formula is None else formula.text,
            "value": None if value is None or (not value.text and cell.get("t") is None) else value.text or "",
            "type": cell.get("t"),
        }
    return cells


class WorkbookFixture(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)

    def create_workbook(self, sheets, name="book.xlsx"):
        envelope = build_existing_workbook(self.directory, sheets, name)
        self.assertNotEqual(envelope["status"], "error", envelope)
        return envelope

    def apply(self, operations, *extra_arguments, name="book.xlsx"):
        write_json(self.directory / "ops.json", operations)
        return run_office(["apply", name, "ops.json", *extra_arguments], self.directory)

    def cells(self, name="book.xlsx", part_name="xl/worksheets/sheet1.xml"):
        return stored_cells(self.directory / name, part_name)


def run_office_python(code, working_directory):
    subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", textwrap.dedent(code)], check=True, cwd=working_directory)


def build_existing_workbook(directory, sheets, name="book.xlsx"):
    titles = [sheet["title"] for sheet in sheets]
    run_office_python(f"""
        from openpyxl import Workbook
        workbook = Workbook()
        workbook.remove(workbook.active)
        for title in {titles!r}:
            workbook.create_sheet(title)
        workbook.save({name!r})
    """, directory)
    write_json(Path(directory) / "fill.json", [operation for sheet in sheets for operation in filling_operations(sheet)])
    return run_office(["apply", name, "fill.json"], directory)


def filling_operations(sheet):
    rows = ([[sheet["heading"]]] if sheet.get("heading") else []) + list(sheet.get("rows") or [])
    header_row = 2 if sheet.get("heading") else 1
    width = max((len(row) for row in rows), default=0)
    operations = [{"op": "set_range", "sheet": sheet["title"], "cell": "A1", "values": rows}] if rows else []
    freeze = sheet.get("freezePanes", f"A{header_row + 1}")
    if freeze and len(rows) >= header_row:
        operations.append({"op": "freeze_panes", "sheet": sheet["title"], "cell": freeze})
    operations += [{"op": "set_column_width", "sheet": sheet["title"], "column": letter, "width": width_value} for letter, width_value in (sheet.get("columnWidths") or {}).items()]
    if sheet.get("autoFilter", True) and width and len(rows) >= header_row:
        operations.append({"op": "set_auto_filter", "sheet": sheet["title"], "range": f"A{header_row}:{column_letter(width)}{len(rows)}"})
    return operations


def column_letter(index):
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters
