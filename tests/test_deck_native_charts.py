from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import openpyxl
from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE
from pptx.oxml.ns import qn

from png_fixture import read_png, write_png
from render_fixture import can_render
from test_deck_kit_samples import SAMPLE_DECKS_PATH, copy_sample_deck


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))
sys.path.insert(0, str(SCRIPTS_PATH / "deck"))

from deck_kit import chart_types  # noqa: E402
from editable_pptx import read_text_layers, write_editable_pptx  # noqa: E402
from native_charts import NATIVE_CHART_TYPES  # noqa: E402
from pptx_chart_look import chart_look  # noqa: E402
from pptx_description import chart_details  # noqa: E402
from pptx_inheritance import slide_context  # noqa: E402
from pptx_preview_chart import chart_svg  # noqa: E402


ACCENT = "rgb(26, 86, 219)"
MUTED = "rgb(200, 210, 224)"
SECOND = "rgb(141, 176, 238)"
TEXT = {"fontFamily": "Paperlogy", "fontWeight": 600, "sizePx": 19, "color": "rgb(47, 61, 82)"}
STRONG = {"fontFamily": "Paperlogy", "fontWeight": 700, "sizePx": 21, "color": "rgb(12, 26, 48)"}
EXPECTED_TYPES = {
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "stacked": XL_CHART_TYPE.COLUMN_STACKED,
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "line": XL_CHART_TYPE.LINE_MARKERS,
    "donut": XL_CHART_TYPE.DOUGHNUT,
    "pie": XL_CHART_TYPE.PIE,
}


def chart_layout(kind: str, series: list[dict], **overrides) -> dict:
    labels = ["1분기", "2분기", "3분기"]
    is_round = kind in ("donut", "pie")
    series_colors = [ACCENT, SECOND][: len(series)]
    points = [[ACCENT, SECOND, MUTED]] if is_round else [[color] * len(labels) for color in series_colors]
    layout = {
        "type": kind, "labels": labels, "series": series, "unit": "억", "decimals": 0, "startsAtZero": kind != "line",
        "valueRange": {"minimum": 50, "maximum": 150} if kind == "line" else None, "gapWidth": 100, "center": "42%" if kind == "donut" else "", "centerLabel": "1분기" if kind == "donut" else "",
        "box": {"left": 100, "top": 200, "right": 1100, "bottom": 800},
        "colors": {"series": series_colors, "points": points, "grid": "rgb(213, 221, 232)", "background": "rgb(255, 255, 255)"},
        "text": {"base": TEXT, "category": TEXT, "legend": TEXT, "share": STRONG, "center": STRONG, "centerLabel": TEXT},
        "pointLabels": [] if is_round else [{"series": 0, "point": point, "below": False, "text": STRONG} for point in range(len(labels))],
    }
    return layout | overrides


def write_layers(review_path: Path, charts: list[dict]) -> None:
    layers_path = review_path / "pptx-layers"
    layers_path.mkdir(parents=True)
    slides = [{"width": 1600, "height": 900, "visibleText": "", "pictureTexts": [], "blocks": [], "shapes": [], "boxesKeptAsPicture": 0, "charts": [chart]} for chart in charts]
    (layers_path / "layout.json").write_text(json.dumps({"language": "ko", "slides": slides}), encoding="utf-8")
    for number in range(1, len(charts) + 1):
        write_png(layers_path / f"background.{number:03}.png", 32, 18, [[(255, 255, 255, 255)] * 32 for _ in range(18)])


def chart_frame(slide):
    return next(shape for shape in slide.shapes if shape.has_chart)


class NativeChartPackageTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def write(self, charts: list[dict]):
        write_layers(self.directory / "review", charts)
        written = write_editable_pptx(read_text_layers(self.directory / "review", len(charts)), [""] * len(charts), self.directory / "deck.pptx")
        return written, Presentation(str(self.directory / "deck.pptx"))

    def test_every_kit_chart_type_has_a_native_chart_type(self):
        self.assertEqual(set(chart_types()), set(NATIVE_CHART_TYPES))

    def test_each_kit_chart_becomes_a_native_chart_with_its_categories_and_series(self):
        one = [{"name": "", "values": [96, 104.5, 128]}]
        two = [{"name": "프리미엄", "values": [38, 47, 61]}, {"name": "일반", "values": [52, 50, 49]}]
        charts = [chart_layout(kind, one if kind in ("donut", "pie", "column", "bar") else two) for kind in EXPECTED_TYPES]
        written, presentation = self.write(charts)
        self.assertEqual(written.chart_count, len(EXPECTED_TYPES))
        for slide, layout in zip(presentation.slides, charts):
            chart = chart_frame(slide).chart
            with self.subTest(layout["type"]):
                self.assertEqual(chart.chart_type, EXPECTED_TYPES[layout["type"]])
                self.assertEqual(list(chart.plots[0].categories), layout["labels"])
                self.assertEqual([list(series.values) for series in chart.plots[0].series], [[float(value) for value in series["values"]] for series in layout["series"]])

    def test_the_chart_sits_in_the_box_the_layout_measured(self):
        _, presentation = self.write([chart_layout("column", [{"name": "", "values": [1, 2, 3]}])])
        frame = chart_frame(presentation.slides[0])
        emu_per_pixel = 12192000 / 1600
        self.assertEqual((frame.left, frame.top, frame.width, frame.height), tuple(round(value * emu_per_pixel) for value in (100, 200, 1000, 600)))

    def test_the_embedded_workbook_holds_the_same_data(self):
        _, presentation = self.write([chart_layout("stacked", [{"name": "프리미엄", "values": [38, 47, 61]}, {"name": "일반", "values": [52, 50, 49.5]}])])
        workbook = openpyxl.load_workbook(io.BytesIO(chart_frame(presentation.slides[0]).chart.part.chart_workbook.xlsx_part.blob))
        rows = [list(row) for row in workbook.active.iter_rows(values_only=True)]
        self.assertEqual(rows, [[None, "프리미엄", "일반"], ["1분기", 38, 52], ["2분기", 47, 50], ["3분기", 61, 49.5]])

    def test_series_and_highlight_colors_and_the_kits_labels_are_kept(self):
        highlighted = chart_layout("column", [{"name": "", "values": [96, 104, 128]}], colors={"series": [ACCENT], "points": [[MUTED, MUTED, ACCENT]], "grid": "rgb(213, 221, 232)", "background": "rgb(255, 255, 255)"})
        _, presentation = self.write([highlighted])
        chart = chart_frame(presentation.slides[0]).chart
        series = chart.plots[0].series[0]._element
        self.assertEqual(series.find(f"{qn('c:spPr')}/{qn('a:solidFill')}/{qn('a:srgbClr')}").get("val"), "1A56DB")
        recolored = {int(point.find(qn("c:idx")).get("val")): point.find(f".//{qn('a:srgbClr')}").get("val") for point in series.findall(qn("c:dPt"))}
        self.assertEqual(recolored, {0: "C8D2E0", 1: "C8D2E0"})
        labels = series.findall(f"{qn('c:dLbls')}/{qn('c:dLbl')}")
        self.assertEqual([label.find(qn("c:numFmt")).get("formatCode") for label in labels], ['#,##0"억"'] * 3)
        self.assertEqual({label.find(qn("c:dLblPos")).get("val") for label in labels}, {"outEnd"})
        self.assertFalse(chart.value_axis.visible)

    def test_a_donut_keeps_its_hole_its_slice_colors_and_its_center_text(self):
        _, presentation = self.write([chart_layout("donut", [{"name": "", "values": [42, 30, 28]}])])
        slide = presentation.slides[0]
        chart = chart_frame(slide).chart
        self.assertEqual(chart._chartSpace.find(f".//{qn('c:holeSize')}").get("val"), "60")
        colors = [point.find(f".//{qn('a:solidFill')}/{qn('a:srgbClr')}").get("val") for point in chart.plots[0].series[0]._element.findall(qn("c:dPt"))]
        self.assertEqual(colors, ["1A56DB", "8DB0EE", "C8D2E0"])
        center = next(shape for shape in slide.shapes if shape.has_text_frame)
        self.assertEqual([paragraph.text for paragraph in center.text_frame.paragraphs], ["42%", "1분기"])

    def test_the_preview_draws_the_charts_own_colors_and_only_its_labels(self):
        highlighted = chart_layout("column", [{"name": "", "values": [96, 104, 128]}], colors={"series": [ACCENT], "points": [[MUTED, MUTED, ACCENT]], "grid": "rgb(213, 221, 232)", "background": "rgb(255, 255, 255)"})
        highlighted["pointLabels"] = [{"series": 0, "point": 2, "below": False, "text": STRONG}]
        _, presentation = self.write([highlighted])
        slide = presentation.slides[0]
        chart = chart_frame(slide).chart
        svg = chart_svg(chart_details(chart), 600, 400, chart_look(chart, slide_context(presentation, slide)), "Paperlogy")
        self.assertEqual((svg.count('fill="#1A56DB"'), svg.count('fill="#C8D2E0"')), (1, 2))
        self.assertIn(">128억<", svg)
        self.assertNotIn(">96억<", svg)
        self.assertEqual(svg.count("<line"), 1, "the category axis is drawn and the hidden value axis leaves no gridlines")

    def test_the_chart_fonts_are_embedded(self):
        written, _ = self.write([chart_layout("bar", [{"name": "", "values": [1, 2, 3]}])])
        self.assertEqual(written.embedded_typefaces, ("Paperlogy 6 SemiBold", "Paperlogy 7 Bold"))


class BuiltNativeChartTest(unittest.TestCase):
    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_a_built_deck_carries_native_charts_read_back_and_previewed(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = copy_sample_deck(SAMPLE_DECKS_PATH / "product-proposal", Path(directory))
            built = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build", "--format", "pptx"], capture_output=True, text=True, cwd=deck_path).stdout)
            pptx_path = Path(built["details"]["outputs"]["pptx"])
            read = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "read", str(pptx_path)], capture_output=True, text=True).stdout)
            checked = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "check", str(pptx_path)], capture_output=True, text=True, cwd=deck_path).stdout)
            layout = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))
            backgrounds = {number: read_png(deck_path / "build" / "review" / "pptx-layers" / f"background.{number:03}.png") for number, slide in enumerate(layout["slides"], start=1) if slide.get("charts")}
            preview = (deck_path / checked["details"]["preview"]).read_text(encoding="utf-8")
        self.assertEqual(built["details"]["pptx"]["charts"], 3)
        charts = [shape["chart"] for slide in read["details"]["slides"] for shape in slide["shapes"] if shape["kind"] == "chart"]
        self.assertEqual([chart["type"] for chart in charts], ["bar_clustered", "line_markers", "doughnut"])
        self.assertEqual(charts[0]["categories"], ["재고 확인", "발주 작성", "매출 정산", "직원 일정", "세금 서류"])
        self.assertEqual(charts[1]["series"][1]["name"], "비교 매장")
        self.assert_chart_left_the_background(layout, backgrounds)
        self.assertNotIn("PPTX_NOT_RENDERED", {issue["code"] for issue in checked["issues"]})
        self.assertIn("svg", preview)

    def assert_chart_left_the_background(self, layout: dict, backgrounds: dict) -> None:
        for number, background in backgrounds.items():
            chart = layout["slides"][number - 1]["charts"][0]
            box = chart["box"]
            scale = background["width"] / layout["slides"][number - 1]["width"]
            columns = range(round(box["left"] * scale), round(box["right"] * scale), 7)
            rows = range(round(box["top"] * scale), round(box["bottom"] * scale), 7)
            colors = {background["rows"][row][column][:3] for row in rows for column in columns}
            self.assertEqual(len(colors), 1, f"slide {number} still draws its chart in the background")


if __name__ == "__main__":
    unittest.main()
