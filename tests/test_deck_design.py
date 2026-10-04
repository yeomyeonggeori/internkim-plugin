from __future__ import annotations

import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from core.css_color import contrast_ratio, hex_oklch  # noqa: E402
from core.host_contract import HOST_CONTRACT, RUNTIME_CONTEXT_VARIABLE  # noqa: E402
from deck.deck_design import DESIGN, QUESTIONS, design_colors, design_tokens, options, resolve_design  # noqa: E402
from deck.deck_logo import read_logo  # noqa: E402


def decided(**options_by_axis: dict[str, float]) -> dict:
    return {"choices": {axis: {"option": max(probabilities, key=probabilities.get), "probabilities": probabilities} for axis, probabilities in options_by_axis.items()}}


def hue_distance(first: float, second: float) -> float:
    return abs((first - second + 180) % 360 - 180)


class DesignDecisionTest(unittest.TestCase):
    def test_the_accent_follows_the_intent_the_decision_chose(self):
        for intent in options("palette"):
            if intent == "neutral":
                continue
            colors = design_colors(resolve_design({}, decided(palette={intent: 0.9, "neutral": 0.1})))
            self.assertLess(hue_distance(hex_oklch(colors["accent"])[2], DESIGN["hues"][intent]["hue"]), 20, intent)

    def test_a_near_tie_gives_the_runner_up_the_second_accent(self):
        design = resolve_design({}, decided(palette={"fresh": 0.5, "clarity": 0.45, "trust": 0.05}))
        self.assertEqual(design.secondary_palette, "clarity")
        self.assertLess(hue_distance(hex_oklch(design_colors(design)["accent-2"])[2], DESIGN["hues"]["clarity"]["hue"]), 20)
        clear = resolve_design({}, decided(palette={"fresh": 0.8, "clarity": 0.15, "trust": 0.05}))
        self.assertIsNone(clear.secondary_palette)

    def test_an_unsure_decision_falls_back_to_the_safe_option(self):
        design = resolve_design({}, decided(cover={"photo": 0.3, "icon": 0.28, "key_figure": 0.22, "type_only": 0.2}))
        self.assertEqual((design.option("cover"), design.choices["cover"].source), (QUESTIONS["cover"]["fallback"], "fallback"))

    def test_what_the_deck_writes_outranks_the_decision(self):
        design = resolve_design({"data-tone": "bold"}, decided(tone={"formal": 0.9, "bold": 0.1}))
        self.assertEqual((design.option("tone"), design.choices["tone"].source), ("bold", "source"))

    def test_the_same_decision_draws_the_same_tokens(self):
        decision = decided(palette={"warmth": 0.6, "energy": 0.4}, tone={"friendly": 0.7, "formal": 0.3}, type={"classic": 1.0})
        self.assertEqual(design_tokens(resolve_design({}, decision)), design_tokens(resolve_design({}, json.loads(json.dumps(decision)))))

    def test_every_derived_palette_reads_at_its_contrast_minimum(self):
        for palette, tone, temperature in itertools.product(options("palette"), options("tone"), options("temperature")):
            colors = design_colors(resolve_design({"data-palette": palette, "data-tone": tone, "data-temperature": temperature}, None))
            for token, minimum in DESIGN["contrast"].items():
                backdrop = colors["feature-bg"] if token.startswith("feature-") else colors["bg"]
                self.assertGreaterEqual(round(contrast_ratio(colors[token], backdrop), 2), minimum, f"{palette} {tone} {temperature} {token}")

    def test_each_type_choice_names_fonts_the_pptx_can_carry(self):
        from fonts.registry import bundled_family, face_facts

        for faces in DESIGN["types"].values():
            for name in faces.values():
                family = bundled_family(name)
                self.assertIsNotNone(family, name)
                self.assertTrue(all(face_facts(family, face).can_embed_in_office for face in family.faces), name)


class LogoTest(unittest.TestCase):
    def logo(self, color: tuple[int, int, int], transparent: bool) -> Path:
        directory = Path(tempfile.mkdtemp())
        image = Image.new("RGBA" if transparent else "RGB", (200, 100), (0, 0, 0, 0) if transparent else (255, 255, 255))
        image.paste(color, (40, 20, 160, 80))
        path = directory / "logo.png"
        image.save(path)
        return path

    def test_the_logo_color_leads_the_palette_in_an_accessible_shade(self):
        for color in ((226, 35, 26), (250, 220, 60)):
            logo = read_logo(self.logo(color, transparent=True))
            colors = design_colors(resolve_design({}, decided(palette={"trust": 0.9, "neutral": 0.1}), logo.brand_color))
            self.assertLess(hue_distance(hex_oklch(colors["accent"])[2], hex_oklch(logo.brand_color)[2]), 12, color)
            self.assertGreaterEqual(contrast_ratio(colors["accent"], colors["bg"]), DESIGN["contrast"]["accent"])

    def test_an_opaque_logo_sits_on_a_plate_and_a_clear_one_only_where_it_fades(self):
        opaque = read_logo(self.logo((20, 40, 120), transparent=False))
        clear = read_logo(self.logo((20, 40, 120), transparent=True))
        self.assertTrue(opaque.needs_plate("FFFFFF"))
        self.assertFalse(clear.needs_plate("FFFFFF"))
        self.assertTrue(clear.needs_plate("101418"))


class DeckPreparationRequestTest(unittest.TestCase):
    def guide_with_context(self, context: dict) -> tuple[str, Path]:
        directory = Path(tempfile.mkdtemp())
        context_path = directory / "office-runtime-context.json"
        context_path.write_text(json.dumps({"requester": {"name": "이샘플", "email": "a@example.com"}, "today": "2026-10-04", "company": {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": False, **context}), encoding="utf-8")
        environment = os.environ | {RUNTIME_CONTEXT_VARIABLE: str(context_path)}
        guide = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", "slides"], capture_output=True, text=True, env=environment, check=True).stdout
        return guide, directory / HOST_CONTRACT["deckPreparation"]["requestFile"]

    def test_the_slides_guide_asks_a_host_that_prepares_decks_once(self):
        guide, request = self.guide_with_context({"preparesDecks": True, "deckDesign": None, "images": []})
        self.assertTrue(request.is_file(), guide[:300])
        self.assertEqual(Path(json.loads(request.read_text(encoding="utf-8"))["design"]).name, "design.json")
        _, prepared = self.guide_with_context({"preparesDecks": True, "deckDesign": decided(palette={"trust": 1.0}), "images": []})
        self.assertFalse(prepared.exists())
        _, unprepared = self.guide_with_context({"preparesDecks": False, "deckDesign": None, "images": []})
        self.assertFalse(unprepared.exists())

    def test_the_design_guide_names_the_decision_and_every_image(self):
        directory = Path(tempfile.mkdtemp())
        photo = directory / "greenhouse.jpg"
        Image.new("RGB", (1600, 1000), (40, 120, 60)).save(photo)
        context_path = directory / "office-runtime-context.json"
        context_path.write_text(json.dumps({"requester": {"name": "", "email": ""}, "today": "2026-10-04", "company": {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": False, "preparesDecks": True,
                                            "deckDesign": decided(palette={"fresh": 0.8, "trust": 0.2}, cover={"photo": 0.9, "type_only": 0.1}),
                                            "images": [{"path": str(photo), "name": "greenhouse.jpg", "source": "dataroom", "title": "Greenhouse rows", "summary": "Strawberry rows", "width": 1600, "height": 1000}]}), encoding="utf-8")
        text = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", "design"], capture_output=True, text=True, env=os.environ | {RUNTIME_CONTEXT_VARIABLE: str(context_path)}, check=True).stdout
        self.assertIn("palette: fresh (fresh 0.80, trust 0.20)", text)
        self.assertIn("cover: photo", text)
        self.assertIn(f"{photo} (1600x1000, dataroom) Greenhouse rows: Strawberry rows", text)

    def test_without_a_host_the_design_guide_lists_every_option_from_the_design_file(self):
        text = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", "design"], capture_output=True, text=True, env={key: value for key, value in os.environ.items() if key != RUNTIME_CONTEXT_VARIABLE}, check=True).stdout
        for axis, question in QUESTIONS.items():
            self.assertIn(f"data-{axis} (default {question['fallback']})", text)
            for option in question["options"]:
                self.assertIn(f"{option}: ", text)


if __name__ == "__main__":
    unittest.main()
