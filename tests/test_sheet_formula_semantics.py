import json
from pathlib import Path
import unittest

from sheet_fixture import WorkbookFixture

CASES = json.loads((Path(__file__).parent / "sheet_formula_cases.json").read_text(encoding="utf-8"))
DATA_ROWS = [
    [10, 1, "Seoul", 5, 1],
    [None, 2, "Busan", 6, "=1/0"],
    [20, 3, "seoul", 7],
    ["text", 4, None, 8],
    [30, None, "Daegu", 9],
    ["yes"],
    ["5"],
    [7.5],
]
OTHER_ROWS = [[3], [4], [5]]
CHAIN_ROWS = [["=D!B1*2"], ["=D!B2*2"], ["=G!A1+G!A2"], ["=IF(A3>5,\"big\",\"small\")"], ["=1/0"]]


class FormulaSemanticsTest(WorkbookFixture):
    def test_computed_values_match_what_excel_shows(self):
        rows = [[formula] for formula, _, _ in CASES]
        self.create_workbook([
            {"title": "D", "rows": DATA_ROWS, "autoFilter": False},
            {"title": "Other", "rows": OTHER_ROWS, "autoFilter": False},
            {"title": "G", "rows": CHAIN_ROWS, "autoFilter": False},
            {"title": "F", "rows": rows, "autoFilter": False},
        ])
        cells = self.cells(part_name="xl/worksheets/sheet4.xml")
        mismatches = []
        for index, (formula, cell_type, text) in enumerate(CASES, start=1):
            stored = cells[f"A{index}"]
            actual = (None, None) if stored["value"] is None else ({"n": "n", None: "n", "str": "str", "b": "b", "e": "e"}[stored["type"]], stored["value"])
            if actual != (cell_type, text):
                mismatches.append((formula, actual, (cell_type, text)))
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()
