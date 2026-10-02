import datetime
import unittest
import zipfile

from openpyxl import load_workbook

from sheet_fixture import WorkbookFixture, run_office

ORDERS = [["date", "region", "channel", "product", "qty", "amount", "cost"]] + [
    ["2024-01-15", "Seoul", "Online", "A", 3, 3000, 1800],
    ["2024-02-03", "Busan", "Store", "A", 5, 5000, 3200],
    ["2024-02-20", "Seoul", "Store", "B", 2, 4000, 2500],
    ["2024-04-11", "Daegu", "Online", "A", 7, 7000, 4100],
    ["2024-05-30", "Busan", "Online", "B", 1, 2000, 1300],
    ["2025-01-08", "Seoul", "Online", "A", 4, 4000, 2300],
]
SOURCE = "A1:G7"


def archive_text(path, part):
    with zipfile.ZipFile(path) as archive:
        return archive.read(part).decode()


class PivotFixture(WorkbookFixture):
    def setUp(self):
        super().setUp()
        self.create_workbook([{"title": "Orders", "rows": ORDERS}])

    def pivot(self, **fields):
        envelope = self.apply([{"op": "add_pivot_table", "range": SOURCE, **fields}])
        self.assertEqual(envelope["status"], "ok", envelope)
        return envelope

    def refused(self, **fields):
        envelope = self.apply([{"op": "add_pivot_table", "range": SOURCE, **fields}])
        self.assertEqual(envelope["status"], "error", envelope)
        return envelope["issues"][0]

    def grid(self, first_row=3, last_row=None, columns=8):
        sheet = load_workbook(self.directory / "book.xlsx")["Pivot"]
        rows = [[cell.value for cell in row] for row in sheet.iter_rows(min_row=first_row, max_row=last_row or sheet.max_row, max_col=columns)]
        return [row[:max((index + 1 for index, value in enumerate(row) if value is not None), default=0)] for row in rows]

    def part(self, name):
        return archive_text(self.directory / "book.xlsx", name)

    def reloaded_pivot(self):
        return load_workbook(self.directory / "book.xlsx")["Pivot"]._pivots[0]


class NestedFieldsTest(PivotFixture):
    def test_two_row_fields_nest_with_a_subtotal_row_per_outer_item(self):
        self.pivot(row=["region", "product"], values=["amount"])
        self.assertEqual(self.grid(), [
            ["region", "product", "Sum of amount"],
            ["Busan", "A", 5000],
            [None, "B", 2000],
            ["Busan Total", None, 7000],
            ["Daegu", "A", 7000],
            ["Daegu Total", None, 7000],
            ["Seoul", "A", 7000],
            [None, "B", 4000],
            ["Seoul Total", None, 11000],
            ["Grand Total", None, 25000],
        ])
        table = self.part("xl/pivotTables/pivotTable1.xml")
        self.assertIn('<rowFields count="2"><field x="1"/><field x="3"/></rowFields>', table)
        self.assertIn('<i r="1"><x v="1"/></i><i t="default"><x/></i>', table)
        self.assertIn('firstDataCol="2"', table)
        pivot = self.reloaded_pivot()
        self.assertEqual((len(pivot.rowFields), pivot.location.ref), (2, "A3:C12"))

    def test_two_column_fields_add_a_subtotal_column_per_outer_item(self):
        self.pivot(row="region", column=["channel", "product"], values=["qty"])
        grid = self.grid()
        self.assertEqual(grid[0], ["Sum of qty", "channel", "product"])
        self.assertEqual(grid[1], [None, "Online", None, "Online Total", "Store", None, "Store Total", "Grand Total"])
        self.assertEqual(grid[2], ["region", "A", "B", None, "A", "B"])
        self.assertEqual(grid[3], ["Busan", None, 1, 1, 5, None, 5, 6])
        self.assertEqual(grid[-1], ["Grand Total", 14, 1, 15, 5, 2, 7, 22])
        self.assertIn('<colFields count="2"><field x="2"/><field x="3"/></colFields>', self.part("xl/pivotTables/pivotTable1.xml"))
        self.assertEqual(self.reloaded_pivot().location.firstDataRow, 3)


class ValueFieldsTest(PivotFixture):
    def test_values_take_their_own_function_percent_and_formula(self):
        self.pivot(row="region", values=[
            "amount",
            {"field": "qty", "function": "average"},
            {"field": "amount", "showAs": "percent_of_total", "label": "Share"},
            {"field": "margin", "formula": "amount-cost", "label": "Margin"},
            {"field": "rate", "formula": "(amount - cost) / amount", "showAs": "value", "numberFormat": "0.0%"},
        ])
        grid = self.grid()
        self.assertEqual(grid[0], ["region", "Sum of amount", "Average of qty", "Share", "Margin", "Sum of rate"])
        self.assertEqual(grid[1][:5], ["Busan", 7000, 3, 0.28, 2500])
        self.assertAlmostEqual(grid[1][5], 2500 / 7000)
        self.assertEqual([grid[-1][index] for index in (0, 1, 3, 4)], ["Grand Total", 25000, 1, 9800])
        self.assertAlmostEqual(grid[-1][2], 22 / 6)
        cache = self.part("xl/pivotCache/pivotCacheDefinition1.xml")
        self.assertIn('<cacheField name="margin" numFmtId="0" formula="\'amount\'-\'cost\'" databaseField="0"/>', cache)
        table = self.part("xl/pivotTables/pivotTable1.xml")
        self.assertIn('subtotal="average"', table)
        self.assertIn('showDataAs="percentOfTotal"', table)
        self.assertIn('<dataField name="Margin" fld="7"', table)
        pivot = self.reloaded_pivot()
        self.assertEqual([field.formula for field in pivot.cache.cacheFields[7:]], ["'amount'-'cost'", "('amount'-'cost')/'amount'"])
        self.assertEqual(load_workbook(self.directory / "book.xlsx")["Pivot"]["D4"].number_format, "0.0%")

    def test_percent_of_row_and_column_divide_by_their_own_totals(self):
        self.pivot(row="region", column="channel", values=[{"field": "amount", "showAs": "percent_of_row"}])
        grid = self.grid()
        self.assertEqual(grid[2], ["Busan", 2000 / 7000, 5000 / 7000, 1])
        self.assertEqual(grid[-1], ["Grand Total", 16000 / 25000, 9000 / 25000, 1])
        self.pivot(row="region", column="channel", values=[{"field": "amount", "showAs": "percent_of_column"}], targetCell="A12")
        grid = self.grid(first_row=12)
        self.assertEqual(grid[2], ["Busan", 2000 / 16000, 5000 / 9000, 7000 / 25000])
        self.assertIn('showDataAs="percentOfCol"', self.part("xl/pivotTables/pivotTable2.xml"))


class DateGroupingTest(PivotFixture):
    def test_dates_group_by_month_in_a_real_field_group(self):
        envelope = self.pivot(row="date", values=["amount"], groupDates={"date": "month"})
        self.assertNotIn("as dates", envelope["details"]["changes"][0]["change"])
        self.assertEqual(load_workbook(self.directory / "book.xlsx")["Orders"]["A2"].value, datetime.datetime(2024, 1, 15))
        self.assertEqual(self.grid(), [["date", "Sum of amount"], ["Jan", 7000], ["Feb", 9000], ["Apr", 7000], ["May", 2000], ["Grand Total", 25000]])
        cache = self.part("xl/pivotCache/pivotCacheDefinition1.xml")
        self.assertIn('<rangePr groupBy="months" startDate="2024-01-15T00:00:00" endDate="2025-01-09T00:00:00"/>', cache)
        self.assertIn('<groupItems count="14"><s v="&lt;2024-01-15"/><s v="Jan"/>', cache)
        self.assertIn('<d v="2024-01-15T00:00:00"/>', self.part("xl/pivotCache/pivotCacheRecords1.xml"))
        self.assertEqual(self.reloaded_pivot().cache.cacheFields[0].fieldGroup.rangePr.groupBy, "months")

    def test_dates_kept_as_text_are_stored_as_dates_when_they_group(self):
        self.apply([{"op": "set_range", "sheet": "Orders", "cell": "A2", "values": [[row[0]] for row in ORDERS[1:]], "type": "text"}])
        self.assertEqual(load_workbook(self.directory / "book.xlsx")["Orders"]["A2"].value, "2024-01-15")
        envelope = self.pivot(row="date", values=["amount"], groupDates={"date": "month"})
        self.assertIn("stored 6 YYYY-MM-DD texts of 'date' as dates", envelope["details"]["changes"][0]["change"])
        self.assertEqual(load_workbook(self.directory / "book.xlsx")["Orders"]["A2"].value, datetime.datetime(2024, 1, 15))

    def test_quarters_and_years_group_across_rows_and_columns(self):
        self.pivot(row="region", column="date", values=["qty"], groupDates={"date": "year"})
        self.assertEqual(self.grid()[1], ["region", "2024", "2025", "Grand Total"])
        self.assertEqual(self.grid()[-1], ["Grand Total", 18, 4, 22])
        self.pivot(row="date", values=["qty"], groupDates={"date": "quarter"}, targetCell="F3")
        sheet = load_workbook(self.directory / "book.xlsx")["Pivot"]
        self.assertEqual([[cell.value for cell in row] for row in sheet["F4:G5"]], [["Qtr1", 14], ["Qtr2", 8]])

    def test_a_text_cell_in_a_grouped_column_is_named_with_its_row(self):
        self.apply([{"op": "set_cell", "sheet": "Orders", "cell": "A4", "value": "soon"}])
        issue = self.refused(row="date", values=["qty"], groupDates={"date": "month"})
        self.assertIn("row 4 holds 'soon'", issue["message"])
        issue = self.refused(row="region", values=["qty"], groupDates={"date": "month"})
        self.assertIn("must also be named in row or column", issue["message"])


class NumberGroupingTest(PivotFixture):
    def test_numbers_group_into_bins_of_equal_width(self):
        self.pivot(row="amount", values=["qty"], groupNumbers={"amount": {"step": 2000}})
        self.assertEqual(self.grid(), [["amount", "Sum of qty"], ["2000-3999", 4], ["4000-5999", 11], ["6000-7999", 7], ["Grand Total", 22]])
        cache = self.part("xl/pivotCache/pivotCacheDefinition1.xml")
        self.assertIn('<rangePr autoStart="0" startNum="2000" endNum="7000" groupInterval="2000"/>', cache)
        self.assertIn('<groupItems count="5"><s v="&lt;2000"/><s v="2000-3999"/>', cache)
        self.assertEqual(self.reloaded_pivot().cache.cacheFields[5].fieldGroup.rangePr.groupInterval, 2000)
        self.apply([{"op": "set_cell", "sheet": "Orders", "cell": "F2", "value": 12000000}])
        self.pivot(row="amount", values=["qty"], groupNumbers={"amount": {"step": 5000000}}, targetSheet="Wide")
        sheet = load_workbook(self.directory / "book.xlsx")["Wide"]
        self.assertEqual((sheet["A4"].value, sheet["A5"].value), ("0-4999999", "10000000-14999999"))
        self.assertGreaterEqual(sheet.column_dimensions["A"].width, len("10000000-14999999") + 2)

    def test_a_bin_needs_a_number_in_every_row_and_a_positive_step(self):
        self.apply([{"op": "set_cell", "sheet": "Orders", "cell": "F4", "value": "미정"}])
        issue = self.refused(row="amount", values=["qty"], groupNumbers={"amount": {"step": 1000}})
        self.assertIn("row 4 holds '미정'", issue["message"])
        issue = self.refused(row="qty", values=["amount"], groupNumbers={"qty": {"step": 0}})
        self.assertEqual(issue["location"], "ops[0].groupNumbers.qty.step")


class TopFilterTest(PivotFixture):
    def test_only_the_items_with_the_largest_totals_stay_and_the_total_follows_them(self):
        self.pivot(row="region", values=["qty", "amount"], top={"field": "region", "count": 2})
        self.assertEqual(self.grid(), [["region", "Sum of qty", "Sum of amount"], ["Daegu", 7, 7000], ["Seoul", 9, 11000], ["Grand Total", 16, 18000]])
        table = self.part("xl/pivotTables/pivotTable1.xml")
        self.assertIn('<filters count="1"><filter fld="1" type="count" evalOrder="-1" id="1" iMeasureFld="0"><autoFilter ref="A1"><filterColumn colId="0"><top10 val="2" filterVal="2"/>', table)
        self.assertEqual(len(self.reloaded_pivot().filters), 1)
        self.pivot(row="region", values=["qty"], top={"field": "region", "count": 1, "bottom": True}, targetCell="F3")
        sheet = load_workbook(self.directory / "book.xlsx")["Pivot"]
        self.assertEqual([[cell.value for cell in row] for row in sheet["F4:G5"]], [["Busan", 6], ["Grand Total", 6]])

    def test_the_filtered_header_must_be_a_row_or_column(self):
        issue = self.refused(row="region", values=["qty"], top={"field": "channel", "count": 1})
        self.assertEqual(issue["location"], "ops[0].top.field")


class ReportFilterTest(PivotFixture):
    def test_filters_sit_above_the_table_as_page_fields(self):
        self.pivot(row="region", filters=["channel", "product"], values=["amount"])
        sheet = load_workbook(self.directory / "book.xlsx")["Pivot"]
        self.assertEqual([[cell.value for cell in row] for row in sheet["A3:B6"]], [["channel", "(All)"], ["product", "(All)"], [None, None], ["region", "Sum of amount"]])
        table = self.part("xl/pivotTables/pivotTable1.xml")
        self.assertIn('rowPageCount="2" colPageCount="1"', table)
        self.assertIn('<pageFields count="2"><pageField fld="2" hier="-1"/><pageField fld="3" hier="-1"/></pageFields><dataFields', table)
        self.assertIn('<pivotField axis="axisPage" showAll="0"><items count="3"><item x="0"/><item x="1"/><item t="default"/></items></pivotField>', table)
        self.assertEqual(len(self.reloaded_pivot().pageFields), 2)
        self.assertEqual(run_office(["check", "book.xlsx"], self.directory)["status"], "ok")


class PivotRefusalTest(PivotFixture):
    def test_a_formula_names_an_unknown_header_or_a_wrong_function(self):
        issue = self.refused(row="region", values=[{"field": "margin", "formula": "amount-cots"}])
        self.assertEqual(issue["suggestion"], "use 'cost'")
        issue = self.refused(row="region", values=[{"field": "margin", "formula": "amount-cost", "function": "average"}])
        self.assertIn("its function is sum", issue["message"])
        issue = self.refused(row="region", values=[{"field": "amount", "formula": "qty*2"}])
        self.assertIn("needs a new name", issue["message"])
        issue = self.refused(row="region", values=[{"field": "margin", "formula": "amount cost"}])
        self.assertIn("follows a finished formula", issue["message"])

    def test_a_header_takes_one_place(self):
        issue = self.refused(row="region", column="region", values=["qty"])
        self.assertIn("named in row and in column", issue["message"])


class PivotPersistenceTest(PivotFixture):
    def test_a_later_edit_keeps_groups_formulas_and_filters(self):
        self.pivot(row=["date", "region"], filters=["channel"], values=["qty", {"field": "margin", "formula": "amount-cost"}], groupDates={"date": "quarter"})
        envelope = self.apply([{"op": "set_cell", "sheet": "Orders", "cell": "I1", "value": "later"}])
        self.assertEqual(envelope["status"], "ok", envelope)
        cache = self.part("xl/pivotCache/pivotCacheDefinition1.xml")
        self.assertIn('groupBy="quarters"', cache)
        self.assertIn("formula=\"'amount'-'cost'\"", cache)
        self.assertIn("pageField", self.part("xl/pivotTables/pivotTable1.xml"))
        self.pivot(row="amount", values=["qty"], groupNumbers={"amount": {"step": 2000}}, top={"field": "amount", "count": 2}, targetSheet="Bins")
        self.apply([{"op": "set_cell", "sheet": "Orders", "cell": "I2", "value": "later"}])
        self.assertIn('groupInterval="2000"', self.part("xl/pivotCache/pivotCacheDefinition2.xml"))
        self.assertIn('<top10 val="2" filterVal="2"/>', self.part("xl/pivotTables/pivotTable2.xml"))
        rendered = run_office(["render", "book.xlsx", "--sheet", "Pivot"], self.directory)
        self.assertEqual(rendered["status"], "ok", rendered)
        preview = (self.directory / "book-preview" / "preview.html").read_text(encoding="utf-8")
        for text in ("Qtr1 Total", "Sum of margin", "(All)"):
            self.assertIn(text, preview)



class TextValuesTest(PivotFixture):
    def test_a_values_header_holding_numbers_as_text_is_refused_with_the_conversion(self):
        self.apply([{"op": "set_range", "sheet": "Orders", "cell": "E2", "values": [[str(row[4])] for row in ORDERS[1:]]}])
        issue = self.refused(row="region", values=["qty"])
        self.assertEqual(issue["location"], "ops[0].values[0]")
        self.assertIn("'qty' in Orders!E2:E7 holds numbers as text", issue["message"])
        self.assertEqual(issue["fix"], [{"op": "set_range", "sheet": "Orders", "cell": "E2", "values": [[3], [5], [2], [7], [1], [4]]}])
        self.assertEqual(self.apply(issue["fix"])["status"], "ok")
        self.pivot(row="region", values=["qty"])
        self.assertEqual(self.grid()[1], ["Busan", 6])

    def test_a_text_header_is_counted_and_not_summed(self):
        issue = self.refused(row="region", values=["product"])
        self.assertIn('"function": "count"', issue["suggestion"])
        self.pivot(row="region", values=[{"field": "product", "function": "count"}])

    def test_check_reports_a_pivot_whose_value_cells_are_empty(self):
        self.pivot(row="region", values=["amount"])
        self.assertNotIn("PIVOT_VALUES_EMPTY", [issue["code"] for issue in run_office(["check", "book.xlsx"], self.directory)["issues"]])
        self.apply([{"op": "clear_range", "sheet": "Pivot", "range": "B4:B7"}])
        issues = [issue for issue in run_office(["check", "book.xlsx"], self.directory)["issues"] if issue["code"] == "PIVOT_VALUES_EMPTY"]
        self.assertEqual([issue["location"] for issue in issues], ["Pivot!A3:B7"])
        self.assertIn("Orders!A1:G7", issues[0]["message"])


if __name__ == "__main__":
    unittest.main()
