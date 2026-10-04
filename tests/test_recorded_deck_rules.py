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
from deck.design_system import read_design_system, token_issues  # noqa: E402


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


def measured(name: str) -> list:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        for source in (RECORDED / name).iterdir():
            shutil.copy(source, path / source.name)
        Image.new("RGB", (1200, 800), (90, 140, 70)).save(path / "photo.jpg")
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

    def test_clustered_content_with_an_empty_band_is_refused(self):
        self.assertTrue({5, 6, 7, 8} <= slides_with(self.issues, "CONTENT_CLUSTERED"), slides_with(self.issues, "CONTENT_CLUSTERED"))

    def test_slides_that_use_the_canvas_are_not_called_clustered(self):
        self.assertFalse({3, 9, 11} & slides_with(self.issues, "CONTENT_CLUSTERED"))

    def test_clustered_refusal_names_how_much_is_empty(self):
        self.assertRegex(messages_of(self.issues, "CONTENT_CLUSTERED", "slide 5")[0], r"\d+px")

    def test_three_big_numbers_over_small_labels_are_refused_on_the_slide_and_the_cover(self):
        self.assertTrue({1, 2} <= slides_with(self.issues, "HERO_METRIC_TEMPLATE"), slides_with(self.issues, "HERO_METRIC_TEMPLATE"))

    def test_an_eyebrow_above_body_text_is_refused(self):
        self.assertTrue({4, 6, 7, 8} <= slides_with(self.issues, "LABEL_ABOVE_HEADING"), slides_with(self.issues, "LABEL_ABOVE_HEADING"))

    def test_an_em_dash_in_a_title_is_refused(self):
        self.assertIn(2, slides_with(self.issues, "EM_DASH_OVERUSE"))

    def test_a_thick_one_sided_border_on_a_plain_column_is_refused(self):
        self.assertIn(2, slides_with(self.issues, "ONE_SIDED_ACCENT_BAR"))


@unittest.skipUnless(can_render(), "the renderer is not available")
class RecordedKoreanDeckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.issues = measured("ko_smartfarm_grant")

    def test_text_below_the_size_floor_is_refused(self):
        self.assertTrue(slides_with(self.issues, "TEXT_TOO_SMALL"))

    def test_clustered_content_with_an_empty_band_is_refused(self):
        self.assertTrue({6, 9} <= slides_with(self.issues, "CONTENT_CLUSTERED"), slides_with(self.issues, "CONTENT_CLUSTERED"))


class TypeScaleTokenTest(unittest.TestCase):
    def read(self, name: str):
        system, issues = read_design_system(RECORDED / name / "DESIGN.md")
        self.assertEqual(issues, [])
        return system

    def test_a_body_size_under_the_floor_is_refused_in_the_design_file(self):
        for name in ("en_product_strategy", "ko_smartfarm_grant"):
            with self.subTest(deck=name):
                codes = {issue.kind.code for issue in token_issues(self.read(name))}
                self.assertIn("TEXT_TOO_SMALL", codes)


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
