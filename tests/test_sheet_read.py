import unittest

from sheet_fixture import WorkbookFixture, run_office, run_office_python

FIXTURE_WORKBOOK = """
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.table import Table

workbook = Workbook()
sales = workbook.active
sales.title = "Sales"
for row in [["item", "amount"], ["A", 10], ["B", 20], ["C", 30]]:
    sales.append(row)
sales["B5"] = "=SUM(B2:B4)"
sales["D1"] = "=B5*2"
sales.freeze_panes = "A2"
sales.auto_filter.ref = "A1:B4"
sales.merge_cells("D3:E3")
sales.add_table(Table(displayName="SalesTable", ref="A1:B4"))
chart = BarChart()
chart.add_data(Reference(sales, min_col=2, min_row=1, max_row=4), titles_from_data=True)
sales.add_chart(chart, "G2")
workbook.create_sheet("Notes")["A1"] = "memo"
workbook.defined_names["Total"] = DefinedName("Total", attr_text="Sales!$B$5")
workbook.save("fixture.xlsx")
"""


class ReadTest(WorkbookFixture):
    def setUp(self):
        super().setUp()
        run_office_python(FIXTURE_WORKBOOK, self.directory)

    def read(self, *arguments):
        envelope = run_office(["sheet", "read", "fixture.xlsx", *arguments], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope)
        return envelope["details"]

    def test_each_sheet_reports_its_dimensions_and_features(self):
        sales = self.read()["sheets"][0]
        self.assertEqual(sales["name"], "Sales")
        self.assertEqual(sales["dimensions"], "A1:E5")
        self.assertEqual(sales["frozenPanes"], "A2")
        self.assertEqual(sales["autoFilter"], "A1:B4")
        self.assertEqual(sales["mergedCells"], ["D3:E3"])
        self.assertEqual(sales["tables"], [{"name": "SalesTable", "range": "A1:B4"}])
        self.assertEqual(sales["charts"], 1)

    def test_defined_names_are_listed_with_what_they_point_at(self):
        self.assertEqual(self.read()["definedNames"], [{"name": "Total", "value": "Sales!$B$5", "scope": None}])

    def test_a_range_returns_values_and_formulas_side_by_side(self):
        selected = self.read("--range", "A4:B5")["range"]
        self.assertEqual(selected["formulas"], [[None, None], [None, "=SUM(B2:B4)"]])
        self.assertEqual(selected["values"][0], ["C", 30])

    def test_where_formula_lists_only_formula_cells(self):
        cells = self.read("--where", "formula")["range"]["cells"]
        self.assertEqual([(cell["cell"], cell["formula"]) for cell in cells], [("D1", "=B5*2"), ("B5", "=SUM(B2:B4)")])

    def test_rows_beyond_the_limit_are_left_out_and_flagged(self):
        selected = self.read("--limit", "2")["range"]
        self.assertEqual((len(selected["values"]), selected["truncated"]), (2, True))

    def test_another_sheet_is_chosen_by_name(self):
        self.assertEqual(self.read("--sheet", "Notes")["range"]["values"], [["memo"]])

    def test_an_unknown_sheet_is_refused_with_the_names_that_exist(self):
        envelope = run_office(["sheet", "read", "fixture.xlsx", "--sheet", "Missing"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["TARGET_NOT_FOUND"])
        self.assertIn("Sales, Notes", envelope["issues"][0]["message"])


if __name__ == "__main__":
    unittest.main()
