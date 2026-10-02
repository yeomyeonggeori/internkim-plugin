import sys
import unittest
from pathlib import Path

from test_deck_pptx_editing import KoreanDeckFixture, codes


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from charts.look import ChartLook  # noqa: E402
from charts.svg import ChartModel, ChartSeries, chart_svg  # noqa: E402
from powerpoint.preview.chart_look import chart_model  # noqa: E402
from powerpoint.description import chart_details  # noqa: E402


C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
BOX = {"slide": 5, "x": "1in", "y": "1in", "w": "6in", "h": "4in"}
QUARTERS = ["1분기", "2분기", "3분기"]


class ChartFormattingTest(KoreanDeckFixture):
    def add(self, **chart):
        envelope = self.apply([{"op": "add_chart", **BOX, **chart}])
        self.assertEqual([issue["code"] for issue in envelope["issues"] if issue["code"] != "TEXT_OVERLAP"], [], envelope)
        return self.presentation().slides[4].shapes[-1].chart

    def test_series_take_their_colors_labels_and_axis_titles(self):
        chart = self.add(type="column", categories=QUARTERS, series=[{"name": "매출", "values": [96, 110, 128]}, {"name": "비용", "values": [80, 84, 79]}], colors=["1F4E79", "C00000"], dataLabels="value", xTitle="분기", yTitle="억 원")
        space = chart._chartSpace
        fills = [series.find(f"{C}spPr/{A}solidFill/{A}srgbClr").get("val") for series in space.iter(f"{C}ser")]
        self.assertEqual(fills, ["1F4E79", "C00000"])
        labels = space.find(f".//{C}barChart/{C}dLbls")
        self.assertEqual([labels.find(f"{C}{flag}").get("val") for flag in ("showVal", "showCatName", "showPercent")], ["1", "0", "0"])
        self.assertEqual(chart_model(chart, chart_details(chart)).axis_titles, ("분기", "억 원"))

    def test_a_doughnut_colors_each_slice_and_labels_its_share(self):
        chart = self.add(type="doughnut", categories=["직판", "파트너"], series=[{"name": "비중", "values": [60, 40]}], colors=["1A73E8", "34A853"], dataLabels="category_percent")
        points = chart._chartSpace.findall(f".//{C}dPt")
        self.assertEqual([point.find(f".//{A}srgbClr").get("val") for point in points], ["1A73E8", "34A853"])
        labels = chart._chartSpace.find(f".//{C}dLbls")
        self.assertEqual([labels.find(f"{C}{flag}").get("val") for flag in ("showVal", "showCatName", "showPercent")], ["0", "1", "1"])

    def test_a_combo_draws_the_marked_series_as_a_line(self):
        chart = self.add(type="combo", categories=QUARTERS, series=[{"name": "매출", "values": [96, 110, 128]}, {"name": "이익률", "values": [0.17, 0.24, 0.38], "line": True}], yTitle="억 원")
        plot_area = chart._chartSpace.find(f"{C}chart/{C}plotArea")
        self.assertEqual([len(plot_area.findall(f"{C}{tag}/{C}ser")) for tag in ("barChart", "lineChart")], [1, 1])
        self.assertEqual(len(plot_area.findall(f"{C}valAx")), 2)
        self.assertEqual(chart_model(chart, chart_details(chart)).axis_titles, ("", "억 원"))

    def test_a_scatter_places_points_by_the_numbers_in_categories(self):
        chart = self.add(type="scatter", categories=[1, 2, 4], series=[{"name": "A", "values": [3, 5, 4]}, {"name": "B", "values": [2, 2.5, 6]}], colors=["7030A0", "00B050"], xTitle="광고비", yTitle="매출")
        details = chart_details(chart)
        self.assertEqual(details["series"][1]["x"], [1.0, 2.0, 4.0])
        markers = [series.find(f"{C}marker/{C}spPr/{A}solidFill/{A}srgbClr").get("val") for series in chart._chartSpace.iter(f"{C}ser")]
        self.assertEqual(markers, ["7030A0", "00B050"])
        self.assertEqual(chart_model(chart, details).axis_titles, ("광고비", "매출"))

    def test_options_a_chart_cannot_draw_are_refused(self):
        series = [{"name": "매출", "values": [96, 110, 128]}]
        cases = [
            ({"type": "column", "dataLabels": "percent"}, "OPERATION_NOT_APPLICABLE"),
            ({"type": "pie", "xTitle": "분기"}, "OPERATION_NOT_APPLICABLE"),
            ({"type": "column", "series": [{**series[0], "line": True}]}, "INVALID_VALUE"),
            ({"type": "combo"}, "INVALID_VALUE"),
            ({"type": "scatter"}, "INVALID_VALUE"),
        ]
        for options, code in cases:
            with self.subTest(options=options):
                envelope = self.apply([{"op": "add_chart", **BOX, "categories": QUARTERS, "series": series, **options}])
                self.assertEqual(codes(envelope), [code])


class AxisTitleDrawingTest(unittest.TestCase):
    def test_titles_are_drawn_below_and_turned_beside_the_plot(self):
        model = ChartModel(("1분기", "2분기"), (ChartSeries("매출", (1.0, 2.0), "column"),), axis_titles=("분기", "억 원"))
        svg = chart_svg(model, 400, 300, ChartLook(series_colors=("#1F4E79",), slice_colors=("#1F4E79",)), "Pretendard")
        self.assertIn(">분기</text>", svg)
        self.assertIn('<g transform="rotate(-90', svg)
        self.assertIn(">억 원</text></g>", svg)

    def test_a_pie_has_no_axis_to_title(self):
        model = ChartModel(("가", "나"), (ChartSeries("비중", (1.0, 2.0), "pie"),), axis_titles=("분기", ""))
        svg = chart_svg(model, 400, 300, ChartLook(series_colors=("#1F4E79",), slice_colors=("#1F4E79", "#C00000")), "Pretendard")
        self.assertNotIn("분기", svg)


if __name__ == "__main__":
    unittest.main()
