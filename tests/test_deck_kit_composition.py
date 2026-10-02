import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
ALIGNMENT_TOLERANCE = 2
COMPOSED_DECK = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>주식회사 예시랩 2026년 3분기 실적 보고</title></head>
<body data-theme="corporate">
<section data-layout="cover">
  <h1>3분기 매출 <em>41.3억 원</em>, 분기 목표를 3% 넘겼습니다</h1>
  <p class="meta">발표자: 박예시 본부장 · 2026년 10월</p>
</section>
<section data-layout="kpi">
  <h2>매출·수익성·고객 모두 2분기보다 나아졌습니다</h2>
  <div class="kpi"><p class="value">41.3억</p><p class="label">3분기 매출, 목표 40억 원 대비 103% 달성</p><p class="up">2분기 36.2억 원 대비 +5.1억 원</p></div>
  <div class="kpi"><p class="value">11.5%</p><p class="label">영업이익률</p><p class="up">2분기 8.2% 대비 +3.3%p</p></div>
  <div class="kpi"><p class="value">23곳</p><p class="label">신규 고객사</p><p class="up">2분기 14곳 대비 +9곳</p></div>
  <div class="kpi"><p class="value">15.8억</p><p class="label">9월 매출, 분기 중 최대</p><p class="up">7월 12.4억 → 8월 13.1억 → 9월 15.8억 원</p></div>
  <p class="takeaway">이탈 고객사 3곳을 제외한 순 고객 증가는 20곳입니다</p>
</section>
<section data-layout="closing">
  <h2>4분기에는 매출 48억 원을 목표로 합니다</h2>
  <ol><li>개발자 5명 채용</li><li>11월 일본 시장 파일럿</li></ol>
</section>
</body>
</html>
"""
KPI_FOOTERS = ("2분기 36.2억 원 대비 +5.1억 원", "2분기 8.2% 대비 +3.3%p", "2분기 14곳 대비 +9곳", "7월 12.4억 → 8월 13.1억 → 9월 15.8억 원")
KPI_LABELS = ("3분기 매출, 목표 40억 원 대비 103% 달성", "영업이익률", "신규 고객사", "9월 매출, 분기 중 최대")


def block_text(block: dict) -> str:
    return "".join("".join(run["text"] for paragraph in block["paragraphs"] for run in paragraph["runs"]).split())


def build(deck_path: Path, source: str) -> dict:
    deck_path.mkdir()
    (deck_path / "slides.html").write_text(source, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build", "--format", "pptx"], capture_output=True, text=True, cwd=deck_path)
    return json.loads(completed.stdout)


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class ComposedDeckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        deck_path = Path(cls.directory.name) / "composed"
        cls.envelope = build(deck_path, COMPOSED_DECK)
        layers = deck_path / "build" / "review" / "pptx-layers" / "layout.json"
        cls.layout = json.loads(layers.read_text(encoding="utf-8")) if layers.exists() else None

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        if self.envelope["details"]["review"]["renderSource"] != "layout":
            self.skipTest("the renderer could not run on this host")

    def block_tops(self, slide_index: int, texts: tuple[str, ...]) -> list[float]:
        blocks = {block_text(block): block["box"]["top"] for block in self.layout["slides"][slide_index]["blocks"]}
        wanted = ["".join(text.split()) for text in texts]
        self.assertLessEqual(set(wanted), set(blocks), sorted(blocks))
        return [blocks[text] for text in wanted]

    def issue_messages(self, code: str, slide: int) -> list[str]:
        return [issue["message"] for issue in self.envelope["issues"] if issue["code"] == code and issue["location"] == f"slide {slide}"]

    def test_every_kpi_in_a_row_starts_its_label_and_its_change_line_on_the_same_line(self):
        for texts in (KPI_LABELS, KPI_FOOTERS):
            tops = self.block_tops(1, texts)
            self.assertLessEqual(max(tops) - min(tops), ALIGNMENT_TOLERANCE, dict(zip(texts, tops)))

    def test_a_kpi_label_that_wraps_past_two_lines_is_reported_with_its_line_count(self):
        messages = self.issue_messages("LABEL_TOO_LONG", 2)
        self.assertEqual(len(messages), 1, self.envelope["issues"])
        self.assertIn("3분기 매출, 목표", messages[0])
        self.assertIn("wraps to 3 lines", messages[0])


if __name__ == "__main__":
    unittest.main()
