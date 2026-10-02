import unittest

from sheet_fixture import WorkbookFixture, run_office, write_json

PRICING_ROWS = [
    ["region", "qty", "price", "amount", "share"],
    ["Seoul", 2, 1.5, "=B2*C2", "=D2/$D$4"],
    ["Busan", 3, 2, "=B3*C3", "=D3/$D$4"],
    ["Total", "", "", "=SUM(D2:D3)", '=IF(D4>8,"high","low")'],
]
SUMMARY_ROWS = [["grand", "=Pricing!D4*2", "='요약 시트'!A2+1"], [10]]


class FormulaValueTest(WorkbookFixture):
    def create_pricing(self):
        self.create_workbook([{"title": "Pricing", "rows": PRICING_ROWS}, {"title": "요약 시트", "rows": SUMMARY_ROWS}])

    def test_every_formula_keeps_its_text_and_gains_its_computed_value(self):
        self.create_pricing()
        cells = self.cells()
        self.assertEqual((cells["D2"]["formula"], cells["D2"]["value"]), ("B2*C2", "3"))
        self.assertEqual((cells["D4"]["formula"], cells["D4"]["value"]), ("SUM(D2:D3)", "9"))
        self.assertEqual((cells["E2"]["formula"], cells["E2"]["value"]), ("D2/$D$4", "0.3333333333333333"))
        self.assertEqual((cells["E4"]["formula"], cells["E4"]["value"], cells["E4"]["type"]), ('IF(D4>8,"high","low")', "high", "str"))

    def test_a_formula_reading_another_sheet_is_computed(self):
        self.create_pricing()
        cells = self.cells(part_name="xl/worksheets/sheet2.xml")
        self.assertEqual((cells["B1"]["formula"], cells["B1"]["value"]), ("Pricing!D4*2", "18"))
        self.assertEqual((cells["C1"]["formula"], cells["C1"]["value"]), ("'요약 시트'!A2+1", "11"))

    def test_an_error_result_is_stored_as_an_error_value(self):
        self.create_workbook([{"title": "Sheet", "rows": [[1, 0, "=A1/B1"]]}])
        cell = self.cells()["C1"]
        self.assertEqual((cell["formula"], cell["value"], cell["type"]), ("A1/B1", "#DIV/0!", "e"))

    def test_an_uncomputable_formula_is_kept_without_a_value_and_reported(self):
        envelope = self.create_workbook([{"title": "Sheet", "rows": [[1, "=BAHTTEXT(A1)", "=B1&A1"]]}])
        cells = self.cells()
        self.assertEqual((cells["B1"]["formula"], cells["B1"]["value"]), ("BAHTTEXT(A1)", None))
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["FORMULA_NOT_EVALUATED"])
        self.assertIn("Sheet!B1", envelope["issues"][0]["message"])
        self.assertEqual(envelope["status"], "warning")

    def test_appended_rows_recompute_the_totals_that_were_already_there(self):
        self.create_pricing()
        envelope = self.apply([{"op": "append_rows", "rows": [["Daegu", 5, 1, "=B5*C5"]]}])
        self.assertEqual(envelope["status"], "ok", envelope)
        cells = self.cells()
        self.assertEqual((cells["D5"]["formula"], cells["D5"]["value"]), ("B5*C5", "5"))
        self.assertEqual(cells["D4"]["value"], "9")


if __name__ == "__main__":
    unittest.main()
