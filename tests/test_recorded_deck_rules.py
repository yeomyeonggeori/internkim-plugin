from pathlib import Path
import json
import os
import shutil
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_fixture import can_render  # noqa: E402

RECORDED = Path(__file__).resolve().parent / "recorded"
SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from deck.deck_logo import logo_crop_box, read_logo  # noqa: E402
from core.design_rules import render_rule_issues  # noqa: E402
from core.host_contract import RUNTIME_CONTEXT_VARIABLE  # noqa: E402
from deck.deck_html import measure_for_gate  # noqa: E402
from deck.design_system import read_design_system  # noqa: E402
from staged_deck_fixture import style_sheet_markdown  # noqa: E402


def measure_with_company_logo(path: Path, system) -> list[dict]:
    company = path / "company"
    company.mkdir()
    if (path / "logo.png").exists():
        shutil.copy(path / "logo.png", company / "logo.png")
        (company / "company-profile.json").write_text(json.dumps({"name": "Sample", "logoImage": "logo.png"}), encoding="utf-8")
    context = company / "office-runtime-context.json"
    context.write_text(json.dumps({"requester": {"name": "", "email": ""}, "today": "2026-10-04", "company": {"en": str(company / "company-profile.json")} if (company / "company-profile.json").exists() else {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": False}), encoding="utf-8")
    previous = os.environ.get(RUNTIME_CONTEXT_VARIABLE)
    os.environ[RUNTIME_CONTEXT_VARIABLE] = str(context)
    try:
        return measure_for_gate(path / "slides.html", system)
    finally:
        os.environ.pop(RUNTIME_CONTEXT_VARIABLE, None)
        if previous is not None:
            os.environ[RUNTIME_CONTEXT_VARIABLE] = previous


BALANCED = ({"display": "64px", "title": "48px", "body": "28px", "small": "20px"}, "96px", "32px")
AIRY = ({"display": "72px", "title": "56px", "body": "30px", "small": "22px"}, "104px", "40px")
RECORDED_DENSITY = {"ko_smartfarm_v2": AIRY, "ko_smartfarm_grant": AIRY}


def recorded_scale(name: str) -> dict:
    return {"sizes": RECORDED_DENSITY.get(name, BALANCED)[0]}


def with_recorded_tokens(name: str, source: str) -> str:
    _, margin, gap = RECORDED_DENSITY.get(name, BALANCED)
    return source.replace("</head>", f"<style>:root {{ --margin: {margin}; --gap: {gap}; --border: 1px; }}</style></head>", 1)


def measured(name: str, rewrite=lambda source: source) -> list:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        for source in (RECORDED / name).iterdir():
            shutil.copy(source, path / source.name)
        (path / "slides.html").write_text(with_recorded_tokens(name, rewrite((path / "slides.html").read_text(encoding="utf-8"))), encoding="utf-8")
        Image.new("RGB", (1200, 800), (90, 140, 70)).save(path / "photo.jpg")
        (path / "DESIGN.md").write_text(style_sheet_markdown(recorded_scale(name)), encoding="utf-8")
        system, _ = read_design_system(path / "DESIGN.md")
        slides = measure_with_company_logo(path, system)
    return [issue for number, slide in enumerate(slides, start=1) for issue in render_rule_issues(slide.get("designFindings", []), f"slide {number}")]


def slides_with(issues: list, code: str) -> set[int]:
    return {int(issue.location.split()[-1]) for issue in issues if issue.kind.code == code}


def messages_of(issues: list, code: str, location: str) -> list[str]:
    return [issue.message for issue in issues if issue.kind.code == code and issue.location == location]


@unittest.skipUnless(can_render(), "the renderer is not available")
class RecordedEnglishDeckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.issues = measured("en_product_strategy")

    def test_text_below_the_size_floor_is_refused(self):
        self.assertIn(2, slides_with(self.issues, "TEXT_TOO_SMALL"))
        self.assertIn(4, slides_with(self.issues, "TEXT_TOO_SMALL"))

    def test_a_thick_one_sided_border_on_a_plain_column_is_refused(self):
        self.assertIn(2, slides_with(self.issues, "ONE_SIDED_ACCENT_BAR"))


@unittest.skipUnless(can_render(), "the renderer is not available")
class RecordedKoreanDeckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.issues = measured("ko_smartfarm_grant")

    def test_text_below_the_size_floor_is_refused(self):
        self.assertTrue(slides_with(self.issues, "TEXT_TOO_SMALL"))



@unittest.skipUnless(can_render(), "the renderer is not available")
class SecondRoundRecordedDeckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.korean = measured("ko_smartfarm_v2")
        cls.hiring = measured("en_hiring_v2")
        cls.product = measured("en_product_v2")

    def test_a_list_that_spills_past_its_box_and_off_the_slide_is_refused_as_overflow_and_out_of_frame(self):
        self.assertEqual(slides_with(self.korean, "CONTENT_OVERFLOW"), {4})
        self.assertEqual(slides_with(self.korean, "OUT_OF_FRAME"), {4})
        for clean in (self.hiring, self.product):
            self.assertEqual(slides_with(clean, "CONTENT_OVERFLOW") | slides_with(clean, "OUT_OF_FRAME"), set())

    def test_a_logo_drawn_over_a_title_is_refused_as_overlap(self):
        placed_by_the_model = measured("en_product_v2", lambda source: source.replace(" data-logo>", ' src="logo.png">'))
        self.assertTrue({6, 7} <= slides_with(placed_by_the_model, "CONTENT_OVERLAP"), slides_with(placed_by_the_model, "CONTENT_OVERLAP"))
        self.assertEqual(slides_with(self.product, "CONTENT_OVERLAP"), set())

    def test_a_chart_that_collapsed_to_its_labels_is_refused_and_a_drawn_one_is_not(self):
        self.assertEqual(slides_with(self.hiring, "CHART_COLLAPSED"), {2, 3, 4})
        self.assertEqual(slides_with(self.korean, "CHART_COLLAPSED") | slides_with(self.product, "CHART_COLLAPSED"), set())



class LogoTrimTest(unittest.TestCase):
    def test_a_logo_drawn_small_inside_a_wide_white_margin_is_cropped_to_its_mark(self):
        logo = read_logo(RECORDED / "ko_smartfarm_grant" / "logo.png")
        left, top, right, bottom = logo_crop_box(logo.path)
        self.assertLess(right - left, 512 * 0.6)
        self.assertLess(bottom - top, 512 * 0.8)
        self.assertGreater(logo.width / logo.height, 0.5)
        self.assertLess(logo.width, 400)

    def test_no_wide_margin_is_left_around_the_mark(self):
        logo = read_logo(RECORDED / "ko_smartfarm_grant" / "logo.png")
        self.assertLessEqual(logo.width * logo.height, 512 * 512 * 0.45)


if __name__ == "__main__":
    unittest.main()
