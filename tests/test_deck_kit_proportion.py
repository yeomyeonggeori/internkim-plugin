import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from deck.deck_kit import kit_length, slide_size  # noqa: E402
from deck.layout_thresholds import MARK_BREADTH_MINIMUM  # noqa: E402


KIT_SCRIPT = (SCRIPTS_PATH.parent / "assets" / "deck-kit" / "deck-kit.js").read_text(encoding="utf-8")
LEGIBLE_CONTRAST = 3
POSITION_TOLERANCE = 48
EDGE_TOLERANCE = 4
FRAME_WIDTH = slide_size()[0] - 2 * kit_length("margin-x")
ROUND_STEP_MULTIPLES = (1, 2, 5, 10)
TICK_INTERVALS_MAXIMUM = 4
PROPORTION_DECK = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>비율 표본</title></head>
<body data-theme="swiss">
<section data-layout="cover"><h1>차트가 담은 데이터만큼 자리를 씁니다</h1><p class="meta">이샘플 · 2026년 10월</p></section>
<section data-layout="chart"><h2>영업이익률이 8.2%에서 11.5%로 올랐습니다</h2>
  <figure data-chart="column" data-labels="2분기, 3분기" data-values="8.2, 11.5" data-unit="%" data-highlight="3분기"><figcaption>영업이익률, 단위 %</figcaption></figure>
  <div class="insight"><p class="value">+3.3%p</p><p>2분기 대비 영업이익률 개선</p></div></section>
<section data-layout="chart"><h2>클라우드가 매출의 52%를 차지했습니다</h2>
  <figure data-chart="donut" data-labels="클라우드, 온프레미스, 컨설팅" data-values="52, 31, 17" data-unit="%"><figcaption>제품별 매출 비중, 단위 %</figcaption></figure>
  <p class="takeaway">온프레미스 31%, 컨설팅 17%가 뒤를 이었습니다.</p></section>
<section data-layout="kpi"><h2>출시 전 지표가 모두 목표를 넘었습니다</h2>
  <div class="kpi"><p class="value">4.2만</p><p class="label">사전 관심 등록</p><p class="up">목표 3만 명 대비 +40%</p></div>
  <div class="kpi"><p class="value">31%</p><p class="label">체험단 구매 전환</p><p class="up">업계 평균 22% 대비 +9%p</p></div>
  <div class="kpi"><p class="value">3.9만 원</p><p class="label">희망 가격 중앙값</p><p>설문 1,200명 기준</p></div>
  <div class="kpi"><p class="value">68%</p><p class="label">재구매 의향</p><p class="up">기존 제품 52% 대비 +16%p</p></div></section>
<section data-layout="chart"><h2>직군마다 원하는 근무 형태가 다릅니다</h2>
  <figure data-chart="stacked100" data-labels="개발, 영업, 운영, 디자인" data-series="혼합: 58, 41, 39, 55; 사무실: 14, 44, 46, 18; 원격: 28, 15, 15, 27" data-unit="%"><figcaption>직군별 선호 근무 형태, 단위 %</figcaption></figure></section>
<section data-layout="chart"><h2>원격 비율이 높은 팀도 생산성이 떨어지지 않았습니다</h2>
  <figure data-chart="scatter" data-labels="A팀, B팀, C팀, D팀, E팀, F팀" data-series="원격 근무 비율: 20, 35, 40, 50, 60, 80; 생산성 지수: 101, 106, 109, 112, 113, 111" data-unit="%, "><figcaption>팀별 원격 근무 비율과 생산성 지수</figcaption></figure></section>
<section data-layout="table"><h2>용량별로 세 가지 가격을 둡니다</h2>
  <table><thead><tr><th>용량</th><th>가격</th><th>원가율</th></tr></thead>
  <tbody><tr><td>350ml</td><td>3.2만 원</td><td>34%</td></tr><tr class="pick"><td>500ml</td><td>3.9만 원</td><td>31%</td></tr><tr><td>1,000ml</td><td>5.6만 원</td><td>29%</td></tr></tbody></table></section>
<section data-layout="closing"><h2>세 가지를 결정해 주십시오</h2><ol><li>예산 승인</li><li>일정 확정</li><li>담당 지정</li></ol></section>
</body>
</html>
"""
SPARSE_CHART_DECK = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>빈 차트</title>
<style>
body { margin: 0; font-family: sans-serif; }
section { width: 1600px; height: 900px; box-sizing: border-box; padding: 80px; background: #fff; }
h2 { margin: 0 0 40px; font-size: 54px; }
figure { margin: 0; width: 1200px; }
.kit-chart { position: relative; width: 1200px; height: 520px; }
.kit-plot-area { position: relative; width: 1200px; height: 520px; }
.kit-bar { position: absolute; bottom: 0; width: 6%; background: #1a56db; }
.kit-donut-ring { width: 300px; height: 300px; border-radius: 50%; background: #1a56db; }
</style></head><body>
<section><h2>막대가 너무 가늘어 비어 보입니다</h2><figure><div class="kit-chart" data-native-chart><div class="kit-plot-area"><div class="kit-bar" style="left: 20%; height: 60%"></div><div class="kit-bar" style="left: 70%; height: 90%"></div></div></div></figure></section>
<section><h2>원이 자리보다 훨씬 작습니다</h2><figure><div class="kit-chart" data-native-chart><div class="kit-donut-ring"></div></div></figure></section>
</body></html>"""


def build(deck_path: Path, source: str) -> dict:
    deck_path.mkdir()
    (deck_path / "slides.html").write_text(source, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build", "--format", "pptx"], capture_output=True, text=True, cwd=deck_path)
    return json.loads(completed.stdout)


def block_text(block: dict) -> str:
    return "".join("".join(run["text"] for paragraph in block["paragraphs"] for run in paragraph["runs"]).split())


def contains(outer: dict, inner: dict) -> bool:
    return outer["left"] <= inner["left"] and outer["top"] <= inner["top"] and outer["right"] >= inner["right"] and outer["bottom"] >= inner["bottom"]


def channels(color: str) -> list[float]:
    return [float(channel) for channel in re.findall(r"[\d.]+", color)[:3]]


def relative_luminance(color: str) -> float:
    linear = [share / 12.92 if share <= 0.03928 else ((share + 0.055) / 1.055) ** 2.4 for share in (channel / 255 for channel in channels(color))]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def is_round_step(step: float) -> bool:
    magnitude = 10 ** math.floor(math.log10(step))
    return any(math.isclose(step, multiple * magnitude) for multiple in ROUND_STEP_MULTIPLES)


def round_ticks(minimum: float, maximum: float) -> bool:
    span = maximum - minimum
    steps = [span / intervals for intervals in range(1, TICK_INTERVALS_MAXIMUM + 1)]
    return any(is_round_step(step) and math.isclose(minimum / step, round(minimum / step), abs_tol=1e-9) for step in steps)


def kit_share(name: str) -> float:
    return float(re.search(rf"const {name} = ([\d.]+);", KIT_SCRIPT).group(1))


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class ProportionedChartTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        deck_path = Path(cls.directory.name) / "proportion"
        cls.envelope = build(deck_path, PROPORTION_DECK)
        cls.layout = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def issues(self, code: str) -> list[dict]:
        return [issue for issue in self.envelope["issues"] if issue["code"] == code]

    def block(self, slide_index: int, text: str) -> dict:
        wanted = "".join(text.split())
        blocks = [block for block in self.layout["slides"][slide_index]["blocks"] if block_text(block) == wanted]
        self.assertTrue(blocks, text)
        return blocks[0]

    def block_box(self, slide_index: int, text: str) -> dict:
        return self.block(slide_index, text)["box"]

    def test_no_chart_leaves_most_of_its_room_empty(self):
        self.assertEqual(self.issues("CHART_UNDERFILLED"), [])
        self.assertTrue(self.envelope["details"]["acceptance"]["acceptable"], self.envelope["summary"])

    def test_two_bars_fill_their_bands_and_give_the_freed_width_to_the_insight(self):
        chart = self.layout["slides"][1]["charts"][0]
        widest_gap = round((1 - MARK_BREADTH_MINIMUM) / MARK_BREADTH_MINIMUM * 100)
        self.assertLessEqual(chart["gapWidth"], widest_gap, chart["gapWidth"])
        insight = self.block_box(1, "+3.3%p")
        width = chart["box"]["right"] - chart["box"]["left"]
        self.assertGreater(insight["left"], chart["box"]["right"], (insight, chart["box"]))
        self.assertLess(width, FRAME_WIDTH * 0.6, chart["box"])
        self.assertGreaterEqual(width, FRAME_WIDTH * 0.45, chart["box"])

    def test_a_donut_takes_the_body_height_with_its_legend_and_takeaway_beside_it(self):
        ring = self.layout["slides"][2]["charts"][0]["box"]
        legend = max((block["box"] for block in self.layout["slides"][2]["blocks"] if block_text(block) == "클라우드"), key=lambda box: box["left"])
        takeaway = self.block_box(2, "온프레미스 31%, 컨설팅 17%가 뒤를 이었습니다.")
        self.assertGreater(takeaway["left"], ring["right"], (takeaway, ring))
        self.assertGreaterEqual(ring["bottom"] - ring["top"], 0.8 * (takeaway["bottom"] - legend["top"]), (ring, legend, takeaway))

    def test_no_part_beside_a_chart_leaves_an_empty_region(self):
        self.assertEqual(self.issues("EMPTY_REGION"), [])

    def test_an_insight_beside_a_column_chart_is_centred_on_the_chart(self):
        chart = self.layout["slides"][1]["charts"][0]["box"]
        value = self.block_box(1, "+3.3%p")
        card = next(shape["box"] for shape in self.layout["slides"][1]["shapes"] if "fill" in shape and contains(shape["box"], value))
        above = card["top"] - chart["top"]
        below = chart["bottom"] - card["bottom"]
        self.assertGreater(above, 0, (card, chart))
        self.assertLessEqual(abs(above - below), EDGE_TOLERANCE, (card, chart))

    def test_the_parts_beside_a_donut_are_centred_on_its_ring(self):
        ring = self.layout["slides"][2]["charts"][0]["box"]
        legend = max((block["box"] for block in self.layout["slides"][2]["blocks"] if block_text(block) == "클라우드"), key=lambda box: box["left"])
        takeaway = self.block_box(2, "온프레미스 31%, 컨설팅 17%가 뒤를 이었습니다.")
        group_middle = (legend["top"] + takeaway["bottom"]) / 2
        ring_middle = (ring["top"] + ring["bottom"]) / 2
        self.assertLessEqual(abs(group_middle - ring_middle), POSITION_TOLERANCE / 2, (legend, takeaway, ring))

    def test_short_metric_cards_are_not_stretched_hollow(self):
        self.assertEqual([issue for issue in self.issues("VERTICAL_DEAD_ZONE") if issue["location"] == "slide 4"], [])

    def test_every_label_inside_a_segment_contrasts_with_its_fill(self):
        chart = self.layout["slides"][4]["charts"][0]
        for label in chart["pointLabels"]:
            fill = chart["colors"]["points"][label["series"]][label["point"]]
            self.assertGreaterEqual(contrast(label["text"]["color"], fill), LEGIBLE_CONTRAST, (label, fill))

    def test_a_table_stub_column_shares_one_start_edge_in_every_row(self):
        stubs = [self.block(6, text) for text in ("용량", "350ml", "500ml", "1,000ml")]
        self.assertEqual({stub["paragraphs"][0]["alignment"] for stub in stubs}, {"l"})
        starts = [stub["box"]["left"] + stub["insets"]["left"] for stub in stubs]
        self.assertLessEqual(max(starts) - min(starts), 1, starts)

    def test_scatter_axes_end_on_round_steps(self):
        chart = self.layout["slides"][5]["charts"][0]
        for axis in ("valueRange", "secondaryRange"):
            limits = chart[axis]
            self.assertTrue(round_ticks(limits["minimum"], limits["maximum"]), (axis, limits))


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class UnderfilledChartTest(unittest.TestCase):
    def test_thin_bars_and_a_small_ring_are_underfilled_charts(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = build(Path(directory) / "sparse", SPARSE_CHART_DECK)
        messages = {issue["location"]: issue["message"] for issue in envelope["issues"] if issue["code"] == "CHART_UNDERFILLED"}
        self.assertIn("its bars cover 12%", messages.get("slide 1", ""), envelope["issues"])
        self.assertIn("its ring spans 25%", messages.get("slide 2", ""), envelope["issues"])
        self.assertIn("CHART_UNDERFILLED", {defect["code"] for defect in envelope["details"]["acceptance"]["defects"]})


class BandFillConformanceTest(unittest.TestCase):
    def test_the_kit_fills_every_band_beyond_the_underfilled_minimum(self):
        self.assertGreaterEqual(kit_share("barBandFill"), MARK_BREADTH_MINIMUM)
        self.assertGreaterEqual(kit_share("clusterBandFill") * (1 - kit_share("clusterGapShare")), MARK_BREADTH_MINIMUM)


if __name__ == "__main__":
    unittest.main()
