import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, run_office, write_json


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
        self.assertIn("2026 Q2 South Revenue", view["notes"][0])

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


class PartialPropagationTest(DeclaredWorkbookFixture):
    def test_a_share_of_a_total_missing_an_input_is_marked_on_every_row(self):
        cumulative = {"sheet": "Summary", "title": "Share", "rows": ["Region"], "measures": ["Revenue"], "totals": True, "add": [{"name": "Share", "expression": "share(Revenue, Region)"}]}
        result = self.create(sales_declaration([cumulative]))
        shown = result["details"]["views"][0]["rows"]
        self.assertTrue(all(row[2].endswith("*") for row in shown[1:]), shown)

    def test_a_chart_point_summing_a_missing_input_is_left_out(self):
        by_period = {"sheet": "Summary", "title": "By period", "rows": ["Year", "Quarter"], "measures": ["Revenue"]}
        self.create(sales_declaration([by_period], [{"view": "By period", "type": "line"}]))
        sheet = run_office(["read", "book.xlsx"], self.directory.name)["details"]["sheets"][1]
        series_cells = sheet["charts"][0]["data"][0].split("!")[1].replace("$", "")
        self.assertEqual([row[0] for row in self.values(cell_range=series_cells)][-1], "#N/A")

    def test_the_preview_draws_a_left_out_point_as_a_gap(self):
        self.create(sales_declaration([BY_QUARTER], [{"view": "By quarter", "type": "line"}]))
        rendered = run_office(["render", "book.xlsx", "--sheet", "Summary"], self.directory.name)
        self.assertNotEqual(rendered["status"], "error", rendered)
        preview = Path(self.directory.name, rendered["details"]["preview"]).read_text(encoding="utf-8")
        self.assertEqual(preview.count("<circle"), 5)


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


class CoverageNoteTest(DeclaredWorkbookFixture):
    def test_a_member_covering_fewer_periods_than_its_siblings_is_named_under_the_view(self):
        result = self.create(sales_declaration([BY_QUARTER]))
        notes = result["details"]["views"][0]["notes"]
        self.assertEqual(notes[-1], "Unequal coverage: 2026 (2 of 4 Quarter)")
        self.assertIn("Unequal coverage: 2026 (2 of 4 Quarter)", [row[0] for row in self.values()])

    def test_the_note_is_written_in_the_declaration_language(self):
        result = self.create({**sales_declaration([BY_QUARTER]), "language": "ko"})
        self.assertEqual(result["details"]["views"][0]["notes"][-1], "범위가 다릅니다: 2026 (Quarter 4개 중 2개)")

    def test_a_change_down_the_rows_names_the_member_it_cannot_compare(self):
        by_year = {"sheet": "Summary", "title": "By year", "rows": ["Year"], "measures": ["Revenue"], "add": [{"name": "Growth", "expression": "percentChange(Revenue, Year)"}]}
        result = self.create(sales_declaration([by_year]))
        self.assertIn("2026 (2 of 4 Quarter)", result["details"]["views"][0]["notes"][-1])

    def test_members_laid_side_by_side_over_a_summed_away_dimension_are_labelled(self):
        by_year = {"sheet": "Summary", "title": "By year", "rows": ["Year"], "columns": "Region", "measure": "Revenue", "totals": True}
        result = self.create(sales_declaration([by_year]))
        self.assertIn("2026 (2 of 4 Quarter)", result["details"]["views"][0]["notes"][-1])

    def test_a_view_that_shows_every_period_needs_no_coverage_note(self):
        by_period = {"sheet": "Summary", "title": "By period", "rows": ["Year", "Quarter"], "columns": "Region", "measure": "Revenue"}
        result = self.create(sales_declaration([by_period]))
        self.assertTrue(all("coverage" not in note for note in result["details"]["views"][0].get("notes", [])), result["details"]["views"][0])

    def test_a_view_whose_members_cover_the_same_records_has_no_coverage_note(self):
        result = self.create(BUDGET)
        self.assertTrue(all("coverage" not in note for note in result["details"]["views"][0].get("notes", [])))


BUDGET_CSV = "category,month,budget,actual\nCloud,2026-07,100,120\nTravel,2026-07,50,\n"
BUDGET_COLUMNS = [{"name": "category"}, {"name": "month"}, {"name": "budget", "type": "amount", "unit": "USD"}, {"name": "actual", "type": "amount", "unit": "USD"}]
BUDGET_VIEW = {"sheet": "Summary", "title": "By category", "rows": ["category"], "measures": ["budget", "actual"], "totals": True}


class AttachedTableTest(DeclaredWorkbookFixture):
    def create_with_attachment(self, table, attachment_name="budget.csv", text=BUDGET_CSV):
        attachment = Path(self.directory.name, "attachments", attachment_name)
        attachment.parent.mkdir()
        attachment.write_text(text, encoding="utf-8")
        context = {"requester": {"name": "이샘플", "email": "sample@example.com"}, "today": "2026-10-04", "company": {}, "registeredDocuments": [],
                   "attachments": [{"name": attachment_name, "path": str(attachment)}]}
        write_json(Path(self.directory.name, "context.json"), context)
        write_json(Path(self.directory.name, "book.workbook.json"), {"kind": "workbook", "language": "en", "tables": [table], "views": [BUDGET_VIEW]})
        environment = dict(os.environ, OFFICE_RUNTIME_CONTEXT=str(Path(self.directory.name, "context.json")))
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "book.xlsx", "book.workbook.json"], capture_output=True, text=True, cwd=self.directory.name, env=environment)
        return json.loads(completed.stdout)

    def test_an_attached_csv_typed_into_rows_is_refused_and_csv_path_named(self):
        result = self.create_with_attachment({"name": "Data", "columns": BUDGET_COLUMNS, "rows": [["Cloud", "2026-07", 100, 120], ["Travel", "2026-07", 50, None]]})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["issues"][0]["code"], "DECLARATION_INVALID")
        self.assertIn("budget.csv", result["issues"][0]["message"])
        self.assertIn('"csvPath"', result["issues"][0]["suggestion"])

    def test_an_attached_csv_read_through_csv_path_compiles(self):
        result = self.create_with_attachment({"name": "Data", "columns": BUDGET_COLUMNS, "csvPath": "attachments/budget.csv"})
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["details"]["blanks"], [{"field": "Data!D3", "label": "Travel 2026-07 actual"}])

    def test_an_attached_tsv_is_read_with_tabs(self):
        result = self.create_with_attachment({"name": "Data", "columns": BUDGET_COLUMNS, "csvPath": "attachments/budget.tsv"}, "budget.tsv", BUDGET_CSV.replace(",", "\t"))
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(self.values("Data")[1], ["Cloud", "2026-07", 100, 120])


class DeclarationOnlyTest(DeclaredWorkbookFixture):
    def test_a_workbook_spec_with_sheets_is_refused_for_the_declaration(self):
        write_json(Path(self.directory.name, "spec.json"), {"sheets": [{"title": "S", "rows": [["a", "b"], [1, "=A2*2"]]}]})
        result = run_office(["create", "book.xlsx", "spec.json"], self.directory.name)
        self.assertEqual(result["issues"][0]["code"], "DECLARATION_REQUIRED")
        self.assertFalse(Path(self.directory.name, "book.xlsx").exists())

    def test_a_csv_is_not_typed_into_a_new_workbook(self):
        Path(self.directory.name, "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        result = run_office(["create", "book.xlsx", "data.csv"], self.directory.name)
        self.assertEqual(result["issues"][0]["code"], "DECLARATION_REQUIRED")
        self.assertIn("csvPath", result["issues"][0]["message"])


class CompiledCellsTest(DeclaredWorkbookFixture):
    def apply(self, operations, *extra):
        write_json(Path(self.directory.name, "ops.json"), operations)
        return run_office(["apply", "book.xlsx", "ops.json", *extra], self.directory.name)

    def test_create_records_the_declaration_and_its_compiled_ranges_beside_the_workbook(self):
        self.create(BUDGET)
        source = json.loads(Path(self.directory.name, "book.xlsx.source.json").read_text(encoding="utf-8"))
        self.assertEqual(source["declaration"], str(Path(self.directory.name, "book.workbook.json").resolve()))
        self.assertIn({"sheet": "Data", "range": "A1:C4"}, source["compiled"])
        self.assertIn({"sheet": "Summary", "range": "A1:E7"}, source["compiled"])
        self.assertEqual(source["blanks"], [{"field": "Data!C3", "label": "Travel Actual"}])

    def test_apply_refuses_to_write_into_a_compiled_view(self):
        self.create(BUDGET)
        before = Path(self.directory.name, "book.xlsx").read_bytes()
        result = self.apply([{"op": "set_cell", "sheet": "Summary", "cell": "C3", "value": 125}])
        self.assertEqual(result["issues"][0]["code"], "COMPILED_CELLS")
        self.assertIn("Summary!C3", result["issues"][0]["message"])
        self.assertIn("book.workbook.json", result["issues"][0]["suggestion"])
        self.assertEqual(Path(self.directory.name, "book.xlsx").read_bytes(), before)

    def test_apply_refuses_to_fill_a_declared_blank_input(self):
        self.create(BUDGET)
        result = self.apply([{"op": "set_cell", "sheet": "Data", "cell": "C3", "value": "집계 전"}])
        self.assertEqual(result["issues"][0]["code"], "COMPILED_CELLS")
        self.assertIn("Data!C3", result["issues"][0]["message"])

    def test_apply_refuses_to_shift_compiled_rows(self):
        self.create(BUDGET)
        result = self.apply([{"op": "insert_rows", "sheet": "Data", "at": 2, "count": 1}])
        self.assertEqual(result["issues"][0]["code"], "COMPILED_CELLS")

    def test_apply_refuses_to_rename_a_compiled_sheet(self):
        self.create(BUDGET)
        result = self.apply([{"op": "rename_sheet", "sheet": "Summary", "name": "요약"}])
        self.assertEqual(result["issues"][0]["code"], "COMPILED_CELLS")
        self.assertIn("sheet Summary", result["issues"][0]["message"])

    def test_apply_still_formats_compiled_cells_and_writes_outside_them(self):
        self.create(BUDGET)
        result = self.apply([
            {"op": "format_range", "sheet": "Summary", "range": "A2:E2", "bold": True},
            {"op": "add_sheet", "name": "Notes"},
            {"op": "set_cell", "sheet": "Notes", "cell": "A1", "value": "memo"},
        ])
        self.assertNotEqual(result["status"], "error", result)
        self.assertTrue(Path(self.directory.name, "book.xlsx.source.json").is_file())


if __name__ == "__main__":
    unittest.main()
