import unittest
import zipfile

from sheet_fixture import WorkbookFixture, run_office, run_office_python, stored_cells, write_json


TEMPLATE = """
from openpyxl import Workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
workbook = Workbook()
sheet = workbook.active
sheet.title = "견적서"
sheet["A1"] = "견적서: {{ customer.name }} 귀하"
sheet["A2"] = CellRichText("담당: {{ man", TextBlock(InlineFont(b=True), "ager }}"))
sheet["B3"] = "{{ amount }}"
sheet["B4"] = "=B3*1.1"
sheet["B5"] = "{{ issued }}"
sheet["A6"] = "{{ items.0.name }}"
sheet.oddHeader.center.text = "{{ customer.name }}"
workbook.save("quote.xlsx")
"""


class SheetMergeTest(WorkbookFixture):
    def setUp(self):
        super().setUp()
        run_office_python(TEMPLATE, self.directory)

    def merge(self, values):
        write_json(self.directory / "values.json", values)
        return run_office(["sheet", "merge", "quote.xlsx", "values.json", "filled.xlsx"], self.directory)

    def test_a_whole_cell_placeholder_takes_the_value_type_and_formulas_recompute(self):
        envelope = self.merge({"customer": {"name": "박예시"}, "manager": "최견본", "amount": 1200000, "issued": "2026-10-01", "items": [{"name": "연간 유지보수"}]})
        self.assertEqual(envelope["status"], "ok", envelope)
        cells = stored_cells(self.directory / "filled.xlsx")
        self.assertEqual((cells["B3"]["type"], cells["B3"]["value"]), (None, "1200000"))
        self.assertEqual(cells["B4"]["value"], "1320000")
        self.assertEqual(cells["B5"]["type"], "inlineStr")
        read = run_office(["sheet", "read", "filled.xlsx", "--range", "A1:A6"], self.directory)
        texts = [value for row in read["details"]["range"]["values"] for value in row if value]
        self.assertEqual(texts, ["견적서: 박예시 귀하", "담당: 최견본", "연간 유지보수"])
        with zipfile.ZipFile(self.directory / "filled.xlsx") as archive:
            self.assertIn("박예시".encode(), archive.read("xl/worksheets/sheet1.xml"))

    def test_a_missing_value_or_a_bare_list_writes_nothing(self):
        envelope = self.merge({"customer": {"name": "박예시"}, "manager": "최견본", "amount": 1, "issued": [1, 2]})
        self.assertEqual(sorted((issue["code"], issue["location"]) for issue in envelope["issues"]), [("LIST_NEEDS_A_ROW", "견적서!B5"), ("UNRESOLVED_PLACEHOLDER", "견적서!A6")])
        self.assertFalse((self.directory / "filled.xlsx").exists())

    def test_untouched_parts_are_kept_byte_for_byte(self):
        self.merge({"customer": {"name": "박예시"}, "manager": "최견본", "amount": 5, "issued": "오늘", "items": [{"name": "품목"}]})
        with zipfile.ZipFile(self.directory / "quote.xlsx") as before, zipfile.ZipFile(self.directory / "filled.xlsx") as after:
            unchanged = [name for name in before.namelist() if name not in ("xl/worksheets/sheet1.xml", "xl/sharedStrings.xml") and before.read(name) != after.read(name)]
        self.assertEqual(unchanged, [])


if __name__ == "__main__":
    unittest.main()
