import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

OFFICE_SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
SCRIPTS_PATH = OFFICE_SCRIPTS_PATH / "sheet"
SPREADSHEET_NAMESPACE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

PROBE_ROWS = [
    ["region", "qty", "price", "amount", "rate share", "label"],
    ["Seoul", 2, 1.5, "=B2*C2", "=D2/$D$6", '=IF(A2="Q1","yes","no")'],
    ["Busan", 3, 2, "=B3*C3", "=D3/$D$6", "=LOG10(B3)"],
    ["Seoul", 1, 4, "=B4*C4", "=VLOOKUP(A4,$A$2:$C$4,2,0)", ""],
    ["Daegu", 5, 1, "=B5*C5", '=SUMIF($A$2:$A$5,"Seoul",$D$2:$D$5)', ""],
    ["Total", "", "", "=SUM(D2:D5)", "", ""],
]


def run_script(script_name, *arguments):
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_PATH / script_name), *arguments],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(OFFICE_SCRIPTS_PATH)},
    )
    if result.returncode != 0 and "dependencies are unavailable" in result.stderr:
        raise unittest.SkipTest(f"openpyxl is not importable and the skill runtime could not install it: {result.stderr.strip()}")
    if result.returncode != 0:
        raise AssertionError(f"{script_name} failed: {result.stderr}")


def read_cells(workbook_path):
    with zipfile.ZipFile(workbook_path) as archive:
        shared_strings = read_shared_strings(archive)
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    cells = {}
    for cell in sheet.iter(f"{SPREADSHEET_NAMESPACE}c"):
        cells[cell.get("r")] = read_cell(cell, shared_strings)
    return cells


def read_shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(text.text or "" for text in item.iter(f"{SPREADSHEET_NAMESPACE}t")) for item in root]


def read_cell(cell, shared_strings):
    formula = cell.find(f"{SPREADSHEET_NAMESPACE}f")
    if formula is not None:
        return ("formula", "=" + (formula.text or ""))
    if cell.get("t") == "inlineStr":
        return ("text", "".join(text.text or "" for text in cell.iter(f"{SPREADSHEET_NAMESPACE}t")))
    value = cell.find(f"{SPREADSHEET_NAMESPACE}v")
    if value is None:
        return ("empty", "")
    if cell.get("t") == "s":
        return ("text", shared_strings[int(value.text)])
    return ("number", value.text)


class SpreadsheetFormulaTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.directory, ignore_errors=True))

    def build_probe_workbook(self):
        specification_path = self.directory / "spec.json"
        specification_path.write_text(json.dumps({"title": "Probe", "sheets": [{"title": "Data", "rows": PROBE_ROWS}]}))
        workbook_path = self.directory / "probe.xlsx"
        run_script("create_xlsx.py", str(workbook_path), str(specification_path))
        return read_cells(workbook_path)

    def test_every_formula_is_stored_exactly_as_written(self):
        cells = self.build_probe_workbook()
        for row_index, row in enumerate(PROBE_ROWS, start=1):
            for column_index, value in enumerate(row):
                if not (isinstance(value, str) and value.startswith("=")):
                    continue
                coordinate = f"{'ABCDEF'[column_index]}{row_index}"
                self.assertEqual(cells[coordinate], ("formula", value), coordinate)

    def test_no_row_is_inserted_above_the_written_rows(self):
        cells = self.build_probe_workbook()
        self.assertEqual(cells["A1"], ("text", "region"))
        self.assertEqual(cells["A6"], ("text", "Total"))
        self.assertNotIn("A7", cells)

    def test_csv_numbers_are_numeric_and_leading_zeros_stay_text(self):
        csv_path = self.directory / "data.csv"
        with open(csv_path, "w", newline="") as csv_file:
            csv.writer(csv_file).writerows([["code", "amount", "ratio", "note"], ["007", "1500", "2.5", "1,500"]])
        specification_path = self.directory / "spec.json"
        specification_path.write_text(json.dumps({"title": "Csv", "sheets": [{"title": "Data", "csvPath": str(csv_path)}]}))
        workbook_path = self.directory / "csv.xlsx"
        run_script("create_xlsx.py", str(workbook_path), str(specification_path))
        cells = read_cells(workbook_path)
        self.assertEqual(cells["A2"], ("text", "007"))
        self.assertEqual(cells["B2"], ("number", "1500"))
        self.assertEqual(cells["C2"], ("number", "2.5"))
        self.assertEqual(cells["D2"], ("text", "1,500"))


class CellValueGrammarTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SCRIPTS_PATH))
        self.addCleanup(sys.path.remove, str(SCRIPTS_PATH))
        from sheet.cell_values import typed_cell_value

        self.typed_cell_value = typed_cell_value

    def test_numbers_and_text_leaving_dates_to_the_write(self):
        expectations = {
            "12": 12,
            "-3": -3,
            "0": 0,
            "2.50": 2.5,
            "-0.75": -0.75,
            "2026-09-30": "2026-09-30",
            "007": "007",
            "+82": "+82",
            "1,500": "1,500",
            "1234567890123456": "1234567890123456",
            "2026-13-40": "2026-13-40",
            "": "",
            "abc": "abc",
        }
        for text, expected in expectations.items():
            self.assertEqual(self.typed_cell_value(text), expected, text)


if __name__ == "__main__":
    unittest.main()
