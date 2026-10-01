import re
import unittest
import zipfile

from openpyxl import load_workbook

from sheet_fixture import WorkbookFixture, run_office

MONTHS = [["month", "sales", "margin"], ["Jan", 120, 0.21], ["Feb", 150, 0.24], ["Mar", 90, 0.18], ["Apr", 170, 0.27]]


class RenderedPagesTest(WorkbookFixture):
    def render(self):
        envelope = run_office(["sheet", "render", "book.xlsx"], self.directory)
        self.assertNotEqual(envelope["status"], "error", envelope)
        return envelope, (self.directory / "book-preview" / "preview.html").read_text(encoding="utf-8")

    def chart_svgs(self, preview):
        return re.findall(r"<svg.*?</svg>", preview, flags=re.DOTALL)

    def test_a_combo_chart_draws_its_bars_and_its_line_on_a_second_axis(self):
        self.create_workbook([{"title": "Sales", "rows": MONTHS}])
        self.apply([{"op": "add_chart", "type": "combo", "range": "A1:C5", "anchor": "E2", "title": "Sales and margin"}])
        _, preview = self.render()
        svg = self.chart_svgs(preview)[0]
        self.assertEqual(svg.count("<rect x=") - 1 - 2, 4)
        self.assertEqual(svg.count("<polyline"), 1)
        self.assertIn(">0.5<", svg)
        self.assertIn(">margin<", svg)

    def test_a_pie_is_drawn_in_the_slice_colors_it_was_given(self):
        self.create_workbook([{"title": "Sales", "rows": MONTHS}])
        self.apply([{"op": "add_chart", "type": "pie", "range": "A1:B5", "anchor": "E2", "colors": ["111111", "222222", "333333", "444444"]}])
        _, preview = self.render()
        fills = re.findall(r'fill="(#[0-9a-f]{6})"', self.chart_svgs(preview)[0])
        self.assertEqual([color for color in ("#111111", "#222222", "#333333", "#444444") if color in fills], ["#111111", "#222222", "#333333", "#444444"])
        self.apply([{"op": "add_chart", "type": "bar", "range": "A1:C5", "anchor": "E20", "colors": ["AA0000", "00AA00"]}])
        _, preview = self.render()
        bar_fills = set(re.findall(r'fill="(#[0-9a-f]{6})"', self.chart_svgs(preview)[1]))
        self.assertTrue({"#aa0000", "#00aa00"} <= bar_fills, bar_fills)

    def test_horizontal_stacked_bars_stay_horizontal_and_stacked(self):
        self.create_workbook([{"title": "Sales", "rows": [["team", "won", "lost"], ["North", 4, 2], ["South", 3, 5]]}])
        self.apply([{"op": "add_chart", "type": "bar", "range": "A1:C3", "anchor": "E2", "horizontal": True, "stacked": True}])
        _, preview = self.render()
        bars = re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)" fill="#', self.chart_svgs(preview)[0])
        north_won, north_lost = bars[1], bars[3]
        self.assertEqual(north_won[1], north_lost[1])
        self.assertAlmostEqual(float(north_won[0]) + float(north_won[2]), float(north_lost[0]), delta=0.2)
        self.assertGreater(float(north_won[2]), float(north_won[3]))

    def test_a_chart_across_a_page_break_draws_its_rest_on_the_next_page_and_says_so(self):
        self.create_workbook([{"title": "Sales", "rows": [["day", "sales"]] + [[f"d{index}", index] for index in range(1, 61)]}])
        self.apply([{"op": "add_chart", "type": "line", "range": "A1:B13", "anchor": "D40", "title": "Daily sales", "width": 10}])
        envelope, preview = self.render()
        self.assertNotIn("BLANK_PAGE", [issue["code"] for issue in envelope["issues"]])
        contents = envelope["details"]["pageContents"]
        self.assertEqual([(page["page"], page["sheet"]) for page in contents], [(1, "Sales"), (2, "Sales")])
        self.assertTrue(contents[0]["cells"].startswith("A1:") and contents[1]["cells"].startswith("A"))
        self.assertEqual([page["drawings"] for page in contents], [[{"chart": "Daily sales", "type": "line", "shown": "part, cut at the page edge"}]] * 2)
        self.assertEqual(len(self.chart_svgs(preview)), 2)

    def test_a_long_heading_stays_on_one_line_and_a_merged_title_does_not_grow_its_row(self):
        heading = "판매 실적 원본 데이터 (판매실적_2026.csv · 2026-04~2026-09)"
        self.create_workbook([{"title": "Sales", "heading": heading, "rows": MONTHS}])
        sheet = load_workbook(self.directory / "book.xlsx")["Sales"]
        self.assertFalse(sheet["A1"].alignment.wrap_text)
        self.assertLess(sheet.column_dimensions["A"].width, 20)
        self.apply([{"op": "merge_cells", "range": "A1:C1"}, {"op": "format_range", "range": "A1", "wrapText": True}])
        _, preview = self.render()
        first_row = re.search(r"grid-template-rows:([\d.]+)px", preview).group(1)
        self.assertLess(float(first_row), 30)

    def test_a_page_with_nothing_on_it_is_reported_with_its_number(self):
        self.create_workbook([{"title": "Sales", "rows": MONTHS}])
        self.apply([{"op": "set_cell", "cell": "A200", "value": "note"}])
        envelope, _ = self.render()
        issue = next(issue for issue in envelope["issues"] if issue["code"] == "BLANK_PAGE")
        self.assertIn("3 of 5 printed pages show nothing: page 2 (Sales), page 3 (Sales), page 4 (Sales)", issue["message"])
        self.assertIn("print area", issue["suggestion"])

    def test_a_full_sheet_reports_no_blank_page(self):
        self.create_workbook([{"title": "Sales", "rows": MONTHS}])
        envelope, _ = self.render()
        self.assertNotIn("BLANK_PAGE", [issue["code"] for issue in envelope["issues"]])


SHARES = [["분기", "국내", "해외"], ["1분기", 30, 10], ["2분기", 20, 20], ["3분기", 45, 5]]


class PercentChartTest(WorkbookFixture):
    def chart_xml(self, number):
        with zipfile.ZipFile(self.directory / "book.xlsx") as archive:
            return archive.read(f"xl/charts/chart{number}.xml").decode()

    def test_percent_stacked_columns_and_percent_slices_are_written_and_drawn(self):
        self.create_workbook([{"title": "매출", "rows": SHARES}])
        envelope = self.apply([
            {"op": "add_chart", "type": "bar", "range": "A1:C4", "stacked": "percent", "dataLabels": "value", "anchor": "E2"},
            {"op": "add_chart", "type": "pie", "range": "A1:B4", "dataLabels": "category_percent", "anchor": "E20"},
            {"op": "add_chart", "type": "area", "range": "A1:C4", "stacked": "percent", "anchor": "E38"},
        ])
        self.assertEqual(envelope["status"], "ok", envelope)
        columns = self.chart_xml(1)
        self.assertIn('<grouping val="percentStacked"/>', columns)
        self.assertIn('formatCode="0%"', columns)
        self.assertIn('<showVal val="1"/>', columns)
        self.assertIn('<showCatName val="1"/><showSerName val="0"/><showPercent val="1"/>', self.chart_xml(2))
        self.assertIn('<grouping val="percentStacked"/>', self.chart_xml(3))
        run_office(["sheet", "render", "book.xlsx"], self.directory)
        svgs = re.findall(r"<svg.*?</svg>", (self.directory / "book-preview" / "preview.html").read_text(encoding="utf-8"), flags=re.DOTALL)
        heights = [float(height) for height in re.findall(r'<rect x="[\d.]+" y="[\d.]+" width="[\d.]+" height="([\d.]+)" fill="#', svgs[0])[1:]]
        self.assertAlmostEqual(heights[0] + heights[3], heights[1] + heights[4], delta=0.2)
        self.assertIn(">100%<", svgs[0])
        self.assertIn(">30<", svgs[0])
        self.assertIn(">1분기 32%<", svgs[1])
        self.assertIn(">100%<", svgs[2])

    def test_percent_labels_on_a_chart_without_slices_are_refused(self):
        self.create_workbook([{"title": "매출", "rows": SHARES}])
        issue = self.apply([{"op": "add_chart", "type": "bar", "range": "A1:C4", "dataLabels": "percent"}])["issues"][0]
        self.assertEqual((issue["code"], issue["location"]), ("OPERATION_NOT_APPLICABLE", "ops[0].dataLabels"))
        self.assertIn('"stacked": "percent"', issue["suggestion"])


if __name__ == "__main__":
    unittest.main()
