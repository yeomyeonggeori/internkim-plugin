import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from design_gate_fixture import design_markdown, issue_codes, issues_at, run_office  # noqa: E402
from design_gate_slides import CLEAN, CLEAN_STYLE, SEEDED, SEEDED_STYLE, SEEDED_VARIANTS, VARIANT_STYLE, deck  # noqa: E402
from render_fixture import can_render  # noqa: E402


@unittest.skipUnless(can_render(), "the renderer is not available")
class SeededRenderGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        path = Path(cls.directory.name)
        (path / "DESIGN.md").write_text(design_markdown(), encoding="utf-8")
        (path / "slides.html").write_text(deck(list(SEEDED.values()), SEEDED_STYLE), encoding="utf-8")
        cls.envelope = run_office(["check", "slides.html"], path)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_every_rule_fires_on_its_own_slide(self):
        for number, code in enumerate(SEEDED, start=1):
            with self.subTest(code=code):
                located = [issue["location"] for issue in issues_at(self.envelope, code)]
                self.assertIn(f"slide {number}", located, sorted(issue_codes(self.envelope)))

    def test_no_rule_fires_on_a_slide_seeded_for_another(self):
        codes = list(SEEDED)
        collateral = {
            ("ICON_ABOVE_HEADING", "LABEL_ABOVE_HEADING"),
            ("GRID_STRIPE_BACKGROUND", "CANVAS_NOT_FILLED"),
        }
        for number, seeded in enumerate(codes, start=1):
            found = {issue["code"] for issue in self.envelope["issues"] if issue["location"] == f"slide {number}" and issue["code"] in codes}
            with self.subTest(seeded=seeded):
                self.assertLessEqual(found - {seeded}, {other for first, other in collateral if first == seeded}, found)

    def test_a_refusal_names_the_code_the_slide_and_the_selector(self):
        issue = issues_at(self.envelope, "ONE_SIDED_ACCENT_BAR")[0]
        self.assertEqual(issue["severity"], "error")
        self.assertEqual(issue["location"], "slide 2")
        self.assertIn("div.callout", issue["message"])


@unittest.skipUnless(can_render(), "the renderer is not available")
class VariantRenderGateTest(unittest.TestCase):
    def test_every_variant_of_a_rule_is_found_on_its_slide(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "DESIGN.md").write_text(design_markdown(), encoding="utf-8")
            (path / "slides.html").write_text(deck([content for _, content in SEEDED_VARIANTS], VARIANT_STYLE), encoding="utf-8")
            envelope = run_office(["check", "slides.html"], path)
            for number, (code, _) in enumerate(SEEDED_VARIANTS, start=1):
                with self.subTest(code=code, slide=number):
                    self.assertIn(f"slide {number}", [issue["location"] for issue in issues_at(envelope, code)], sorted(issue_codes(envelope)))


@unittest.skipUnless(can_render(), "the renderer is not available")
class CleanRenderGateTest(unittest.TestCase):
    def test_clean_decks_raise_no_design_refusal(self):
        for index, sections in enumerate(CLEAN, start=1):
            with self.subTest(deck=index), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                (path / "DESIGN.md").write_text(design_markdown(), encoding="utf-8")
                (path / "slides.html").write_text(deck(sections, CLEAN_STYLE), encoding="utf-8")
                envelope = run_office(["check", "slides.html"], path)
                self.assertEqual(envelope["status"], "ok", envelope["summary"])


if __name__ == "__main__":
    unittest.main()
