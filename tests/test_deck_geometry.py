import json
from pathlib import Path
import tempfile
import unittest

from png_fixture import write_png
from render_fixture import can_render
from staged_deck_fixture import build_deck, check_deck, write_staged_deck

from deck.review.deck_review import review_deck  # noqa: E402


FIXTURE_SOURCE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>Fixture</title></head><body>
<section><h2>이 슬라이드는 깔끔하게 들어갑니다</h2><p>짧은 본문입니다.</p><aside class="notes">노트 하나</aside></section>
<section><h2>이 슬라이드는 그림이 늘어났습니다</h2><img src="photo.png"><aside class="notes">노트 둘</aside></section>
</body></html>
"""
MEASURED_SLIDES = [
    {"index": 1, "height": 900, "distortedImages": []},
    {"index": 2, "height": 900, "distortedImages": [{"selector": "img", "text": "", "renderedRatio": 4.0, "naturalRatio": 1.0}]},
]
CLIPPED = (
    "<h2>이 슬라이드는 상자가 넘칩니다</h2>"
    '<div style="width: 400px; height: 60px; overflow: hidden; font-size: 28px">길고 긴 문장이 상자 높이를 넘도록 계속 이어집니다 길고 긴 문장이 상자 높이를 넘도록 계속 이어집니다 길고 긴 문장이 상자 높이를 넘도록 계속 이어집니다</div>'
)
CARDS_STYLE = ".cards { display: flex; gap: 24px; height: 420px; } .card { flex: 1; overflow: hidden; background: var(--surface); padding: 24px; }"


def cards_page(sentence_count: int) -> str:
    paragraph = "매장 운영 시간을 줄이고 발주 정확도를 높입니다. " * sentence_count
    cards = "".join(f'<div class="card" style="flex: {weight}"><h3>{title}</h3><p>{paragraph}</p></div>' for weight, title in ((3, "품절 알림"), (2, "발주 추천"), (1, "매출 정산")))
    return f'<h2>세 기능이 재고 업무를 줄입니다</h2><div class="cards">{cards}</div>'


class GeometryReviewTest(unittest.TestCase):
    def test_measured_findings_are_reported_on_their_own_slide_only(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            (deck_path / "slides.html").write_text(FIXTURE_SOURCE, encoding="utf-8")
            review_path = deck_path / "review"
            review_path.mkdir()
            for number in (1, 2):
                write_png(review_path / f"deck.{number:03d}.png", 32, 18, [[(255, 255, 255, 255)] * 32 for _ in range(18)])
            (review_path / "geometry.json").write_text(json.dumps({"viewport": {"width": 1600, "height": 900}, "slides": MEASURED_SLIDES}), encoding="utf-8")
            result = review_deck(deck_path / "slides.html", "deck", review_path)
        located = {(issue.kind.code, issue.location) for issue in result.issues}
        self.assertIn(("IMAGE_DISTORTED", "slide 2"), located)
        self.assertNotIn(("IMAGE_DISTORTED", "slide 1"), located)


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class RenderedGeometryTest(unittest.TestCase):
    def test_the_gate_refuses_an_overflowing_box_and_leaves_a_clean_page_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = check_deck(write_staged_deck(Path(directory), ["<h2>이 슬라이드는 깔끔하게 들어갑니다</h2><p>짧은 본문입니다.</p>", CLIPPED]))
        located = {issue["location"] for issue in envelope["issues"] if issue["code"] == "CONTENT_OVERFLOW"}
        self.assertEqual(located, {"page 2"})

    def test_cards_whose_text_spills_past_their_box_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = build_deck(write_staged_deck(Path(directory), [cards_page(30)], CARDS_STYLE), extension="pdf")
        self.assertEqual(envelope["status"], "error")
        self.assertIn(("CONTENT_OVERFLOW", "page 1"), {(issue["code"], issue["location"]) for issue in envelope["issues"]})

    def test_cards_whose_text_fits_are_acceptable(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = build_deck(write_staged_deck(Path(directory), [cards_page(2)], CARDS_STYLE), extension="pdf")
        self.assertNotIn("CONTENT_OVERFLOW", {issue["code"] for issue in envelope["issues"]}, envelope["summary"])


if __name__ == "__main__":
    unittest.main()
