from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deck.design_system import read_design_system, token_issues  # noqa: E402
from design_gate_fixture import design_markdown, issue_codes, run_office  # noqa: E402


SEEDED_TOKENS = {
    "CREAM_GROUND": [{"colors": {"ground": "#F5EFE0"}}, {"colors": {"ground": "#FAF6EC"}}],
    "AI_PALETTE": [{"colors": {"accent": "#7C3AED", "secondary": "#2563EB"}}, {"colors": {"ground": "#0B1220", "text": "#F5F7FA", "accent": "#22D3EE"}}],
    "FONT_NOT_BUNDLED": [{"fonts": {"display": "Inter"}}, {"fonts": {"body": "Helvetica Neue"}}],
    "ITALIC_SERIF_DISPLAY": [{"fonts": {"display": "NanumMyeongjo", "display-style": "italic"}}],
    "FLAT_HIERARCHY": [{"type": {"display": "30px", "title": "30px", "body": "24px"}}],
    "TIGHT_TRACKING": [{"type": {"tracking": "-0.05em"}}],
    "EXTREME_RADIUS": [{"radius": "40px"}, {"radius": "999px"}],
    "HAIRLINE_WIDE_SHADOW": [{"border": "1px", "shadow": "0 24px 64px rgba(0,0,0,0.2)"}],
    "GLOW_SHADOW": [{"shadow": "0 0 32px rgba(31,95,191,0.6)"}, {"glow": "0 0 24px #1F5FBF"}],
    "GLASS_BLUR": [{"glass": "blur(12px)"}, {"backdrop-blur": "16px"}],
    "DECORATIVE_GRADIENT": [{"gradient": "linear-gradient(90deg, #1F5FBF, #0F766E)"}],
    "GRADIENT_TEXT": [{"text-gradient": "linear-gradient(90deg, #1F5FBF, #0F766E)"}],
}

CLEAN_VARIANTS = [
    {},
    {"colors": {"ground": "#FAFAFA"}},
    {"colors": {"ground": "#0F1720", "text": "#F2F5F9", "accent": "#6FA8F5", "secondary": "#7FD1B9"}},
    {"fonts": {"display": "NanumMyeongjo"}, "radius": "8px"},
    {"colors": {"accent": "#9A4156", "secondary": "#4B5563"}, "shadow": "0 2px 6px rgba(0,0,0,0.12)"},
    {"fonts": {"display": "Paperlogy", "body": "Paperlogy"}, "type": {"title": "56px", "body": "26px", "tracking": "-0.01em"}},
]


def codes_for(overrides: dict) -> set[str]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "DESIGN.md"
        path.write_text(design_markdown(overrides), encoding="utf-8")
        system, issues = read_design_system(path)
        return {issue.kind.code for issue in issues + (token_issues(system) if system else [])}


class TokenGateTest(unittest.TestCase):
    def test_each_rule_refuses_its_seeded_tokens(self):
        for code, variants in SEEDED_TOKENS.items():
            for index, overrides in enumerate(variants):
                with self.subTest(code=code, variant=index):
                    self.assertIn(code, codes_for(overrides))

    def test_clean_design_systems_pass(self):
        for index, overrides in enumerate(CLEAN_VARIANTS):
            with self.subTest(variant=index):
                self.assertEqual(codes_for(overrides), set())

    def test_a_missing_design_document_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual({issue.kind.code for issue in read_design_system(Path(directory) / "DESIGN.md")[1]}, {"DESIGN_MISSING"})

    def test_a_missing_token_is_named(self):
        self.assertEqual(codes_for({"colors": {"secondary": None}}), {"DESIGN_INCOMPLETE"})

    def test_low_contrast_text_is_refused(self):
        self.assertIn("DESIGN_LOW_CONTRAST", codes_for({"colors": {"text": "#B0B7C3"}}))

    def test_office_check_refuses_design_before_any_slide_is_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "DESIGN.md").write_text(design_markdown({"colors": {"ground": "#F5EFE0"}, "radius": "40px"}), encoding="utf-8")
            envelope = run_office(["check", "DESIGN.md"], path)
            self.assertEqual(envelope["status"], "error")
            self.assertEqual(issue_codes(envelope), {"CREAM_GROUND", "EXTREME_RADIUS"})

    def test_office_check_passes_a_clean_design(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "DESIGN.md").write_text(design_markdown(), encoding="utf-8")
            self.assertEqual(run_office(["check", "DESIGN.md"], path)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
