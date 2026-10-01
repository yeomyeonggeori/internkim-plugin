import unittest

from sheet_fixture import WorkbookFixture, run_office, run_office_python, stored_cells, write_json

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


TAMPER_CACHED_VALUES = r"""
import re
import zipfile

with zipfile.ZipFile("book.xlsx") as source:
    entries = {info.filename: source.read(info.filename) for info in source.infolist()}
sheet = entries["xl/worksheets/sheet1.xml"].decode()
sheet = re.sub(r'(<c r="C2"[^>]*><f>[^<]*</f><v>)[^<]*', r'\g<1>25', sheet)
sheet = re.sub(r'(<c r="D2"[^>]*><f>[^<]*</f><v>)[^<]*', r'\g<1>stale', sheet)
entries["xl/worksheets/sheet1.xml"] = sheet.encode()
with zipfile.ZipFile("book.xlsx", "w") as target:
    for name, content in entries.items():
        target.writestr(name, content)
"""


class StaleCachedValueTest(WorkbookFixture):
    def setUp(self):
        super().setUp()
        self.create_workbook([{"title": "Sales", "rows": [["a", "b", "double", "label"], [10, 5, "=A2*2", '="n"&B2'], [1, 2, "=A3*2", '="n"&B3']]}])

    def findings(self):
        envelope = run_office(["sheet", "check", "book.xlsx"], self.directory)
        return [(issue["code"], issue["location"]) for issue in envelope["issues"]]

    def test_a_workbook_written_here_has_no_stale_value(self):
        self.assertEqual(self.findings(), [])

    def test_a_stored_value_that_differs_from_the_computed_one_is_reported_and_recalculated(self):
        run_office_python(TAMPER_CACHED_VALUES, self.directory)
        envelope = run_office(["sheet", "check", "book.xlsx"], self.directory)
        issue = next(issue for issue in envelope["issues"] if issue["code"] == "STALE_CACHED_VALUE")
        self.assertEqual(issue["location"], "Sales!C2")
        self.assertIn("Sales!C2 stores 25 but computes 20", issue["message"])
        self.assertIn("Sales!D2", issue["message"])
        self.assertEqual(self.apply([issue["suggestion"]])["status"], "ok")
        self.assertEqual(self.findings(), [])
        self.assertEqual(stored_cells(self.directory / "book.xlsx")["C2"]["value"], "20")


CHART_FIXTURE = """
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference

workbook = Workbook()
sales = workbook.active
sales.title = "Sales"
for row in [["month", "amount"], ["1월", 10], ["2월", 20]]:
    sales.append(row)
chart = BarChart()
chart.add_data(Reference(sales, min_col=2, min_row=1, max_row=3), titles_from_data=True)
sales.add_chart(chart, "E2")
empty = BarChart()
empty.add_data(Reference(sales, min_col=8, min_row=1, max_row=3), titles_from_data=True)
sales.add_chart(empty, "E20")
workbook.save("charts.xlsx")
"""


class ChartReferenceTest(WorkbookFixture):
    def test_a_chart_reading_an_empty_range_is_reported_and_one_with_data_is_not(self):
        run_office_python(CHART_FIXTURE, self.directory)
        issues = run_office(["sheet", "check", "charts.xlsx"], self.directory)["issues"]
        self.assertEqual([(issue["code"], issue["location"]) for issue in issues], [("CHART_REFERENCE_BROKEN", "Sales chart 1")])
        self.assertIn("$H$2:$H$3", issues[0]["message"])
