import json
from pathlib import Path
import tempfile
import unittest

from render_fixture import can_render
from host_fixture import FakeHost
from staged_deck_fixture import PICTURE, build_deck, write_staged_deck
from task_context_fixture import environment_with_context, write_context_at


STYLE = """
figure[data-chart] { width: 1400px; height: 560px; margin: 0; }
.cards { display: flex; gap: 24px; }
.cards > .card { flex: 1; }
table { flex: 1; }
"""
DARK = {"colors": {"text": "#F2F4F7", "surface": "#1E2A3A", "line": "#3A4A5E"}, "backgrounds": {"cover": "#0B1320", "content": "#0B1320", "data": "#0B1320", "closing": "#0B1320"}}

COVER = '<h1>물류 자동화로 출고 시간을 줄입니다</h1><p>주식회사 예시랩 · 2026년 3분기</p>'
CLOSING = '<h2>세 가지를 오늘 승인해 주십시오</h2><ol><li>예산 6억원</li><li>협력사 두 곳 계약</li><li>11월 착공</li></ol>'
ICON_PAGE = '<h2>두 가지 기능을 먼저 만듭니다</h2><p><i data-icon="lightbulb"></i> 연구개발</p><p><i data-icon="megaphone"></i> 영업</p>'


def cards(paragraph_style: str = "") -> str:
    attribute = f' style="{paragraph_style}"' if paragraph_style else ""
    return (
        '<h2>세 기능이 재고 업무를 줄입니다</h2><div class="cards">'
        '<div class="card"><h3>품절 알림</h3><p>재고가 줄면 담당자에게 바로 알립니다.</p></div>'
        f'<div class="card"><h3>발주 추천</h3><p{attribute}>판매 추세로 발주량을 제안합니다.</p></div>'
        '<div class="card"><h3>매출 정산</h3><p>매장별 매출을 매일 맞춥니다.</p></div></div>'
        f'{PICTURE}'
    )


def chart_page() -> str:
    return (
        '<h2>영업이익은 3분기에 흑자로 돌아섰습니다</h2>'
        '<figure data-chart="combo" data-labels="1Q, 2Q, 3Q, 4Q" data-series="매출: 300, 320, 310, 290; 영업이익: -40, -10, 30, 80" data-unit="억">'
        "<figcaption>분기 매출과 영업이익, 단위 억원 · 자료: 재무팀</figcaption></figure>"
    )


def table(title_style: str = "") -> str:
    attribute = f' style="{title_style}"' if title_style else ""
    return (
        f"<h2{attribute}>지역별 매출은 서울이 가장 큽니다</h2>"
        "<table><thead><tr><th>지역</th><th>매출</th></tr></thead><tbody><tr><td>서울</td><td>120</td></tr><tr><td>부산</td><td>80</td></tr></tbody></table>"
        "<p>자료: 영업팀</p>"
    )


def context_environment(directory: Path, has_context: bool) -> dict:
    if not has_context:
        return environment_with_context(None)
    return environment_with_context(write_context_at(directory / "task" / "task-context.json", {"requester": {"name": "이샘플", "email": "sample@example.com"}, "today": "2026-10-04"}))


def clean_answers(body: dict) -> dict:
    claims = body["state"].get("claims") or {}
    choices = {name: "source" if name in claims else "none" for name in body["questions"]}
    return {"answers": {name: {"type": "choice", "choice": choice, "probabilities": {choice: 1.0}} for name, choice in choices.items()}, "modelName": "fake", "usage": {"costUSD": 0.0}}


def located(envelope: dict, code: str) -> set[str]:
    return {issue["location"] for issue in envelope["issues"] if issue["code"] == code}


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class PageContrastTest(unittest.TestCase):
    def build(self, sections: list, design: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            write_staged_deck(Path(directory), sections, STYLE, design)
            return build_deck(Path(directory), extension="pdf", environment=context_environment(Path(directory), False))

    def test_text_too_faint_for_its_background_is_refused_on_its_page(self):
        envelope = self.build([COVER, cards(paragraph_style="color:#EEF5F2"), CLOSING])
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(located(envelope, "TEXT_LOW_CONTRAST"), {"page 2"})

    def test_a_light_and_a_dark_style_sheet_draw_their_chart_and_table_above_the_contrast_floor(self):
        for design in (None, DARK):
            with self.subTest(dark=bool(design)):
                envelope = self.build([COVER, chart_page(), table(), CLOSING], design)
                self.assertEqual(located(envelope, "TEXT_LOW_CONTRAST"), set(), envelope["summary"])

    def test_an_off_palette_color_is_named_on_its_page_without_stopping_the_build(self):
        envelope = self.build([COVER, cards(), table(title_style="color:#D81B60"), CLOSING])
        self.assertEqual(located(envelope, "OFF_PALETTE_COLOR"), {"page 3"})
        self.assertNotEqual(envelope["status"], "error", envelope["summary"])


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class VisualReviewManifestTest(unittest.TestCase):
    def build(self, directory: Path, has_context: bool) -> dict:
        write_staged_deck(directory, [COVER, cards(), ICON_PAGE], STYLE)
        return build_deck(directory, environment=context_environment(directory, has_context))

    def test_a_build_without_a_script_host_writes_no_visual_review(self):
        for has_context in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                envelope = self.build(Path(directory), has_context)
                snapshot = json.loads((Path(directory) / "build" / "deck.pptx.source.json").read_text(encoding="utf-8"))
                written = (Path(directory) / "build" / "review" / "visual-review.json").exists()
            self.assertIn(envelope["status"], ("ok", "warning"), envelope["summary"])
            self.assertNotIn("visualReview", envelope["details"])
            self.assertNotIn("visualReview", snapshot)
            self.assertFalse(written)

    def test_each_slide_of_the_visual_review_names_its_page_file_and_outline_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            with FakeHost(decide=clean_answers):
                envelope = self.build(Path(directory), True)
            snapshot = json.loads((Path(directory) / "build" / "deck.pptx.source.json").read_text(encoding="utf-8"))
            review = json.loads(Path(snapshot["visualReview"]).read_text(encoding="utf-8"))
            images_exist = [Path(slide["image"]).is_file() for slide in review["slides"]]
            second_page = (Path(directory) / "pages" / "02.html").read_text(encoding="utf-8")
            outline = json.loads((Path(directory) / "outline.json").read_text(encoding="utf-8"))
        self.assertEqual(envelope["details"]["visualReview"]["outcome"], "clean", envelope["details"]["visualReview"])
        self.assertEqual(images_exist, [True, True, True])
        self.assertIn(review["question"]["cleanOption"], review["question"]["options"])
        self.assertNotIn("hero_metric_template", review["question"]["options"])
        self.assertTrue(0 < review["threshold"] < 1)
        second = review["slides"][1]
        self.assertEqual(Path(second["source"]).name, "02.html")
        self.assertEqual(second["section"], second_page.strip())
        self.assertEqual(second["state"]["page"]["layout"], outline["pages"][1]["layout"])
        self.assertEqual(second["state"]["page"]["title"], "세 기능이 재고 업무를 줄입니다")
        self.assertEqual(second["state"]["design"]["colors"]["accent"], "#0E7C66")
        self.assertNotIn("edits", second)
        self.assertNotIn("recompose", second)
        self.assertEqual([icon["icon"] for icon in review["slides"][2]["state"]["icons"]], ["lightbulb", "megaphone"])


if __name__ == "__main__":
    unittest.main()
