import json
from pathlib import Path
import subprocess
import sys
import tempfile
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
            "value": None if value is None else value.text,
            "type": cell.get("t"),
        }
    return cells


class WorkbookFixture(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)

    def create_workbook(self, sheets, name="book.xlsx"):
        write_json(self.directory / "spec.json", {"sheets": sheets})
        envelope = run_office(["sheet", "create", name, "--spec", "spec.json"], self.directory)
        self.assertNotEqual(envelope["status"], "error", envelope)
        return envelope

    def apply(self, operations, *extra_arguments, name="book.xlsx"):
        write_json(self.directory / "ops.json", operations)
        return run_office(["sheet", "apply", name, "ops.json", *extra_arguments], self.directory)

    def cells(self, name="book.xlsx", part_name="xl/worksheets/sheet1.xml"):
        return stored_cells(self.directory / name, part_name)
