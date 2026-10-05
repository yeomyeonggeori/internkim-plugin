from pathlib import Path
import sys
import unittest

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from core.css_color import hex_oklch  # noqa: E402
from deck.deck_guide import composition_lines  # noqa: E402
from deck.design_system import build_design_system, derived_colors  # noqa: E402


def derived(ground: str, text: str, accent: str) -> dict[str, str]:
    return derived_colors(build_design_system({"colors": {"ground": ground, "text": text, "accent": accent, "secondary": accent}, "fonts": {"display": "Paperlogy", "body": "Paperlogy"}, "type": {"title": "48px", "body": "28px"}}))


class SurfaceTintTest(unittest.TestCase):
    def test_a_surface_carries_the_accents_hue_instead_of_grey(self):
        for ground, text, accent in (("FFFFFF", "1A1A1F", "8C5A2B"), ("FFFFFF", "1A1A1F", "1F5FBF"), ("141821", "F4F4F6", "7FB0FF")):
            with self.subTest(accent=accent):
                colors = derived(ground, text, accent)
                lightness, chroma, hue = hex_oklch(colors["surface"])
                accent_hue = hex_oklch(accent)[2]
                self.assertGreater(chroma, 0.006)
                self.assertLess(abs((hue - accent_hue + 180) % 360 - 180), 25)
                self.assertNotEqual(colors["surface"], colors["ground"])


class CompositionGuidanceTest(unittest.TestCase):
    def test_the_guide_offers_named_compositions_built_from_the_tokens(self):
        text = "\n".join(composition_lines())
        for composition in ("field cover", "chart with a takeaway", "statement", "table", "sequence", "photo beside text"):
            with self.subTest(composition=composition):
                self.assertIn(composition, text)
        for token in ("var(--accent)", "var(--on-accent)", "var(--surface)"):
            self.assertIn(token, text)

    def test_the_guide_asks_for_one_dominant_part_per_slide(self):
        self.assertIn("one dominant part", "\n".join(composition_lines()))


if __name__ == "__main__":
    unittest.main()


class CompositionGatingTest(unittest.TestCase):
    def test_the_compositions_the_guide_offers_pass_the_render_gate(self):
        import tempfile

        from design_gate_fixture import design_markdown, run_office
        from design_gate_slides import deck
        from render_fixture import can_render

        if not can_render():
            self.skipTest("the renderer is not available")
        style = """
.field { background: var(--accent); color: var(--on-accent); justify-content: center; gap: 32px; }
.field h1 { color: var(--on-accent); font-size: var(--size-display); }
.statement { justify-content: center; }
.statement p.big { font-size: var(--size-display); font-family: var(--font-display); line-height: 1.15; }
.chartrow { display: flex; gap: 64px; flex: 1; align-items: center; }
.chartrow figure { width: 940px; height: 620px; margin: 0; }
.panel { flex: 1; justify-content: center; background: var(--surface); padding: 48px; border-radius: var(--radius); display: flex; flex-direction: column; gap: 20px; }
table { border-collapse: collapse; width: 100%; font-size: 28px; height: 560px; }
th, td { text-align: left; padding: 14px 0; border-bottom: 1px solid var(--line); }
"""
        sections = [
            (' class="field"', '<h1>Ledgerline 2027 product strategy</h1><p>Leadership offsite, October</p>'),
            (' class="statement"', '<p class="big">Retention, not signups, is the ceiling.</p><p>Churn held at 3.1 percent a month.</p>'),
            '<h2>Cafes grew by 1,100 in two quarters</h2><div class="chartrow"><figure data-chart="bar" data-labels="Q1, Q2, Q3" data-values="3100, 3500, 4200" data-unit=""></figure><p>Growth came from existing cafes referring peers.</p></div>',
            '<h2>Three bets for 2027</h2><div class="panel"><p>Inventory sync ships in Q1.</p><p>Payroll pilot runs in Q2 with 50 cafes.</p></div>',
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "DESIGN.md").write_text(design_markdown(), encoding="utf-8")
            (path / "slides.html").write_text(deck(sections, style), encoding="utf-8")
            envelope = run_office(["check", "slides.html"], path)
        self.assertEqual(envelope["status"], "ok", envelope["summary"])
