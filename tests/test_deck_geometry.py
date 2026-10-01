import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "deck"
OFFICE_ENTRY = SCRIPTS_PATH.parent / "office"
sys.path.insert(0, str(SCRIPTS_PATH.parent))
sys.path.insert(0, str(SCRIPTS_PATH))

from png_fixture import write_png  # noqa: E402
from render_fixture import can_render  # noqa: E402
from render_review import build_review_report  # noqa: E402


LONG_SLIDE_TEXT = "아주 긴 문장이 이어집니다. " * 120
FIXTURE_SOURCE = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>Fixture</title>
<style>
body {{ margin: 0; font-family: sans-serif; }}
section {{ width: 1600px; height: 900px; position: relative; overflow: hidden; box-sizing: border-box; padding: 80px; }}
.clipped {{ width: 400px; height: 60px; overflow: hidden; font-size: 32px; }}
</style></head><body data-visual-system="fixture">
<section data-slide-role="summary"><h2>이 슬라이드는 깔끔하게 들어갑니다</h2><p>{LONG_SLIDE_TEXT}</p><aside class="notes">노트 하나</aside></section>
<section data-slide-role="risk"><h2>이 슬라이드는 상자가 넘칩니다</h2>
<div class="clipped">길고 긴 문장이 상자 높이를 넘도록 계속 이어집니다 길고 긴 문장이 상자 높이를 넘도록 계속 이어집니다 길고 긴 문장이 상자 높이를 넘도록 계속 이어집니다</div>
<aside class="notes">노트 둘</aside></section>
</body></html>
"""
MEASURED_SLIDES = [
    {"index": 1, "height": 900, "contentBands": [[80, 820]], "overflow": [], "outOfFrame": [], "overlaps": [], "distortedImages": []},
    {
        "index": 2,
        "height": 900,
        "contentBands": [[80, 820]],
        "overflow": [{"selector": "div.clipped", "text": "길고 긴 문장", "scrollWidth": 400, "clientWidth": 400, "scrollHeight": 273, "clientHeight": 60}],
        "outOfFrame": [{"selector": "div.badge", "text": "밖으로", "rect": {"left": 1500, "top": 1000, "right": 1800, "bottom": 1050}}],
        "overlaps": [{"first": {"selector": "div.note", "text": "겹침"}, "second": {"selector": "div.other", "text": "겹침 둘"}, "ratio": 0.68}],
        "distortedImages": [{"selector": "img", "text": "", "renderedRatio": 4.0, "naturalRatio": 1.0}],
    },
]
GEOMETRY_CODES = {"CONTENT_OVERFLOW", "OUT_OF_FRAME", "TEXT_OVERLAP", "IMAGE_DISTORTED"}
TIMELINE_BANDS_ENDING_AT_62_PERCENT = [[44, 47], [72, 98], [126, 187], [234, 264], [280, 558], [800, 802], [815, 836]]
RISK_TABLE_BANDS_ENDING_AT_72_PERCENT = [[44, 47], [72, 98], [126, 187], [216, 648], [800, 802], [815, 836]]


def measured_slide(index: int, bands: list[list[float]]) -> dict:
    return {"index": index, "height": 900, "contentBands": bands, "overflow": [], "outOfFrame": [], "overlaps": [], "distortedImages": []}


def write_review_fixture(deck_path: Path, geometry_slides) -> Path:
    source_path = deck_path / "slides.html"
    source_path.write_text(FIXTURE_SOURCE, encoding="utf-8")
    review_path = deck_path / "review"
    review_path.mkdir()
    for number in (1, 2):
        write_png(review_path / f"deck.{number:03d}.png", 32, 18, [[(255, 255, 255, 255)] * 32 for _ in range(18)])
    if geometry_slides is not None:
        (review_path / "geometry.json").write_text(json.dumps({"viewport": {"width": 1600, "height": 900}, "slides": geometry_slides}), encoding="utf-8")
    return source_path


def slide_codes(report, issues, index: int) -> set[str]:
    return {issue.kind.code for issue in issues if issue.location == f"slide {index}"}


class GeometryReviewTest(unittest.TestCase):
    def review(self, geometry_slides):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            source_path = write_review_fixture(deck_path, geometry_slides)
            return build_review_report(source_path, "deck", deck_path / "review")

    def test_measured_findings_are_reported_on_their_own_slide_only(self):
        report, issues = self.review(MEASURED_SLIDES)
        self.assertTrue(report["geometryMeasured"])
        self.assertEqual(slide_codes(report, issues, 1) & GEOMETRY_CODES, set())
        self.assertEqual(slide_codes(report, issues, 2) & GEOMETRY_CODES, GEOMETRY_CODES)
        overflow = next(issue for issue in issues if issue.kind.code == "CONTENT_OVERFLOW")
        self.assertIn("div.clipped", overflow.message)
        self.assertIn("273", overflow.message)

    def test_a_missing_geometry_file_is_reported_not_guessed(self):
        report, issues = self.review(None)
        self.assertFalse(report["geometryMeasured"])
        codes = {issue.kind.code for issue in issues}
        self.assertIn("GEOMETRY_NOT_MEASURED", codes)
        self.assertEqual(codes & GEOMETRY_CODES, set())

    def test_a_body_that_stops_high_above_its_footer_is_a_dead_zone_the_empty_band_check_missed(self):
        report, issues = self.review([measured_slide(1, TIMELINE_BANDS_ENDING_AT_62_PERCENT), measured_slide(2, RISK_TABLE_BANDS_ENDING_AT_72_PERCENT)])
        self.assertIn("VERTICAL_DEAD_ZONE", slide_codes(report, issues, 1))
        self.assertNotIn("VERTICAL_DEAD_ZONE", slide_codes(report, issues, 2))
        dead_zone = next(issue for issue in issues if issue.kind.code == "VERTICAL_DEAD_ZONE")
        self.assertIn("ends at 62%", dead_zone.message)
        self.assertIn("27% of it empty above the footer", dead_zone.message)

    def test_long_text_alone_no_longer_raises_an_overflow_warning(self):
        report, issues = self.review(MEASURED_SLIDES[:1] + MEASURED_SLIDES[:1])
        self.assertGreater(report["slides"][0]["textCharacterCount"], 900)
        self.assertEqual({issue.kind.code for issue in issues} & (GEOMETRY_CODES | {"TEXT_OVERFLOW_RISK"}), set())


class RenderedGeometryTest(unittest.TestCase):
    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_the_renderer_measures_an_overflowing_box_and_leaves_a_clean_slide_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            (deck_path / "slides.html").write_text(FIXTURE_SOURCE, encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build"], capture_output=True, text=True, cwd=deck_path)
            envelope = json.loads(completed.stdout)
            if envelope["details"]["review"]["renderSource"] != "layout":
                self.skipTest("the renderer could not run on this host")
            geometry = json.loads((deck_path / "build" / "review" / "geometry.json").read_text(encoding="utf-8"))
        clean, clipped = geometry["slides"]
        self.assertEqual(clean["overflow"], [])
        self.assertEqual([finding["selector"] for finding in clipped["overflow"]], ["div.clipped"])
        self.assertIn("CONTENT_OVERFLOW", {issue["code"] for issue in envelope["issues"]})
        self.assertLess(clipped["contentBands"][-1][1], clipped["height"] / 3)
        dead_zones = {issue["location"]: issue["message"] for issue in envelope["issues"] if issue["code"] == "VERTICAL_DEAD_ZONE"}
        self.assertIn("empty below it", dead_zones["slide 2"])


def cards_slide(sentence_count: int) -> str:
    paragraph = "매장 운영 시간을 줄이고 발주 정확도를 높입니다. " * sentence_count
    cards = "".join(f'<div class="card"><h3>{title}</h3><p>{paragraph}</p></div>' for title in ("품절 알림", "발주 추천", "매출 정산"))
    return f'<section data-layout="cards"><h2>세 기능이 재고 업무를 줄입니다</h2>{cards}<aside class="notes">세 기능</aside></section>'


def kit_deck(*slides: str) -> str:
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>맞춤 시험</title></head><body data-theme="editorial">' + "".join(slides) + "</body></html>"


LONG_STATEMENT = '<section data-layout="statement"><h2>' + "재고 관리 자동화로 매장 운영 시간을 줄이고 발주 정확도를 높이며 고객 만족도를 끌어올립니다. " * 6 + '</h2><aside class="notes">긴 문장</aside></section>'


class KitCollisionTest(unittest.TestCase):
    def build(self, source: str) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "slides.html").write_text(source, encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build"], capture_output=True, text=True, cwd=directory)
        envelope = json.loads(completed.stdout)
        if envelope["details"]["review"]["renderSource"] != "layout":
            self.skipTest("the renderer could not run on this host")
        return envelope

    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_cards_whose_text_spills_past_their_box_and_a_paragraph_long_title_are_defects(self):
        envelope = self.build(kit_deck(cards_slide(30), LONG_STATEMENT))
        acceptance = envelope["details"]["acceptance"]
        self.assertFalse(acceptance["acceptable"])
        defects = {(defect["code"], defect["location"]) for defect in acceptance["defects"]}
        self.assertTrue({("CONTENT_OVERFLOW", "slide 1"), ("OUT_OF_FRAME", "slide 1"), ("TITLE_TOO_LONG", "slide 2")} <= defects, defects)

    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_the_kit_shrinks_cards_that_would_cover_the_title_until_they_fit(self):
        envelope = self.build(kit_deck(cards_slide(12)))
        self.assertTrue(envelope["details"]["acceptance"]["acceptable"], envelope["summary"])


if __name__ == "__main__":
    unittest.main()
