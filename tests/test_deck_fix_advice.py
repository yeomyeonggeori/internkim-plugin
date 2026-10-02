import json
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

from deck.deck_definitions import OUT_OF_FRAME  # noqa: E402
from deck.geometry_checks import geometry_warnings  # noqa: E402
from deck.pptx_layout_audit import layout_issue  # noqa: E402


CARD_SENTENCE = "품절 3일 전에 알립니다. "
OVERFLOW_CODES = {"CONTENT_OVERFLOW", "OUT_OF_FRAME", "TEXT_OVERLAP", "TEXT_COVERED", "FOOTER_CROSSED", "TINY_TEXT"}


def crowded_deck(row_count: int, sentence_count: int) -> str:
    rows = "".join(f"<tr><td>지역{index}</td><td>{index * 10}억</td><td>{100 + index}%</td></tr>" for index in range(row_count))
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>넘침 확인</title></head><body>
<section data-layout="cover"><h1>넘침을 확인합니다</h1><p class="meta">이샘플</p></section>
<section data-layout="table"><h2>지역별 실적이 고르게 늘었습니다</h2><table><tr><th>지역</th><th>매출</th><th>달성률</th></tr>{rows}</table></section>
<section data-layout="cards"><h2>두 기능으로 재고 업무를 줄입니다</h2>
<div class="card"><p class="label">알림</p><h3>품절 전 알림</h3><p>{CARD_SENTENCE * sentence_count}</p></div>
<div class="card"><p class="label">추천</p><h3>발주 추천</h3><p>적정 수량을 제안합니다.</p></div></section>
<section data-layout="closing"><h2>승인해 주십시오</h2><ol><li>예산 6억 원</li></ol></section>
</body></html>"""


def build(directory: Path, source: str) -> dict:
    (directory / "slides.html").write_text(source, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", f"build/{Path(directory).name}.pdf", "slides.html"], capture_output=True, text=True, cwd=directory)
    return json.loads(completed.stdout)


def suggestions_on(envelope: dict, location: str) -> dict[str, str]:
    return {issue["code"]: issue["suggestion"] for issue in envelope["issues"] if issue["location"] == location}


class MeasuredAdviceTest(unittest.TestCase):
    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_each_overflow_names_how_much_fits_and_following_it_is_acceptable(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory) / "crowded"
            deck_path.mkdir()
            crowded = build(deck_path, crowded_deck(30, 50))
            table_advice = suggestions_on(crowded, "slide 2")
            card_advice = suggestions_on(crowded, "slide 3")
            self.assertTrue(set(table_advice) & OVERFLOW_CODES, crowded["issues"])
            self.assertEqual(len(set(table_advice.values())), 1, table_advice)
            rows_per_slide = int(re.search(r"at most (\d+) rows", next(iter(table_advice.values()))).group(1))
            characters = int(re.search(r"cut it to (\d+) or fewer", next(iter(card_advice.values()))).group(1))
            sentences = (characters - len("알림품절 전 알림")) // len(CARD_SENTENCE)
            followed = build(deck_path, crowded_deck(rows_per_slide, sentences))
        self.assertTrue(followed["details"]["acceptance"]["acceptable"], followed["summary"])


class KitAdviceTest(unittest.TestCase):
    def measured(self, **findings):
        return {"overflow": [], "outOfFrame": [], "overlaps": [], "distortedImages": [], **findings}

    def test_a_covered_text_without_crowding_names_the_box_and_the_style_to_remove(self):
        covered = {"text": {"selector": "p", "text": "매출"}, "box": {"selector": "div.badge", "text": ""}, "ratio": 0.9}
        issue = geometry_warnings(self.measured(coveredText=[covered]), "cards")[0]
        self.assertIn("div.badge is drawn over p \"매출\"", issue.suggestion)
        self.assertIn("style", issue.suggestion)

    def test_a_stretched_photo_is_moved_to_a_layout_that_crops_it(self):
        image = {"selector": "img", "text": "", "renderedRatio": 2.0, "naturalRatio": 1.5}
        issue = geometry_warnings(self.measured(distortedImages=[image]), "cards")[0]
        self.assertIn("into a cover or image slide", issue.suggestion)

    def test_a_crowded_list_names_how_many_items_fit(self):
        overflow = {"selector": "ol", "text": "", "scrollWidth": 900, "clientWidth": 900, "scrollHeight": 900, "clientHeight": 600}
        issue = geometry_warnings(self.measured(overflow=[overflow], capacity=[{"part": "list", "index": 1, "items": 9, "fits": 5}]), "closing")[0]
        self.assertIn("shows 5 of its 9 items", issue.suggestion)

    def test_a_pptx_layout_issue_points_at_its_fix_or_says_what_to_do_without_one(self):
        moved = layout_issue(OUT_OF_FRAME, "slide 1 shape 2 lies partly outside the slide", "slide 1 shape 2", {"op": "set_transform", "slide": 1, "shape": 2, "x": 0})
        unplaced = layout_issue(OUT_OF_FRAME, "slide 1 shape 2 lies partly outside the slide", "slide 1 shape 2", None)
        self.assertIn("set_transform in fix", moved.suggestion)
        self.assertEqual(moved.fix, ({"op": "set_transform", "slide": 1, "shape": 2, "x": 0},))
        self.assertEqual((unplaced.suggestion, unplaced.fix), (OUT_OF_FRAME.kind.suggestion, ()))

    def test_the_guide_names_kit_actions_for_layout_defects(self):
        guide = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", "create", "slides"], capture_output=True, text=True, check=True).stdout
        fix_of = {code: fix for code, fix in re.findall(r"^\s+([A-Z_]+) \(\w+\): .*?Fix: (.*)$", guide, re.MULTILINE)}
        self.assertIn("cover or image slide", fix_of["IMAGE_DISTORTED"])
        self.assertIn("how many rows, items or characters fit", fix_of["CONTENT_OVERFLOW"])
        self.assertIn("split or cut", fix_of["OUT_OF_FRAME"])
        self.assertIn("remove the style attribute", fix_of["STYLE_NOT_DRAWN"])
        self.assertIn("names the cause", fix_of["TEXT_COVERED"])


if __name__ == "__main__":
    unittest.main()
