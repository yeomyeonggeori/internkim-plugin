import unittest
import zipfile

from sheet_fixture import WorkbookFixture, run_office, run_office_python

DYNAMIC_ROWS = [
    ["region", "unique", "count"],
    ["Seoul", "=UNIQUE(A2:A6)", "=COUNTA(B2#)"],
    ["Busan"],
    ["Seoul"],
    ["Daegu"],
    ["Busan"],
]


class FunctionNameTest(WorkbookFixture):
    def test_newer_functions_are_stored_with_the_prefix_excel_reads(self):
        self.create_workbook([{"title": "Sheet", "rows": [
            [1, "=XLOOKUP(1,A1:A2,A1:A2)", "=FILTER(A1:A2,A1:A2>0)", "=LET(rate,A1,rate*2)", "=SUM(A1:A2)"],
            [2],
        ]}])
        cells = self.cells()
        self.assertEqual(cells["B1"]["formula"], "_xlfn.XLOOKUP(1,A1:A2,A1:A2)")
        self.assertEqual(cells["C1"]["formula"], "_xlfn._xlws.FILTER(A1:A2,A1:A2>0)")
        self.assertEqual(cells["D1"]["formula"], "_xlfn.LET(_xlpm.rate,A1,_xlpm.rate*2)")
        self.assertEqual((cells["D1"]["value"], cells["E1"]["formula"]), ("2", "SUM(A1:A2)"))

    def test_an_unprefixed_newer_function_written_elsewhere_is_a_name_error(self):
        run_office_python("""
            from openpyxl import Workbook
            workbook = Workbook()
            workbook.active.append([1, "=XLOOKUP(1,A1:A1,A1:A1)"])
            workbook.save("foreign.xlsx")
        """, self.directory)
        envelope = run_office(["sheet", "check", "foreign.xlsx"], self.directory)
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("FORMULA_ERROR", "Sheet!B1")])
        self.assertIn("#NAME?", envelope["issues"][0]["message"])


class DynamicArrayTest(WorkbookFixture):
    def test_a_dynamic_array_formula_spills_its_values_and_marks_itself_for_excel(self):
        envelope = self.create_workbook([{"title": "Sheet", "rows": DYNAMIC_ROWS}])
        self.assertEqual(envelope["status"], "ok", envelope)
        cells = self.cells()
        self.assertEqual(cells["B2"]["formula"], "_xlfn.UNIQUE(A2:A6)")
        self.assertEqual([cells[f"B{row}"]["value"] for row in (2, 3, 4)], ["Seoul", "Busan", "Daegu"])
        self.assertEqual((cells["C2"]["formula"], cells["C2"]["value"]), ("COUNTA(_xlfn.ANCHORARRAY(B2))", "3"))
        with zipfile.ZipFile(self.directory / "book.xlsx") as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode()
            self.assertIn('t="str" cm="1"><f t="array" ref="B2:B4">_xlfn.UNIQUE', sheet)
            self.assertIn("xl/metadata.xml", archive.namelist())
            self.assertIn("sheetMetadata+xml", archive.read("[Content_Types].xml").decode())

    def test_an_edit_respills_into_the_new_extent_and_clears_the_old_one(self):
        self.create_workbook([{"title": "Sheet", "rows": DYNAMIC_ROWS}])
        envelope = self.apply([{"op": "set_cell", "cell": "A6", "value": "Ulsan"}, {"op": "set_cell", "cell": "A4", "value": "Busan"}])
        self.assertEqual(envelope["status"], "ok", envelope)
        cells = self.cells()
        self.assertEqual([cells[f"B{row}"]["value"] for row in (2, 3, 4, 5)], ["Seoul", "Busan", "Daegu", "Ulsan"])
        envelope = self.apply([{"op": "set_cell", "cell": "A5", "value": "Seoul"}, {"op": "set_cell", "cell": "A6", "value": "Seoul"}])
        cells = self.cells()
        self.assertEqual([cells[f"B{row}"]["value"] for row in (2, 3)], ["Seoul", "Busan"])
        self.assertNotIn("B5", {coordinate for coordinate, cell in cells.items() if cell["value"]})
        self.assertEqual(cells["C2"]["value"], "2")


class EvaluatorCompatibilityTest(WorkbookFixture):
    def test_a_not_equal_text_criterion_over_numbers_is_left_for_excel(self):
        envelope = self.create_workbook([{"title": "Sheet", "rows": [["a", 1, '=COUNTIF(A1:A3,"<>a")'], [5, 2], ["b", 3]]}])
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["FORMULA_NOT_EVALUATED"])
        self.assertIsNone(self.cells()["C1"]["value"])

    def test_a_cell_depending_on_an_uncomputed_one_through_iferror_is_not_guessed(self):
        self.create_workbook([{"title": "Sheet", "rows": [["=BAHTTEXT(1)", "=IFERROR(A1,0)", "=Other!A1+1"]]}, {"title": "Other", "rows": [["=Sheet!B1"]]}])
        self.assertEqual([self.cells()[coordinate]["value"] for coordinate in ("A1", "B1", "C1")], [None, None, None])


if __name__ == "__main__":
    unittest.main()
