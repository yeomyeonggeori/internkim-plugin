import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from core.host_contract import RUNTIME_CONTEXT_VARIABLE  # noqa: E402
THEMES = ("editorial", "corporate", "midnight", "swiss")


def deck(theme: str, *slides: str) -> str:
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>시험 덱</title></head><body data-theme="{theme}">' + "".join(slides) + "</body></html>"


COVER = '<section data-layout="cover"><h1>물류 자동화로 출고 시간을 줄입니다</h1><p class="lead">주식회사 예시랩 · 2026년 3분기</p><aside class="notes">표지</aside></section>'
CLOSING = '<section data-layout="closing"><h2>세 가지를 오늘 승인해 주십시오</h2><ol><li>예산 6억원</li><li>협력사 두 곳 계약</li><li>11월 착공</li></ol><aside class="notes">마무리</aside></section>'

CLOSING_WITH_CARDS = (
    '<section data-layout="closing"><p class="eyebrow">투자 유치</p><h2>시리즈 B 120억원을 세 곳에 씁니다</h2>'
    '<div class="card" data-icon="lightbulb"><p class="value">45%</p><h3>연구개발</h3><p>제품 개발에 씁니다.</p></div>'
    '<div class="card" data-icon="megaphone"><p class="value">35%</p><h3>영업</h3><p>고객을 늘립니다.</p></div>'
    '<aside class="notes">마무리</aside></section>'
)


def cards(style: str = "", card_style: str = "") -> str:
    card_attribute = f' style="{card_style}"' if card_style else ""
    paragraph_attribute = f' style="{style}"' if style else ""
    return (
        '<section data-layout="cards"><h2>세 기능이 재고 업무를 줄입니다</h2>'
        '<div class="card"><h3>품절 알림</h3><p>재고가 줄면 담당자에게 바로 알립니다.</p></div>'
        f'<div class="card"{card_attribute}><h3>발주 추천</h3><p{paragraph_attribute}>판매 추세로 발주량을 제안합니다.</p></div>'
        '<div class="card"><h3>매출 정산</h3><p>매장별 매출을 매일 맞춥니다.</p></div>'
        '<aside class="notes">세 기능</aside></section>'
    )


def comparison_with_pick() -> str:
    return (
        '<section data-layout="comparison"><h2>새 플랫폼이 운영비를 낮춥니다</h2>'
        '<div class="column"><p class="label">현재</p><h3>자체 서버</h3><ul><li>월 3억원</li><li>수동 배포</li></ul></div>'
        '<div class="column pick"><p class="label">제안</p><h3>새 플랫폼</h3><ul><li>월 2억원</li><li>자동 배포</li></ul></div>'
        '<aside class="notes">비교</aside></section>'
    )


def combo_with_line_inside_columns() -> str:
    return (
        '<section data-layout="chart"><h2>영업이익은 3분기에 흑자로 돌아섰습니다</h2>'
        '<figure data-chart="combo" data-labels="1Q, 2Q, 3Q, 4Q" data-series="매출: 300, 320, 310, 290; 영업이익: -40, -10, 30, 80" data-unit="억">'
        "<figcaption>분기 매출과 영업이익, 단위 억원 · 자료: 재무팀</figcaption></figure>"
        '<aside class="notes">추이</aside></section>'
    )


def table(title_style: str = "") -> str:
    attribute = f' style="{title_style}"' if title_style else ""
    return (
        f'<section data-layout="table"><h2{attribute}>지역별 매출은 서울이 가장 큽니다</h2>'
        "<table><thead><tr><th>지역</th><th>매출</th></tr></thead><tbody><tr><td>서울</td><td>120</td></tr><tr><td>부산</td><td>80</td></tr></tbody></table>"
        '<p class="source">자료: 영업팀</p><aside class="notes">표</aside></section>'
    )


def timeline() -> str:
    steps = "".join(f'<div class="step"><p class="label">{month}</p><h3>{name}</h3><p>{text}</p></div>' for month, name, text in (("10월", "설계", "현장 조사를 마칩니다."), ("11월", "착공", "설비를 들입니다."), ("12월", "가동", "출고를 시작합니다.")))
    return f'<section data-layout="timeline"><h2>석 달 안에 새 센터를 가동합니다</h2>{steps}<aside class="notes">일정</aside></section>'


def number_with_two_points() -> str:
    return (
        '<section data-layout="number"><h2>스마트공장 시장은 2027년 4.6조원으로 커집니다</h2>'
        '<p class="value">4.6조원</p><p class="label">2027년 시장 전망</p>'
        "<p>2024년 3.1조원에서 연평균 14%씩 성장합니다.</p><p>타깃은 중소 제조기업 약 6만 3천 곳입니다.</p>"
        '<aside class="notes">시장</aside></section>'
    )


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class VisualConsistencyTest(unittest.TestCase):
    def build(self, source: str) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "slides.html").write_text(source, encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "build/deck.pdf", "slides.html"], capture_output=True, text=True, cwd=directory)
        return json.loads(completed.stdout)

    def located(self, envelope: dict, code: str) -> set[str]:
        return {issue["location"] for issue in envelope["issues"] if issue["code"] == code}

    def test_text_too_faint_for_its_background_is_a_defect_on_its_slide(self):
        envelope = self.build(deck("editorial", COVER, cards(style="color:#E4E0D6"), CLOSING))
        self.assertEqual(self.located(envelope, "TEXT_LOW_CONTRAST"), {"slide 2"})
        defects = {(defect["code"], defect["location"]) for defect in envelope["details"]["acceptance"]["defects"]}
        self.assertIn(("TEXT_LOW_CONTRAST", "slide 2"), defects)

    def test_every_theme_draws_its_own_parts_above_the_contrast_floor(self):
        for theme in THEMES:
            with self.subTest(theme=theme):
                envelope = self.build(deck(theme, COVER, comparison_with_pick(), combo_with_line_inside_columns(), table(), timeline(), CLOSING_WITH_CARDS))
                self.assertEqual(self.located(envelope, "TEXT_LOW_CONTRAST"), set(), [issue["message"] for issue in envelope["issues"] if issue["code"] == "TEXT_LOW_CONTRAST"])

    def test_a_card_pushed_out_of_its_row_is_misaligned_and_an_even_row_is_not(self):
        pushed = self.build(deck("corporate", COVER, cards(card_style="margin-top:64px"), CLOSING))
        even = self.build(deck("corporate", COVER, cards(), timeline(), CLOSING))
        self.assertEqual(self.located(pushed, "GRID_MISALIGNED"), {"slide 2"})
        self.assertEqual(self.located(even, "GRID_MISALIGNED"), set())

    def test_a_title_restyled_on_one_slide_breaks_from_the_rest_of_the_deck(self):
        restyled = self.build(deck("swiss", COVER, cards(), table(title_style="font-weight:400;text-align:center"), timeline(), CLOSING))
        uniform = self.build(deck("swiss", COVER, cards(), table(), timeline(), comparison_with_pick(), CLOSING))
        self.assertEqual(self.located(restyled, "TITLE_STYLE_INCONSISTENT"), {"slide 3"})
        self.assertEqual(self.located(uniform, "TITLE_STYLE_INCONSISTENT"), set())

    def test_a_number_with_two_supporting_points_stacks_them_apart(self):
        envelope = self.build(deck("corporate", COVER, number_with_two_points(), CLOSING))
        self.assertEqual(self.located(envelope, "TEXT_OVERLAP"), set(), envelope["summary"])

    def build_pptx(self, directory: str, reviews_deck_renders: bool | None) -> dict:
        (Path(directory) / "slides.html").write_text(deck("midnight", COVER, cards(), CLOSING_WITH_CARDS), encoding="utf-8")
        environment = {name: value for name, value in os.environ.items() if name != RUNTIME_CONTEXT_VARIABLE}
        if reviews_deck_renders is not None:
            context_path = Path(directory) / "office-runtime-context.json"
            context_path.write_text(json.dumps({"requester": {"name": "이샘플", "email": "sample@example.com"}, "today": "2026-10-04", "company": {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": reviews_deck_renders}), encoding="utf-8")
            environment[RUNTIME_CONTEXT_VARIABLE] = str(context_path)
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "build/deck.pptx", "slides.html"], capture_output=True, text=True, cwd=directory, env=environment)
        return json.loads(completed.stdout)

    def test_a_build_for_a_host_that_does_not_review_renders_writes_no_visual_review(self):
        for reviews_deck_renders in (None, False):
            with tempfile.TemporaryDirectory() as directory:
                envelope = self.build_pptx(directory, reviews_deck_renders)
                snapshot = json.loads((Path(directory) / "build" / "deck.pptx.source.json").read_text(encoding="utf-8"))
                written = (Path(directory) / "build" / "review" / "visual-review.json").exists()
            self.assertEqual(envelope["status"], "ok", envelope["summary"])
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
        self.assertTrue(0 < review["threshold"] < 1)
        second = review["slides"][1]
        self.assertEqual((second["number"], second["state"]["layout"], second["state"]["theme"]["name"]), (2, "cards", "midnight"))
        self.assertEqual(second["state"]["deck"], "시험 덱")
        self.assertTrue(second["section"].startswith('<section data-layout="cards">'))
        self.assertEqual(review["slides"][2]["state"]["background"], "--feature-bg with --feature-ink text")
        self.assertEqual([icon["icon"] for icon in review["slides"][2]["state"]["icons"]], ["lightbulb", "megaphone"])
        self.assertIn("Layouts", review["fixer"]["kitGuide"])

    def test_an_off_palette_color_is_reported_on_the_slide_that_uses_it(self):
        envelope = self.build(deck("corporate", COVER, cards(), table(title_style="color:#D81B60"), CLOSING))
        self.assertEqual(self.located(envelope, "OFF_PALETTE_COLOR"), {"slide 3"})


if __name__ == "__main__":
    unittest.main()
