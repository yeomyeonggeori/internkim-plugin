import itertools
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.host_contract import RUNTIME_CONTEXT_VARIABLE  # noqa: E402
from deck.deck_design import DESIGN, QUESTIONS, Choice, Design, palette_candidates, resolve_design, type_scale  # noqa: E402
from deck.design_system import design_tokens, read_design_system, token_issues  # noqa: E402
from design_gate_fixture import run_office  # noqa: E402
from render_fixture import can_render  # noqa: E402

DECK_FAMILIES = ("Paperlogy", "Freesentation", "A2Z")


def decided(**options: str) -> dict:
    return {"choices": {axis: {"option": option} for axis, option in options.items()}}


def read(selection: str, design: dict | None = None):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / "DESIGN.md").write_text(f"---\n{selection}\n---\n", encoding="utf-8")
        previous = os.environ.pop(RUNTIME_CONTEXT_VARIABLE, None)
        if design is not None:
            context = path / "context.json"
            context.write_text(json.dumps({"requester": {"name": "", "email": ""}, "today": "2026-10-04", "company": {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": False, "deckDesign": design}), encoding="utf-8")
            os.environ[RUNTIME_CONTEXT_VARIABLE] = str(context)
        try:
            return read_design_system(path / "DESIGN.md")
        finally:
            os.environ.pop(RUNTIME_CONTEXT_VARIABLE, None)
            if previous is not None:
                os.environ[RUNTIME_CONTEXT_VARIABLE] = previous


def codes(issues) -> set[str]:
    return {issue.kind.code for issue in issues}


class SelectionTest(unittest.TestCase):
    def test_a_palette_name_alone_is_a_whole_design_file(self):
        system, issues = read("palette: primary")
        self.assertEqual(issues, [])
        self.assertEqual(system.fonts, {"display": "Paperlogy", "body": "Paperlogy"})
        self.assertGreaterEqual(system.sizes["body"], 28)
        self.assertEqual(token_issues(system), [])

    def test_a_free_color_font_radius_or_shadow_is_not_a_token(self):
        for line in ('colors:\n  ground: "#F5EFE0"', "fonts:\n  display: Inter", "radius: 40px", "shadow: 0 0 32px #1F5FBF", "type:\n  body: 12px"):
            with self.subTest(line=line):
                _, issues = read(f"palette: primary\n{line}")
                self.assertEqual(codes(issues), {"DESIGN_VALUE_INVALID"})

    def test_a_palette_outside_the_candidates_is_refused_with_the_candidates_named(self):
        _, issues = read("palette: sunset")
        self.assertEqual(codes(issues), {"DESIGN_VALUE_INVALID"})
        self.assertIn("primary", issues[0].message)

    def test_a_missing_palette_is_named(self):
        _, issues = read("intent: calm")
        self.assertEqual(codes(issues), {"DESIGN_INCOMPLETE"})

    def test_the_type_is_one_of_the_three_deck_families(self):
        for option, family in (("paperlogy", "Paperlogy"), ("freesentation", "Freesentation"), ("a2z", "A2Z")):
            with self.subTest(option=option):
                system, issues = read(f"palette: primary\ntype: {option}")
                self.assertEqual((issues, system.fonts["body"], system.fonts["display"]), ([], family, family))
        self.assertEqual(codes(read("palette: primary\ntype: Helvetica")[1]), {"DESIGN_VALUE_INVALID"})
        self.assertEqual(codes(read("palette: primary\ntype: modern")[1]), {"DESIGN_VALUE_INVALID"})

    def test_the_decision_chooses_the_type_when_the_file_does_not(self):
        system, _ = read("palette: primary", decided(type="a2z"))
        self.assertEqual(system.fonts["body"], "A2Z")

    def test_the_decision_defaults_to_paperlogy(self):
        self.assertEqual(QUESTIONS["type"]["fallback"], "paperlogy")
        self.assertEqual(set(DESIGN["types"]), {"paperlogy", "freesentation", "a2z"})

    def test_a_display_weight_is_one_the_family_ships(self):
        system, issues = read("palette: primary\nweight: 800")
        self.assertEqual(issues, [])
        self.assertEqual(design_tokens(system)["weight-display"], "800")
        self.assertEqual(codes(read("palette: primary\ntype: freesentation\nweight: 800")[1]), {"DESIGN_VALUE_INVALID"})
        self.assertEqual(codes(read("palette: primary\nweight: 900")[1]), {"DESIGN_VALUE_INVALID"})

    def test_the_shape_is_a_closed_scale_without_extreme_radius_or_shadow(self):
        for name, shape in DESIGN["shapes"].items():
            with self.subTest(shape=name):
                system, issues = read(f"palette: primary\nshape: {name}")
                self.assertEqual(issues, [])
                self.assertLessEqual(system.radius, 24)
                self.assertEqual(system.shadow, "none")
        self.assertEqual(codes(read("palette: primary\nshape: pill")[1]), {"DESIGN_VALUE_INVALID"})


class EveryReachableDesignTest(unittest.TestCase):
    def test_every_combination_of_the_decision_derives_a_system_the_screen_passes(self):
        axes = {axis: tuple(QUESTIONS[axis]["options"]) for axis in ("accent", "mood", "temperature", "type", "density")}
        for combination in itertools.product(*axes.values()):
            choices = dict(zip(axes, combination))
            design = decided(**choices)
            candidates = palette_candidates(resolve_design(design))
            with self.subTest(**choices):
                self.assertTrue(candidates)
                system, issues = read(f"palette: {candidates[0]['name']}", design)
                self.assertEqual(issues, [])
                self.assertEqual(token_issues(system), [])
                self.assertIn(system.fonts["body"], DECK_FAMILIES)

    def test_the_type_scale_is_generated_from_a_base_and_ratios_with_floors(self):
        for density, scale in DESIGN["densities"].items():
            with self.subTest(density=density):
                scale = type_scale(resolve_design(decided(density=density)))
                body = float(scale["body"].removesuffix("px"))
                title = float(scale["title"].removesuffix("px"))
                small = float(scale["small"].removesuffix("px"))
                self.assertGreaterEqual(body, 28)
                self.assertGreaterEqual(small, 20)
                self.assertGreaterEqual(title / body, 1.5)


@unittest.skipUnless(can_render(), "the renderer is not available")
class ModelCssCannotSetAFontTest(unittest.TestCase):
    def test_a_font_family_in_the_slides_is_ignored_and_the_kit_writes_the_family(self):
        from design_gate_slides import deck
        from free_deck_fixture import write_free_deck
        from deck.deck_html import kit_html_text

        with tempfile.TemporaryDirectory() as directory:
            sections = ['<h2 style="font-family: Georgia, serif">Revenue grew</h2><p style="font-family: Comic Sans MS">Body text that is long enough to count as a sentence here.</p>']
            path = write_free_deck(Path(directory), sections, "p { font-family: Papyrus; } h2 { font-family: 'Times New Roman'; }")
            (path / "DESIGN.md").write_text("---\npalette: primary\n---\n", encoding="utf-8")
            system, issues = read_design_system(path / "DESIGN.md")
            self.assertEqual(issues, [])
            html = kit_html_text(path / "slides.html", system)
        for family in ("Georgia", "Comic Sans", "Papyrus", "Times New Roman"):
            self.assertNotIn(family, html)
        self.assertIn("var(--font-body)", html)


@unittest.skipUnless(can_render(), "the renderer is not available")
class RenderedFamiliesInvariantTest(unittest.TestCase):
    def families_of(self, selection: str, sections: list, style: str = "") -> set[str]:
        import deck.deck_html as deck_html
        import deck.layout_thresholds as thresholds
        from design_gate_slides import deck
        from free_deck_fixture import write_free_deck

        original = thresholds.gate_thresholds
        deck_html.gate_thresholds = lambda: original() | {"designRules": [{"code": "FAMILIES", "measure": "fontFamilies", "threshold": {}}]}
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = write_free_deck(Path(directory), sections, style)
                (path / "DESIGN.md").write_text(f"---\n{selection}\n---\n", encoding="utf-8")
                system, _ = read_design_system(path / "DESIGN.md")
                slides = deck_html.measure_for_gate(path / "slides.html", system)
        finally:
            deck_html.gate_thresholds = original
        return {finding["detail"].split(",")[0].strip('" ') for slide in slides for finding in slide["designFindings"]}

    def test_every_text_element_is_set_in_the_decks_family_whatever_the_slides_ask_for(self):
        hostile = ['<h2 style="font-family: Georgia">Revenue grew</h2><p style="font-family: Papyrus">Body text long enough to be a sentence.</p><p class="mono">Another line of body text for the slide.</p>']
        style = ".mono { font-family: 'Courier New', monospace; font: 20px Arial; } h2 { font-family: serif; }"
        for option, family in (("paperlogy", "Paperlogy"), ("freesentation", "Freesentation"), ("a2z", "A2Z")):
            with self.subTest(type=option):
                self.assertEqual(self.families_of(f"palette: primary\ntype: {option}", hostile, style), {family})


if __name__ == "__main__":
    unittest.main()
