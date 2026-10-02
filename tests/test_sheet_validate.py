import unittest

from sheet_fixture import WorkbookFixture, run_office


HEADER = ["month", "sales"]
TABLE_ROWS = [HEADER] + [[f"2025-{month:02d}", month * 10] for month in range(1, 13)]
SUMMARY_ROWS = [["item", "value"], ["total", 780], ["growth", 0.1], ["peak", 120], ["low", 10]]


class StructureRuleTest(WorkbookFixture):
    def validate(self, sheets):
        self.create_workbook([{**sheet, "freezePanes": "", "autoFilter": False} for sheet in sheets])
        envelope = run_office(["check", "book.xlsx"], self.directory)
        return [(issue["code"], issue["location"]) for issue in envelope["issues"]]

    def test_a_data_table_needs_a_frozen_header_and_a_filter(self):
        self.assertEqual(self.validate([{"title": "Sales", "rows": TABLE_ROWS}]), [("HEADER_NOT_FROZEN", "Sales"), ("AUTO_FILTER_MISSING", "Sales")])

    def test_a_short_summary_sheet_needs_neither(self):
        self.assertEqual(self.validate([{"title": "Summary", "rows": SUMMARY_ROWS}]), [])

    def test_a_table_with_one_column_is_not_a_data_table(self):
        self.assertEqual(self.validate([{"title": "List", "rows": [["name"]] + [[f"n{index}"] for index in range(20)]}]), [])

    def test_blank_headers_are_still_reported_on_a_short_sheet(self):
        self.assertEqual(self.validate([{"title": "Summary", "rows": [["item", "", "unit"], ["total", 780, "KRW"]]}]), [("BLANK_HEADER_CELLS", "Summary")])

    def test_a_pivot_table_is_not_held_to_the_header_rules(self):
        regions = ["Seoul", "Busan", "Daegu"]
        rows = [["region", "product", "amount"]] + [[regions[index % 3], f"p{index % 4}", index * 10] for index in range(24)]
        self.create_workbook([{"title": "Sales", "rows": rows}])
        pivot = {"op": "add_pivot_table", "range": "A1:C25", "row": "product", "column": "region", "values": ["amount"]}
        self.assertEqual(self.apply([pivot])["status"], "ok")
        envelope = run_office(["check", "book.xlsx"], self.directory)
        self.assertEqual(envelope["issues"], [])


if __name__ == "__main__":
    unittest.main()
