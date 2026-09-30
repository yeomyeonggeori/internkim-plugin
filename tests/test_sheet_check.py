import unittest

from sheet_fixture import WorkbookFixture, run_office, run_office_python, write_json

FIXTURE_WORKBOOK = """
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

workbook = Workbook()
sales = workbook.active
sales.title = "Sales"
sales["A1"] = 10
sales["A2"] = 0
sales["B1"] = "=A1/A2"
sales["B2"] = "=Gone!A1"
sales["C1"] = 123456789
sales["C1"].number_format = "#,##0"
sales["D1"] = "{{customer_name}} 님"
sales["E1"] = "=SUM(A1:A2)"
workbook.defined_names["Orphan"] = DefinedName("Orphan", attr_text="Gone!$A$1")
workbook.defined_names["Fine"] = DefinedName("Fine", attr_text="Sales!$A$1")
workbook.save("fixture.xlsx")
"""


class SheetCheckTest(WorkbookFixture):
    def setUp(self):
        super().setUp()
        run_office_python(FIXTURE_WORKBOOK, self.directory)

    def check(self):
        return run_office(["sheet", "check", "fixture.xlsx"], self.directory)

    def findings(self):
        return {(issue["code"], issue["location"]) for issue in self.check()["issues"]}

    def test_each_problem_is_reported_once_where_it_is(self):
        self.assertEqual(self.findings(), {
            ("FORMULA_ERROR", "Sales!B1"),
            ("MISSING_SHEET_REFERENCE", "Sales!B2"),
            ("BROKEN_DEFINED_NAME", "Orphan"),
            ("NUMBER_TOO_WIDE", "Sales!C1"),
            ("PLACEHOLDER_LEFT", "Sales!D1"),
        })

    def test_the_computed_error_is_named(self):
        message = next(issue["message"] for issue in self.check()["issues"] if issue["code"] == "FORMULA_ERROR")
        self.assertIn("#DIV/0!", message)

    def test_the_suggested_width_fixes_the_narrow_column(self):
        suggestion = next(issue["suggestion"] for issue in self.check()["issues"] if issue["code"] == "NUMBER_TOO_WIDE")
        self.assertEqual({key: suggestion[key] for key in ("op", "sheet", "column")}, {"op": "set_column_width", "sheet": "Sales", "column": "C"})
        self.assertEqual(self.apply([suggestion], name="fixture.xlsx")["status"], "ok")
        self.assertNotIn(("NUMBER_TOO_WIDE", "Sales!C1"), self.findings())

    def test_a_number_that_fits_is_left_alone(self):
        write_json(self.directory / "ops.json", [{"op": "set_column_width", "column": "C", "width": 14}])
        run_office(["sheet", "apply", "fixture.xlsx", "ops.json"], self.directory)
        self.assertNotIn(("NUMBER_TOO_WIDE", "Sales!C1"), self.findings())

    def test_a_created_workbook_sizes_its_columns_for_its_numbers(self):
        self.create_workbook([{"title": "표", "rows": [["이름", "금액"], ["박예시", 1500000]]}])
        envelope = run_office(["sheet", "check", "book.xlsx"], self.directory)
        self.assertEqual(envelope["issues"], [])

    def test_validate_no_longer_reports_formula_errors(self):
        codes = {issue["code"] for issue in run_office(["sheet", "validate", "fixture.xlsx"], self.directory)["issues"]}
        self.assertNotIn("FORMULA_ERROR_MARKER", codes)


if __name__ == "__main__":
    unittest.main()
