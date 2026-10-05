import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from design_gate_fixture import issue_codes, issues_at  # noqa: E402
from design_gate_slides import CLEAN, CLEAN_STYLE, SEEDED, SEEDED_STYLE, SEEDED_VARIANTS, VARIANT_STYLE  # noqa: E402
from render_fixture import can_render  # noqa: E402
from staged_deck_fixture import SCRIPTS_PATH, check_deck, write_staged_deck  # noqa: E402

RULE_CODES = {rule["code"] for rule in json.loads((SCRIPTS_PATH.parent / "assets" / "design-rules.json").read_text(encoding="utf-8"))["rules"]}


@unittest.skipUnless(can_render(), "the renderer is not available")
class SeededRenderGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.envelope = check_deck(write_staged_deck(Path(cls.directory.name), list(SEEDED.values()), SEEDED_STYLE))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_every_kept_rule_is_seeded(self):
        self.assertEqual(set(SEEDED), RULE_CODES)

    def test_every_rule_fires_on_its_own_page(self):
        for number, code in enumerate(SEEDED, start=1):
            with self.subTest(code=code):
                located = [issue["location"] for issue in issues_at(self.envelope, code)]
                self.assertIn(f"page {number}", located, sorted(issue_codes(self.envelope)))

    def test_no_rule_fires_on_a_page_seeded_for_another(self):
        codes = list(SEEDED)
        for number, seeded in enumerate(codes, start=1):
            found = {issue["code"] for issue in self.envelope["issues"] if issue["location"] == f"page {number}" and issue["code"] in codes}
            with self.subTest(seeded=seeded):
                self.assertLessEqual(found - {seeded}, {"OUT_OF_FRAME"} if seeded == "CONTENT_OVERFLOW" else set(), found)

    def test_a_refusal_names_the_code_the_page_and_the_selector(self):
        issue = issues_at(self.envelope, "ONE_SIDED_ACCENT_BAR")[0]
        self.assertEqual(issue["severity"], "error")
        self.assertEqual(issue["location"], "page 2")
        self.assertIn("div.callout", issue["message"])


@unittest.skipUnless(can_render(), "the renderer is not available")
class VariantRenderGateTest(unittest.TestCase):
    def test_every_variant_of_a_rule_is_found_on_its_page(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = check_deck(write_staged_deck(Path(directory), [content for _, content in SEEDED_VARIANTS], VARIANT_STYLE))
        for number, (code, _) in enumerate(SEEDED_VARIANTS, start=1):
            with self.subTest(code=code, page=number):
                self.assertIn(f"page {number}", [issue["location"] for issue in issues_at(envelope, code)], sorted(issue_codes(envelope)))


@unittest.skipUnless(can_render(), "the renderer is not available")
class CleanRenderGateTest(unittest.TestCase):
    def test_clean_decks_raise_no_refusal(self):
        for index, sections in enumerate(CLEAN, start=1):
            with self.subTest(deck=index), tempfile.TemporaryDirectory() as directory:
                envelope = check_deck(write_staged_deck(Path(directory), sections, CLEAN_STYLE))
                self.assertNotEqual(envelope["status"], "error", envelope["summary"])
                self.assertFalse(issue_codes(envelope) & RULE_CODES, envelope["summary"])


if __name__ == "__main__":
    unittest.main()
