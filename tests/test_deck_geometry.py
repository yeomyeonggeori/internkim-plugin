import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "deck"
OFFICE_ENTRY = SCRIPTS_PATH.parent / "office"
sys.path.insert(0, str(SCRIPTS_PATH.parent))
sys.path.insert(0, str(SCRIPTS_PATH))

from png_codec import write_png  # noqa: E402
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
    {"index": 1, "overflow": [], "outOfFrame": [], "overlaps": [], "distortedImages": []},
    {
        "index": 2,
        "overflow": [{"selector": "div.clipped", "text": "길고 긴 문장", "scrollWidth": 400, "clientWidth": 400, "scrollHeight": 273, "clientHeight": 60}],
        "outOfFrame": [{"selector": "div.badge", "text": "밖으로", "rect": {"left": 1500, "top": 1000, "right": 1800, "bottom": 1050}}],
        "overlaps": [{"first": {"selector": "div.note", "text": "겹침"}, "second": {"selector": "div.other", "text": "겹침 둘"}, "ratio": 0.68}],
        "distortedImages": [{"selector": "img", "text": "", "renderedRatio": 4.0, "naturalRatio": 1.0}],
    },
]
GEOMETRY_CODES = {"CONTENT_OVERFLOW", "OUT_OF_FRAME", "TEXT_OVERLAP", "IMAGE_DISTORTED"}


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

    def test_long_text_alone_no_longer_raises_an_overflow_warning(self):
        report, issues = self.review(MEASURED_SLIDES[:1] + MEASURED_SLIDES[:1])
        self.assertGreater(report["slides"][0]["textCharacterCount"], 900)
        self.assertEqual({issue.kind.code for issue in issues} & (GEOMETRY_CODES | {"TEXT_OVERFLOW_RISK"}), set())
        self.assertNotIn("textOverflowRisk", report["slides"][0]["risks"])


def can_render_in_a_browser() -> bool:
    has_browser = any(shutil.which(program) for program in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "moli"))
    has_mac_browser = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists()
    return shutil.which("bun") is not None and (has_browser or has_mac_browser)


class RenderedGeometryTest(unittest.TestCase):
    @unittest.skipUnless(can_render_in_a_browser(), "needs bun and a browser that speaks the Chrome DevTools Protocol")
    def test_the_renderer_measures_an_overflowing_box_and_leaves_a_clean_slide_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            (deck_path / "slides.html").write_text(FIXTURE_SOURCE, encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build"], capture_output=True, text=True, cwd=deck_path)
            envelope = json.loads(completed.stdout)
            if envelope["details"]["review"]["renderSource"] != "browser":
                self.skipTest("the browser did not render the deck on this host")
            geometry = json.loads((deck_path / "build" / "review" / "geometry.json").read_text(encoding="utf-8"))
        clean, clipped = geometry["slides"]
        self.assertEqual(clean["overflow"], [])
        self.assertEqual([finding["selector"] for finding in clipped["overflow"]], ["div.clipped"])
        self.assertIn("CONTENT_OVERFLOW", {issue["code"] for issue in envelope["issues"]})


if __name__ == "__main__":
    unittest.main()
