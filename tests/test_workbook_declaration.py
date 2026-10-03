from pathlib import Path
import tempfile
import unittest

from doc_fixture import run_office, write_json


SALES = {"2025": {"Q1": [820, 410], "Q2": [870, 395], "Q3": [905, 450], "Q4": [990, 480]}, "2026": {"Q1": [940, 455], "Q2": [1010, None]}}
SALES_ROWS = [[int(year), quarter, region, value] for year, quarters in SALES.items() for quarter, values in quarters.items() for region, value in zip(["North", "South"], values)]
SALES_TABLE = {"name": "Data", "columns": [{"name": "Year"}, {"name": "Quarter"}, {"name": "Region"}, {"name": "Revenue", "type": "amount", "unit": "USD"}], "rows": SALES_ROWS}


def sales_declaration(views, charts=()):
    return {"kind": "workbook", "language": "en", "tables": [SALES_TABLE], "views": views, "charts": list(charts)}


BY_QUARTER = {"sheet": "Summary", "title": "By quarter", "rows": ["Quarter"], "columns": "Year", "measure": "Revenue", "totals": True, "add": [{"name": "YoY", "expression": "percentChange(Revenue, Year)"}]}
BY_REGION = {"sheet": "Summary", "title": "By region", "rows": ["Region"], "columns": "Year", "measure": "Revenue", "totals": True, "add": [{"name": "Share", "expression": "share(Revenue, Region)"}]}
BUDGET = {
    "kind": "workbook",
    "tables": [{"name": "Data", "columns": [{"name": "Category"}, {"name": "Budget", "type": "amount", "unit": "USD"}, {"name": "Actual", "type": "amount", "unit": "USD"}], "rows": [["Cloud", 100, 120], ["Travel", 50, None], ["Training", 0, 10]]}],
    "views": [{"sheet": "Summary", "title": "Budget vs actual", "rows": ["Category"], "measures": ["Budget", "Actual"], "totals": True, "add": [
        {"name": "Variance", "expression": "Actual - Budget"},
        {"name": "Variance %", "expression": "(Actual - Budget) / Budget"},
    ]}],
}


class DeclaredWorkbookFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def create(self, declaration):
        write_json(Path(self.directory.name, "book.workbook.json"), declaration)
        return run_office(["create", "book.xlsx", "book.workbook.json"], self.directory.name)

    def values(self, sheet="Summary", cell_range=None):
        arguments = ["read", "book.xlsx", "--sheet", sheet] + (["--range", cell_range] if cell_range else [])
        return run_office(arguments, self.directory.name)["details"]["range"]["values"]

    def formats(self, sheet="Summary"):
        cells = run_office(["read", "book.xlsx", "--sheet", sheet, "--formats"], self.directory.name)["details"]
        return cells


class ViewValueTest(DeclaredWorkbookFixture):
    def test_cells_sum_the_source_rows_of_their_coordinate(self):
        self.create(sales_declaration([BY_QUARTER]))
        rows = self.values()
        self.assertEqual(rows[1][:4], ["Quarter", 2025, 2026, "YoY"])
        self.assertEqual(rows[2][:3], ["Q1", 1230, 1395])
        self.assertEqual(rows[6][:2], ["Total", 5320])

    def test_a_sum_missing_a_value_adds_only_the_values_given_and_says_so(self):
        result = self.create(sales_declaration([BY_QUARTER]))
        rows = self.values()
        self.assertEqual(rows[3][2], 1010)
        self.assertEqual(rows[6][2], 2405)
        view = result["details"]["views"][0]
        self.assertEqual(view["rows"][2][2], "$1,010*")
        self.assertIn("2026 Q2 South Revenue", view["note"])

    def test_a_period_with_no_rows_is_blank(self):
        self.create(sales_declaration([BY_QUARTER]))
        self.assertIsNone(self.values()[5][2])

    def test_year_over_year_compares_only_cells_that_cover_the_same_rows(self):
        self.create(sales_declaration([BY_QUARTER]))
        rows = self.values()
        self.assertAlmostEqual(rows[2][3], 1395 / 1230 - 1)
        self.assertIsNone(rows[3][3])
        self.assertIsNone(rows[6][3])

    def test_a_share_divides_by_its_column_total(self):
        self.create(sales_declaration([BY_REGION]))
        rows = self.values()
        self.assertAlmostEqual(rows[2][3], (820 + 870 + 905 + 990) / 5320)
        self.assertEqual(rows[4][3], 1)

    def test_views_on_one_sheet_stack_without_overlapping(self):
        self.create(sales_declaration([BY_QUARTER, BY_REGION]))
        rows = self.values()
        titles = [row[0] for row in rows if row and row[0] in ("By quarter", "By region")]
        self.assertEqual(titles, ["By quarter", "By region"])


class MeasureArithmeticTest(DeclaredWorkbookFixture):
    def test_variance_and_its_percent_are_computed_per_row_and_on_the_total(self):
        self.create(BUDGET)
        rows = self.values()
        self.assertEqual(rows[1], ["Category", "Budget (USD)", "Actual (USD)", "Variance", "Variance %"])
        self.assertEqual(rows[2][1:4], [100, 120, 20])
        self.assertAlmostEqual(rows[2][4], 0.2)

    def test_a_variance_is_computed_only_over_the_same_records(self):
        self.create(BUDGET)
        rows = self.values()
        self.assertEqual(rows[3][2:5], [None, None, None])
        self.assertEqual(rows[5][2], 130)
        self.assertEqual(rows[5][3:5], [None, None])

    def test_a_zero_budget_leaves_the_percent_blank_instead_of_an_error(self):
        self.create(BUDGET)
        self.assertIsNone(self.values()[4][4])

    def test_the_result_lists_each_blank_input_cell(self):
        result = self.create(BUDGET)
        self.assertEqual(result["details"]["blanks"], [{"field": "Data!C3", "label": "Travel Actual"}])

    def test_the_result_shows_each_view_as_it_displays(self):
        result = self.create(sales_declaration([BY_QUARTER]))
        view = result["details"]["views"][0]
        self.assertEqual(view["title"], "By quarter")
        self.assertEqual(view["rows"][1], ["Q1", "$1,230", "$1,395", "13.4%"])
        self.assertEqual(view["rows"][3][2:], ["", ""])


class NumberFormatTest(DeclaredWorkbookFixture):
    def test_formats_follow_each_column_unit_and_each_computed_type(self):
        self.create(BUDGET)
        details = run_office(["read", "book.xlsx", "--sheet", "Summary", "--range", "B3:E3", "--formats"], self.directory.name)["details"]
        formats = {cell["cell"]: cell.get("numberFormat") for cell in details["range"]["cells"]}
        self.assertEqual(formats["B3"], '"$"#,##0')
        self.assertEqual(formats["E3"], "0.0%")


    def test_a_header_names_its_unit_once(self):
        units = {"kind": "workbook", "tables": [{"name": "Data", "columns": [{"name": "Item"}, {"name": "units", "type": "quantity", "unit": "units"}, {"name": "Revenue", "type": "amount", "unit": "USD"}], "rows": [["A", 1, 10]]}],
                 "views": [{"sheet": "Summary", "title": "By item", "rows": ["Item"], "measures": ["units", "Revenue"]}]}
        self.create(units)
        self.assertEqual(self.values()[1], ["Item", "units", "Revenue (USD)"])

    def test_a_numeric_dimension_is_written_as_it_is(self):
        typed_year = {**SALES_TABLE, "columns": [{"name": "Year", "type": "quantity", "role": "dimension"}, *SALES_TABLE["columns"][1:]]}
        self.create({"kind": "workbook", "language": "en", "tables": [typed_year], "views": [BY_QUARTER]})
        details = run_office(["read", "book.xlsx", "--sheet", "Data", "--range", "A2:D2", "--formats"], self.directory.name)["details"]
        formats = {cell["cell"]: cell.get("numberFormat") for cell in details["range"]["cells"]}
        self.assertIn(formats.get("A2"), (None, "General"))
        self.assertEqual(formats["D2"], '"$"#,##0')

class ChartTest(DeclaredWorkbookFixture):
    def test_a_chart_draws_missing_values_as_gaps(self):
        result = self.create(sales_declaration([BY_QUARTER], [{"view": "By quarter", "type": "line", "title": "Revenue"}]))
        self.assertEqual(result["status"], "ok", result)
        sheet = run_office(["read", "book.xlsx"], self.directory.name)["details"]["sheets"][1]
        self.assertEqual(len(sheet["charts"]), 1)
        series_cells = sheet["charts"][0]["data"][2].split("!")[1].replace("$", "")
        values = self.values(cell_range=series_cells)
        self.assertEqual([row[0] for row in values], [1395, "#N/A", "#N/A", "#N/A"])

    def test_a_partial_sum_is_left_out_of_its_chart(self):
        self.create(sales_declaration([BY_QUARTER], [{"view": "By quarter", "type": "line"}]))
        sheet = run_office(["read", "book.xlsx"], self.directory.name)["details"]["sheets"][1]
        series_cells = sheet["charts"][0]["data"][2].split("!")[1].replace("$", "")
        self.assertEqual(self.values(cell_range=series_cells)[1][0], "#N/A")

    def test_a_view_with_two_row_dimensions_is_charted_with_joined_labels(self):
        by_year_quarter = {"sheet": "Summary", "title": "By year and quarter", "rows": ["Year", "Quarter"], "columns": "Region", "measure": "Revenue"}
        result = self.create(sales_declaration([by_year_quarter], [{"view": "By year and quarter", "type": "line"}]))
        self.assertEqual(result["status"], "ok", result)
        sheet = run_office(["read", "book.xlsx"], self.directory.name)["details"]["sheets"][1]
        category_cells = sheet["charts"][0]["data"][1].split("!")[1].replace("$", "")
        labels = [row[0] for row in self.values(cell_range=category_cells)]
        self.assertEqual(labels[:2], ["2025 Q1", "2025 Q2"])
        self.assertEqual(labels[-1], "2026 Q2")


class CheckTest(DeclaredWorkbookFixture):
    def test_a_compiled_workbook_passes_check(self):
        self.create(sales_declaration([BY_QUARTER, BY_REGION], [{"view": "By quarter", "type": "line"}]))
        result = run_office(["check", "book.xlsx"], self.directory.name)
        self.assertEqual([issue["message"] for issue in result["issues"]], [])


class DeclarationErrorTest(DeclaredWorkbookFixture):
    def test_a_measure_named_where_a_dimension_belongs_is_refused(self):
        result = self.create(sales_declaration([{**BY_QUARTER, "columns": "Revenue"}]))
        self.assertEqual(result["issues"][0]["code"], "DECLARATION_INVALID")

    def test_an_unknown_column_names_the_ones_that_exist(self):
        result = self.create(sales_declaration([{**BY_QUARTER, "rows": ["Month"]}]))
        self.assertIn("Year, Quarter, Region, Revenue", result["issues"][0]["message"])


if __name__ == "__main__":
    unittest.main()
