from __future__ import annotations

import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree

from free_deck_fixture import build_pptx, write_free_deck
from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from charts.combo import AXIS_INTERVALS, SECONDARY_AXIS_RATIO, combo_chart_space, lines_need_own_axis, zero_aligned_ranges  # noqa: E402
from deck.deck_kit import kit_number  # noqa: E402


C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
TOLERANCE = 1e-9


def random_group(generator: random.Random) -> list[float]:
    magnitude = 10 ** generator.uniform(-2, 5)
    sign = generator.choice(("positive", "negative", "mixed"))
    low, high = {"positive": (0, 1), "negative": (-1, 0), "mixed": (-1, 1)}[sign]
    return [round(generator.uniform(low, high) * magnitude, 2) for _ in range(generator.randint(1, 8))]


def zero_share(minimum: float, maximum: float) -> float:
    return -minimum / (maximum - minimum)


class ZeroAlignedRangesTest(unittest.TestCase):
    def assert_aligned(self, groups: list[list[float]], ranges: list[tuple[float, float, float]]) -> None:
        for values, (minimum, maximum, step) in zip(groups, ranges):
            self.assertLessEqual(minimum, min(0.0, *values) + TOLERANCE, (groups, ranges))
            self.assertGreaterEqual(maximum, max(0.0, *values) - TOLERANCE, (groups, ranges))
            self.assertAlmostEqual((maximum - minimum) / step, round((maximum - minimum) / step), places=6)
        shares = [zero_share(minimum, maximum) for minimum, maximum, _ in ranges]
        self.assertTrue(all(abs(share - shares[0]) < 1e-6 for share in shares), (groups, ranges))
        intervals = {round((maximum - minimum) / step) for minimum, maximum, step in ranges}
        self.assertEqual(len(intervals), 1, (groups, ranges))

    def test_every_axis_holds_its_values_and_every_zero_sits_at_one_height(self):
        generator = random.Random(20261003)
        for _ in range(2000):
            groups = [random_group(generator) for _ in range(generator.choice((1, 2, 2, 3)))]
            ranges = [(axis.minimum, axis.maximum, axis.step) for axis in zero_aligned_ranges(groups)]
            self.assert_aligned(groups, ranges)

    def test_edge_shapes_keep_the_rule(self):
        for groups in ([[0, 0]], [[-5], [5]], [[-1e-3, -2e-3], [4000, 9000]], [[100, 200], [-3, -1]], [[7], [7]], [[-40, -15, 10, 35], [1.2, 2.8, 4.5, 7.1]]):
            self.assert_aligned(groups, [(axis.minimum, axis.maximum, axis.step) for axis in zero_aligned_ranges(groups)])


class OfficeComboAxesTest(unittest.TestCase):
    def test_a_line_on_its_own_axis_shares_the_columns_zero_in_word_and_powerpoint_charts(self):
        series = [("Revenue", (850.0, 920.0, 1010.0, 1100.0), False), ("Operating margin", (-4.2, -1.1, 2.5, 6.8), True)]
        self.assertTrue(lines_need_own_axis(series))
        axes = combo_chart_space(("FY24", "FY25", "FY26", "FY27"), series, True).findall(f".//{C}valAx")
        limits = [(float(axis.find(f"{C}scaling/{C}min").get("val")), float(axis.find(f"{C}scaling/{C}max").get("val"))) for axis in axes]
        self.assertEqual(len(limits), 2)
        self.assertLessEqual(limits[1][0], -4.2)
        self.assertGreaterEqual(limits[0][1], 1100)
        self.assertAlmostEqual(zero_share(*limits[0]), zero_share(*limits[1]))
        self.assertEqual(axes[1].find(f"{C}delete").get("val"), "0")


class DocumentPreviewAxesTest(unittest.TestCase):
    def preview_look(self, series):
        from doc.model.charts import ChartSpecification, chart_space, read_specification

        class ChartPart:
            blob = ElementTree.tostring(chart_space(ChartSpecification("combo", ("A", "B", "C"), tuple(series))))

        return read_specification(ChartPart()).look(("#4472C4", "#C0504D"))

    def test_the_word_preview_draws_the_axes_the_chart_part_holds(self):
        series = [("Bookings", (1200.0, 1500.0, 1900.0), False), ("Refunds", (-14.0, -9.0, -6.0), True)]
        look = self.preview_look(series)
        self.assertLessEqual(look.secondary_limits[0], -14)
        self.assertAlmostEqual(zero_share(*look.value_limits), zero_share(*look.secondary_limits))

    def test_a_chart_part_without_limits_stays_automatic(self):
        from doc.model.charts import read_specification

        class ChartPart:
            blob = ElementTree.tostring(combo_chart_space(("A", "B"), [("Sales", (5.0, 7.0), False), ("Share", (-0.2, 0.4), True)], False))

        look = read_specification(ChartPart()).look(("#4472C4", "#C0504D"))
        self.assertEqual((look.value_limits, look.secondary_limits), ((None, None), (None, None)))


ONE_UNIT = '<figure data-chart="combo" data-labels="2023, 2024, 2025, 2026" data-series="Revenue: 8.2, 19.5, 36.8, 61; Operating profit: -12.4, -7.1, -1.9, 4.3" data-unit="M"><figcaption>Revenue and operating profit, USD M</figcaption></figure>'
TWO_UNITS = '<figure data-chart="combo" data-labels="FY24, FY25, FY26, FY27" data-series="Revenue: 850, 920, 1010, 1100; Operating margin: -4.2, -1.1, 2.5, 6.8" data-unit="M, %"><figcaption>Revenue USD M, margin %</figcaption></figure>'
NEGATIVE_COLUMNS = '<figure data-chart="combo" data-labels="1분기, 2분기, 3분기, 4분기" data-series="순현금흐름: -40, -15, 10, 35; 누적 고객: 1.2, 2.8, 4.5, 7.1" data-unit="억, 천명"><figcaption>분기별 순현금흐름과 누적 고객</figcaption></figure>'
ONE_UNIT_APART = '<figure data-chart="combo" data-labels="Q1, Q2, Q3" data-series="Bookings: 1200, 1500, 1900; Refunds: -14, -9, -6" data-unit="K"><figcaption>Bookings and refunds, USD K</figcaption></figure>'
CHARTS = (ONE_UNIT, TWO_UNITS, NEGATIVE_COLUMNS, ONE_UNIT_APART)
PLAIN_NEGATIVE_COLUMNS = '<figure data-chart="column" data-labels="Q1, Q2, Q3, Q4" data-values="-40, -15, 10, 35" data-unit="M"><figcaption>Net cash flow, USD M</figcaption></figure>'


def combo_sections() -> list[str]:
    return [f"<h2>Chart {index} reads against its own zero</h2>{chart}" for index, chart in enumerate((*CHARTS, PLAIN_NEGATIVE_COLUMNS), start=1)]


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class DeckComboAxesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = write_free_deck(Path(directory) / "combo", combo_sections())
            cls.envelope = build_pptx(deck_path, "combo")
            layout = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))
            with zipfile.ZipFile(deck_path / "build" / "combo.pptx") as archive:
                names = sorted((name for name in archive.namelist() if name.startswith("ppt/charts/chart") and name.endswith(".xml")), key=lambda name: int(name.removeprefix("ppt/charts/chart").removesuffix(".xml")))
                cls.chart_xml = [ElementTree.fromstring(archive.read(name)) for name in names]
        cls.charts = [chart for slide in layout["slides"] for chart in slide.get("charts", []) if chart["type"] == "combo"]
        cls.chart_xml = cls.chart_xml[: len(cls.charts)]

    def test_every_value_label_stays_inside_its_plot(self):
        codes = {issue["code"] for issue in self.envelope["issues"]}
        self.assertFalse(codes & {"CONTENT_OVERFLOW", "TEXT_OVERLAP", "TINY_TEXT"}, self.envelope["summary"])

    def test_category_names_sit_under_the_plot_rather_than_on_the_zero_line(self):
        for root in self.chart_xml:
            self.assertEqual(root.find(f".//{C}catAx/{C}tickLblPos").get("val"), "low")

    def test_the_kit_and_python_decide_the_same_axes(self):
        self.assertEqual(kit_number("tickIntervals"), AXIS_INTERVALS)
        self.assertEqual(kit_number("separateAxisRatio"), round(1 / SECONDARY_AXIS_RATIO))
        decisions = [chart["secondaryRange"] is not None for chart in self.charts]
        self.assertEqual(decisions, [False, True, True, True])
        same_unit = [chart for chart in self.charts if chart["units"][0] == chart["units"][1]]
        self.assertEqual([chart["secondaryRange"] is not None for chart in same_unit], [lines_need_own_axis([(series["name"], tuple(series["values"]), index == len(chart["series"]) - 1) for index, series in enumerate(chart["series"])]) for chart in same_unit])

    def test_every_series_lies_inside_the_axis_it_is_drawn_against(self):
        for chart in self.charts:
            line_range = chart["secondaryRange"] or chart["valueRange"]
            for index, series in enumerate(chart["series"]):
                drawn = line_range if index == len(chart["series"]) - 1 else chart["valueRange"]
                self.assertLessEqual(drawn["minimum"], min(0, *series["values"]), chart)
                self.assertGreaterEqual(drawn["maximum"], max(0, *series["values"]), chart)

    def test_two_axes_put_zero_at_one_height(self):
        for chart in self.charts:
            if chart["secondaryRange"] is None:
                continue
            primary, secondary = chart["valueRange"], chart["secondaryRange"]
            self.assertAlmostEqual(zero_share(primary["minimum"], primary["maximum"]), zero_share(secondary["minimum"], secondary["maximum"]), places=6, msg=chart)

    def test_the_pptx_shows_the_axis_a_line_of_its_own_is_read_against(self):
        for chart, root in zip(self.charts, self.chart_xml):
            value_axes = root.findall(f".//{C}valAx")
            line_axes = [axis.get("val") for axis in root.findall(f".//{C}lineChart/{C}axId")]
            if chart["secondaryRange"] is None:
                self.assertEqual(len(value_axes), 1)
                self.assertEqual(line_axes, [axis.get("val") for axis in root.findall(f".//{C}barChart/{C}axId")])
                continue
            secondary = value_axes[1]
            self.assertEqual(secondary.find(f"{C}delete").get("val"), "0")
            self.assertAlmostEqual(float(secondary.find(f"{C}scaling/{C}min").get("val")), chart["secondaryRange"]["minimum"])
            self.assertAlmostEqual(float(secondary.find(f"{C}scaling/{C}max").get("val")), chart["secondaryRange"]["maximum"])


if __name__ == "__main__":
    unittest.main()
