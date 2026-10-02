import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from deck.deck_kit import kit_length, slide_size  # noqa: E402


LEGIBLE_SHARE_OF_WIDTH = 0.013
CARD_TEXT_SPAN_MINIMUM = 0.6
CARD_HEIGHT_SHARE_MAXIMUM = 0.6
ROW_HEIGHT_PER_FONT_SIZE_MAXIMUM = 3.5
COVER_SECTION = """<section data-layout="cover">
  <p class="eyebrow">주식회사 예시랩 2026년 3분기 실적 보고</p>
  <h1>분기 매출 <em>41.3억 원</em>, 목표 40억을 돌파했습니다</h1>
  <p class="lead">클라우드 중심의 매출 성장과 수익률 개선을 보고합니다.</p>
  <p class="meta">발표 박예시 본부장 · 2026년 10월 1일</p>
</section>
"""
BALANCED_DECK = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>주식회사 예시랩 2026년 3분기 실적 보고</title></head>
<body data-theme="corporate">
""" + COVER_SECTION + """<section data-layout="kpi">
  <h2>매출, 수익성, 신규 고객이 함께 늘었습니다</h2>
  <div class="kpi">
    <p class="value">41.3억</p>
    <p class="label">3분기 매출</p>
    <p class="up">목표 40억 대비 +3.3%</p>
  </div>
  <div class="kpi">
    <p class="value">23곳</p>
    <p class="label">신규 고객사</p>
    <p class="up">2분기 14곳 대비 +9곳</p>
  </div>
</section>
<section data-layout="table">
  <h2>2분기 대비 매출, 수익률, 신규 고객이 모두 올랐습니다</h2>
  <table>
    <tr><th>지표</th><th>2분기</th><th>3분기</th><th>변화</th></tr>
    <tr class="pick"><td>매출</td><td>36.2억 원</td><td>41.3억 원</td><td>+5.1억 원 (+14.1%)</td></tr>
    <tr><td>영업이익률</td><td>8.2%</td><td>11.5%</td><td>+3.3%p</td></tr>
    <tr><td>신규 고객사</td><td>14곳</td><td>23곳</td><td>+9곳</td></tr>
  </table>
</section>
<section data-layout="cards">
  <h2>공공 수주와 신제품 출시가 3분기 주요 성과입니다</h2>
  <div class="card">
    <p class="label">공공 수주</p>
    <h3>공공기관 2곳 수주</h3>
    <p>합계 6.2억 원</p>
  </div>
  <div class="card">
    <p class="label">신제품</p>
    <h3>예시 Flow 출시</h3>
    <p>9월 2일 출시</p>
  </div>
  <div class="card">
    <p class="label">고객 기반</p>
    <h3>고객사 순증 +20곳</h3>
    <p>신규 23곳, 이탈 3곳</p>
  </div>
</section>
</body>
</html>
"""
COVER_DECK = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>표지</title></head><body data-theme="corporate">
""" + COVER_SECTION + "</body></html>"
HOLLOW_BOX_DECK = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>빈 상자</title>
<style>
body { margin: 0; font-family: sans-serif; }
section { width: 1600px; height: 900px; box-sizing: border-box; padding: 80px; background: #fff; }
h2 { margin: 0 0 40px; font-size: 54px; }
.panel { height: 640px; box-sizing: border-box; padding: 40px; background: #eef2f7; font-size: 28px; }
.caption { font-size: 17px; }
</style></head><body>
<section><h2>상자 안이 거의 비었습니다</h2><div class="panel">한 줄만 들어 있습니다 <span class="caption">작은 주석</span></div></section>
</body></html>"""

INDENTED_DECK = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>들여쓰기</title>
<style>
body { margin: 0; font-family: sans-serif; }
section { width: 1600px; height: 900px; box-sizing: border-box; padding: 80px; background: #fff; }
.box { display: flex; flex-direction: column; font-size: 24px; }
.box > p:first-child { font-size: 40px; }
.box > p + p { font-size: 30px; }
</style></head><body>
<section>
  <div class="box">
    <p>첫째줄</p>
    <p>둘째줄</p>
  </div>
</section>
</body></html>"""


def build(directory: Path, source: str, output_format: str) -> dict:
    (directory / "slides.html").write_text(source, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", f"build/{Path(directory).name}.{output_format}", "slides.html"], capture_output=True, text=True, cwd=directory)
    return json.loads(completed.stdout)


def drawn_sizes(pdf_path: Path, text: str, page_index: int) -> list[float]:
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_index]
        pixels_per_point = slide_size()[0] / page.width
        footer_top = slide_size()[1] - kit_length("footer-height")
        words = page.extract_words(extra_attrs=["size"])
        return [word["size"] * pixels_per_point for word in words if text in word["text"] and word["bottom"] * pixels_per_point < footer_top]


def cell_text(block: dict) -> str:
    return "".join(run["text"] for paragraph in block["paragraphs"] for run in paragraph["runs"]).strip()


def inside(block: dict, box: dict) -> bool:
    middle = (block["box"]["left"] + block["box"]["right"]) / 2, (block["box"]["top"] + block["box"]["bottom"]) / 2
    return box["left"] <= middle[0] <= box["right"] and box["top"] <= middle[1] <= box["bottom"]


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class IndentedMarkupTest(unittest.TestCase):
    def test_indentation_between_flex_items_does_not_change_which_selectors_match(self):
        with tempfile.TemporaryDirectory() as directory:
            build(Path(directory), INDENTED_DECK, "pdf")
            pdf_path = Path(directory) / "build" / f"{Path(directory).name}.pdf"
            self.assertAlmostEqual(drawn_sizes(pdf_path, "첫째줄", 0)[0], 40, delta=0.5)
            self.assertAlmostEqual(drawn_sizes(pdf_path, "둘째줄", 0)[0], 30, delta=0.5)



@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class CoverTitleTest(unittest.TestCase):
    def test_a_number_stays_with_its_unit_and_the_cover_title_breaks_after_its_clause(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory) / "cover"
            deck_path.mkdir()
            build(deck_path, COVER_DECK, "pptx")
            layout = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))
        title = next(block for block in layout["slides"][0]["blocks"] if "41.3" in "".join(run["text"] for paragraph in block["paragraphs"] for run in paragraph["runs"]))
        lines = [line["text"] for paragraph in title["paragraphs"] for line in paragraph["lines"]]
        self.assertTrue(lines[0].endswith("41.3억 원,"), lines)
        self.assertFalse(any(line.startswith("원") for line in lines), lines)


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class BalancedKitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.deck_path = Path(cls.directory.name) / "balance"
        cls.deck_path.mkdir()
        build(cls.deck_path, BALANCED_DECK, "pptx")
        cls.layout = json.loads((cls.deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))
        cls.envelope = build(cls.deck_path, BALANCED_DECK, "pdf")

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_the_deck_is_acceptable(self):
        self.assertTrue(self.envelope["details"]["acceptance"]["acceptable"], self.envelope["summary"])

    def test_each_card_holds_its_text_from_top_to_bottom_and_leaves_the_slide_room(self):
        slide = self.layout["slides"][3]
        cards = [shape["box"] for shape in slide["shapes"] if shape["geometry"] == "roundRect"]
        self.assertEqual(len(cards), 3)
        for card in cards:
            blocks = [block["box"] for block in slide["blocks"] if inside(block, card)]
            span = max(block["bottom"] for block in blocks) - min(block["top"] for block in blocks)
            height = card["bottom"] - card["top"]
            self.assertGreaterEqual(span / height, CARD_TEXT_SPAN_MINIMUM, (card, blocks))
            self.assertLessEqual(height / slide_size()[1], CARD_HEIGHT_SHARE_MAXIMUM, card)

    def test_labels_and_table_headers_draw_at_the_smallest_type_step_and_that_step_is_legible(self):
        smallest = kit_length("size-small")
        self.assertGreaterEqual(smallest / slide_size()[0], LEGIBLE_SHARE_OF_WIDTH)
        pdf_path = self.deck_path / "build" / "balance.pdf"
        for text, page_index in (("3분기", 1), ("지표", 2)):
            sizes = drawn_sizes(pdf_path, text, page_index)
            self.assertTrue(sizes, text)
            self.assertGreaterEqual(min(sizes), smallest - 0.5, text)

    def test_a_short_table_gives_its_spare_height_to_type_rather_than_to_its_rows(self):
        slide = self.layout["slides"][2]
        table = slide["tables"][0]
        cell_sizes = [run["sizePx"] for block in slide["blocks"] if inside(block, table["box"]) and "매출" == block["paragraphs"][0]["runs"][0]["text"] for run in block["paragraphs"][0]["runs"]]
        self.assertTrue(cell_sizes)
        self.assertGreater(min(cell_sizes), kit_length("size-body"))
        for row in table["rows"][1:]:
            self.assertLessEqual(row["heightPx"] / min(cell_sizes), ROW_HEIGHT_PER_FONT_SIZE_MAXIMUM, table["rows"])


    def test_every_number_in_a_column_lines_up_on_the_right_whatever_unit_it_carries(self):
        slide = self.layout["slides"][2]
        table = slide["tables"][0]
        for column in (("36.2억 원", "8.2%", "14곳"), ("41.3억 원", "11.5%", "23곳"), ("+5.1억 원 (+14.1%)", "+3.3%p", "+9곳")):
            alignments = [block["paragraphs"][0]["alignment"] for block in slide["blocks"] if inside(block, table["box"]) and cell_text(block) in column]
            self.assertEqual(len(alignments), len(column), column)
            self.assertEqual(set(alignments), {"r"}, (column, alignments))

@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class HollowBoxTest(unittest.TestCase):
    def test_a_tall_box_around_one_line_is_a_dead_zone_and_text_under_the_kit_floor_is_tiny(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = build(Path(directory), HOLLOW_BOX_DECK, "pdf")
        messages = {issue["code"]: issue["message"] for issue in envelope["issues"] if issue["location"] == "slide 1"}
        self.assertIn("mostly empty inside", messages.get("VERTICAL_DEAD_ZONE", ""), messages)
        self.assertIn("div.panel", messages["VERTICAL_DEAD_ZONE"])
        self.assertIn("17px", messages.get("TINY_TEXT", ""), messages)
        self.assertEqual({defect["code"] for defect in envelope["details"]["acceptance"]["defects"]}, {"VERTICAL_DEAD_ZONE", "TINY_TEXT"})


if __name__ == "__main__":
    unittest.main()
