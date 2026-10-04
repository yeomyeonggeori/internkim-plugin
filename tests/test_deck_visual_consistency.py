import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from design_gate_fixture import decided_context, design_markdown
from design_gate_slides import fill_sections
from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from core.host_contract import RUNTIME_CONTEXT_VARIABLE  # noqa: E402


STYLE = """
figure[data-chart] { width: 1400px; height: 560px; margin: 0; }
section { padding: var(--margin); box-sizing: border-box; display: flex; flex-direction: column; gap: var(--gap); font-family: var(--font-body); }
h1, h2 { font-family: var(--font-display); font-size: var(--size-title); margin: 0; font-weight: 700; }
h3 { font-size: 30px; margin: 0; }
p { margin: 0; }
.cards { display: flex; gap: 24px; align-items: flex-start; }
.card { padding: 28px; background: var(--surface); border-radius: var(--radius); }
figure { width: 900px; height: 420px; margin: 0; }
"""
def dark_ground() -> str:
    from deck.deck_design import palette_candidates, resolve_design

    return palette_candidates(resolve_design({"choices": {"mood": {"option": "bold"}}}))[0]["colors"]["ground"]


DARK_TOKENS = {"mood": "bold"}


def deck(*slides: str) -> str:
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>시험 덱</title><style>{STYLE}</style></head><body>' + fill_sections("".join(slides)) + "</body></html>"


COVER = '<section><h1>물류 자동화로 출고 시간을 줄입니다</h1><p>주식회사 예시랩 · 2026년 3분기</p><aside class="notes">표지</aside></section>'
CLOSING = '<section><h2>세 가지를 오늘 승인해 주십시오</h2><ol><li>예산 6억원</li><li>협력사 두 곳 계약</li><li>11월 착공</li></ol><aside class="notes">마무리</aside></section>'
ICON_SLIDE = '<section><h2>두 가지 기능을 먼저 만듭니다</h2><p><i data-icon="lightbulb"></i> 연구개발</p><p><i data-icon="megaphone"></i> 영업</p><aside class="notes">기능</aside></section>'


def cards(paragraph_style: str = "", card_style: str = "") -> str:
    paragraph_attribute = f' style="{paragraph_style}"' if paragraph_style else ""
    pushed = f"; {card_style}" if card_style else ""
    return (
        '<section><h2>세 기능이 재고 업무를 줄입니다</h2><div class="cards">'
        '<div class="card" style="flex: 3"><h3>품절 알림</h3><p>재고가 줄면 담당자에게 바로 알립니다.</p></div>'
        f'<div class="card" style="flex: 2{pushed}"><h3>발주 추천</h3><p{paragraph_attribute}>판매 추세로 발주량을 제안합니다.</p></div>'
        '<div class="card" style="flex: 2"><h3>매출 정산</h3><p>매장별 매출을 매일 맞춥니다.</p></div>'
        '</div><aside class="notes">세 기능</aside></section>'
    )


def chart_slide() -> str:
    return (
        '<section><h2>영업이익은 3분기에 흑자로 돌아섰습니다</h2>'
        '<figure data-chart="combo" data-labels="1Q, 2Q, 3Q, 4Q" data-series="매출: 300, 320, 310, 290; 영업이익: -40, -10, 30, 80" data-unit="억">'
        "<figcaption>분기 매출과 영업이익, 단위 억원 · 자료: 재무팀</figcaption></figure><aside class=\"notes\">추이</aside></section>"
    )


def table(title_style: str = "") -> str:
    attribute = f' style="{title_style}"' if title_style else ""
    return (
        f"<section><h2{attribute}>지역별 매출은 서울이 가장 큽니다</h2>"
        "<table><thead><tr><th>지역</th><th>매출</th></tr></thead><tbody><tr><td>서울</td><td>120</td></tr><tr><td>부산</td><td>80</td></tr></tbody></table>"
        '<p>자료: 영업팀</p><aside class="notes">표</aside></section>'
    )


def steps() -> str:
    items = "".join(f"<li><b>{month}</b> {name}: {text}</li>" for month, name, text in (("10월", "설계", "현장 조사를 마칩니다."), ("11월", "착공", "설비를 들입니다."), ("12월", "가동", "출고를 시작합니다.")))
    return f'<section><h2>석 달 안에 새 센터를 가동합니다</h2><ol>{items}</ol><aside class="notes">일정</aside></section>'


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class VisualConsistencyTest(unittest.TestCase):
    def build(self, source: str, overrides: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "slides.html").write_text(source, encoding="utf-8")
            (Path(directory) / "DESIGN.md").write_text(design_markdown(), encoding="utf-8")
            environment = {name: value for name, value in os.environ.items() if name != RUNTIME_CONTEXT_VARIABLE}
            if overrides:
                environment[RUNTIME_CONTEXT_VARIABLE] = str(decided_context(Path(directory), **overrides))
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "build/deck.pdf", "slides.html"], capture_output=True, text=True, cwd=directory, env=environment)
        return json.loads(completed.stdout)

    def located(self, envelope: dict, code: str) -> set[str]:
        return {issue["location"] for issue in envelope["issues"] if issue["code"] == code}

    def test_text_too_faint_for_its_background_is_a_defect_on_its_slide(self):
        envelope = self.build(deck(COVER, cards(paragraph_style="color:#E4E0D6"), CLOSING))
        self.assertEqual(self.located(envelope, "TEXT_LOW_CONTRAST"), {"slide 2"})
        defects = {(defect["code"], defect["location"]) for defect in envelope["details"]["acceptance"]["defects"]}
        self.assertIn(("TEXT_LOW_CONTRAST", "slide 2"), defects)

    def test_a_light_and_a_dark_design_draw_their_chart_and_table_above_the_contrast_floor(self):
        for overrides in (None, DARK_TOKENS):
            with self.subTest(dark=bool(overrides)):
                envelope = self.build(deck(COVER, chart_slide(), table(), steps(), CLOSING), overrides)
                self.assertEqual(self.located(envelope, "TEXT_LOW_CONTRAST"), set(), [issue["message"] for issue in envelope["issues"] if issue["code"] == "TEXT_LOW_CONTRAST"])

    def test_a_card_pushed_out_of_its_row_is_misaligned_and_an_even_row_is_not(self):
        pushed = self.build(deck(COVER, cards(card_style="margin-top:64px"), CLOSING))
        even = self.build(deck(COVER, cards(), steps(), CLOSING))
        self.assertEqual(self.located(pushed, "GRID_MISALIGNED"), {"slide 2"})
        self.assertEqual(self.located(even, "GRID_MISALIGNED"), set())

    def test_a_title_restyled_on_one_slide_breaks_from_the_rest_of_the_deck(self):
        restyled = self.build(deck(COVER, cards(), table(title_style="font-weight:400;text-align:center"), steps(), chart_slide(), CLOSING))
        uniform = self.build(deck(COVER, cards(), table(), steps(), chart_slide(), CLOSING))
        self.assertEqual(self.located(restyled, "TITLE_STYLE_INCONSISTENT"), {"slide 3"})
        self.assertEqual(self.located(uniform, "TITLE_STYLE_INCONSISTENT"), set())

    def build_pptx(self, directory: str, reviews_deck_renders: bool | None) -> dict:
        (Path(directory) / "slides.html").write_text(deck(COVER, cards(), ICON_SLIDE), encoding="utf-8")
        (Path(directory) / "DESIGN.md").write_text(design_markdown(), encoding="utf-8")
        environment = {name: value for name, value in os.environ.items() if name != RUNTIME_CONTEXT_VARIABLE}
        if reviews_deck_renders is not None:
            context_path = Path(directory) / "office-runtime-context.json"
            context_path.write_text(json.dumps({"requester": {"name": "이샘플", "email": "sample@example.com"}, "today": "2026-10-04", "company": {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": reviews_deck_renders, "deckDesign": {"choices": {"mood": {"option": "bold"}}}}), encoding="utf-8")
            environment[RUNTIME_CONTEXT_VARIABLE] = str(context_path)
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "build/deck.pptx", "slides.html"], capture_output=True, text=True, cwd=directory, env=environment)
        return json.loads(completed.stdout)

    def test_a_build_for_a_host_that_does_not_review_renders_writes_no_visual_review(self):
        for reviews_deck_renders in (None, False):
            with tempfile.TemporaryDirectory() as directory:
                envelope = self.build_pptx(directory, reviews_deck_renders)
                snapshot = json.loads((Path(directory) / "build" / "deck.pptx.source.json").read_text(encoding="utf-8"))
                written = (Path(directory) / "build" / "review" / "visual-review.json").exists()
            self.assertIn(envelope["status"], ("ok", "warning"), envelope["summary"])
            self.assertNotIn("visualReview", envelope["details"])
            self.assertNotIn("visualReview", snapshot)
            self.assertFalse(written)

    def test_a_build_writes_the_visual_review_each_slide_render_is_asked_with(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = self.build_pptx(directory, True)
            review = json.loads(Path(envelope["details"]["visualReview"]).read_text(encoding="utf-8"))
            snapshot = json.loads((Path(directory) / "build" / "deck.pptx.source.json").read_text(encoding="utf-8"))
            images_exist = [Path(slide["image"]).is_file() for slide in review["slides"]]
        self.assertEqual(snapshot["visualReview"], envelope["details"]["visualReview"])
        self.assertEqual([slide["slide"] for slide in snapshot["slides"]], [1, 2, 3])
        self.assertEqual(images_exist, [True, True, True])
        self.assertIn(review["question"]["cleanOption"], review["question"]["options"])
        self.assertIn(review["deck"]["cleanOption"], review["deck"]["options"])
        self.assertTrue(0 < review["threshold"] < 1)
        second = review["slides"][1]
        self.assertEqual(second["number"], 2)
        self.assertEqual(second["state"]["deck"], "시험 덱")
        self.assertEqual(second["state"]["design"]["colors"]["ground"], dark_ground())
        self.assertTrue(second["section"].startswith("<section>"))
        self.assertEqual([icon["icon"] for icon in review["slides"][2]["state"]["icons"]], ["lightbulb", "megaphone"])
        self.assertIn("Canvas", review["fixer"]["kitGuide"])

    def test_an_off_palette_color_is_reported_on_the_slide_that_uses_it(self):
        envelope = self.build(deck(COVER, cards(), table(title_style="color:#D81B60"), CLOSING))
        self.assertEqual(self.located(envelope, "OFF_PALETTE_COLOR"), {"slide 3"})


if __name__ == "__main__":
    unittest.main()
