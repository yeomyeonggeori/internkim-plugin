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
from deck.deck_design import DESIGN, QUESTIONS, accent_hue, options, palette_candidates, resolve_design  # noqa: E402
from deck.deck_logo import read_logo  # noqa: E402
from deck.deck_photos import focal_point, focus_photos  # noqa: E402


def decided(**options_by_axis: dict[str, float]) -> dict:
    return {"choices": {axis: {"option": max(probabilities, key=probabilities.get), "probabilities": probabilities} for axis, probabilities in options_by_axis.items()}}


def hue_distance(first: float, second: float) -> float:
    return abs((first - second + 180) % 360 - 180)


class DesignIntentTest(unittest.TestCase):
    def test_the_accent_candidates_follow_the_hue_family_the_decision_chose(self):
        for intent in options("accent"):
            if intent == "neutral":
                continue
            candidates = palette_candidates(resolve_design(decided(accent={intent: 0.9, "neutral": 0.1})))
            self.assertTrue(candidates, intent)
            for candidate in candidates:
                self.assertLess(hue_distance(hex_oklch(candidate["colors"]["accent"])[2], DESIGN["hues"][intent]["hue"]), 25, intent)

    def test_a_near_tie_leans_toward_the_runner_up(self):
        design = resolve_design(decided(accent={"fresh": 0.5, "clarity": 0.45, "trust": 0.05}))
        self.assertEqual(design.secondary_accent, "clarity")
        self.assertGreater(hue_distance(accent_hue(design), DESIGN["hues"]["fresh"]["hue"]), 0)
        self.assertIsNone(resolve_design(decided(accent={"fresh": 0.8, "clarity": 0.15, "trust": 0.05})).secondary_accent)

    def test_an_unsure_decision_falls_back_to_the_safe_option(self):
        design = resolve_design(decided(mood={"formal": 0.3, "friendly": 0.28, "calm": 0.22, "bold": 0.2}))
        self.assertEqual((design.option("mood"), design.choices["mood"].source), (QUESTIONS["mood"]["fallback"], "fallback"))

    def test_the_logo_color_outranks_the_intent(self):
        design = resolve_design(decided(accent={"trust": 0.9, "neutral": 0.1}), "E2231A")
        for candidate in palette_candidates(design):
            self.assertLess(hue_distance(hex_oklch(candidate["colors"]["accent"])[2], hex_oklch("E2231A")[2]), 14)

    def test_every_candidate_passes_the_gate_and_reads_at_its_contrast(self):
        for accent, mood, temperature in itertools.product(options("accent"), options("mood"), options("temperature")):
            design = resolve_design(decided(accent={accent: 1.0}, mood={mood: 1.0}, temperature={temperature: 1.0}))
            candidates = palette_candidates(design)
            self.assertTrue(candidates, f"{accent} {mood} {temperature}")
            for candidate in candidates:
                self.assertGreaterEqual(candidate["textContrast"], 7, f"{accent} {mood} {temperature}")
                self.assertGreaterEqual(candidate["accentContrast"], 4.5, f"{accent} {mood} {temperature}")

    def test_the_same_decision_draws_the_same_candidates(self):
        decision = decided(accent={"warmth": 0.6, "energy": 0.4}, mood={"friendly": 0.7, "formal": 0.3})
        self.assertEqual(palette_candidates(resolve_design(decision)), palette_candidates(resolve_design(json.loads(json.dumps(decision)))))

    def test_choices_across_subjects_spread_over_the_hue_circle(self):
        hues = [round(accent_hue(resolve_design(decided(accent={intent: 1.0})))) for intent in options("accent") if intent != "neutral"]
        self.assertGreaterEqual(len({hue // 20 for hue in hues}), 6)

    def test_each_type_choice_names_bundled_fonts(self):
        from fonts.registry import bundled_family

        for faces in DESIGN["types"].values():
            for role in ("display", "body"):
                self.assertIsNotNone(bundled_family(faces[role]), faces[role])
            for weight in faces["weights"]:
                self.assertIn(weight, [face.weight for face in bundled_family(faces["display"]).faces])


class LogoTest(unittest.TestCase):
    def logo(self, color: tuple[int, int, int], transparent: bool) -> Path:
        directory = Path(tempfile.mkdtemp())
        image = Image.new("RGBA" if transparent else "RGB", (200, 100), (0, 0, 0, 0) if transparent else (255, 255, 255))
        image.paste(color, (40, 20, 160, 80))
        path = directory / "logo.png"
        image.save(path)
        return path

    def test_the_logo_gives_a_brand_color_only_when_it_has_one(self):
        self.assertIsNotNone(read_logo(self.logo((226, 35, 26), transparent=True)).brand_color)
        self.assertIsNone(read_logo(self.logo((120, 120, 120), transparent=True)).brand_color)

    def test_a_logo_records_whether_it_has_a_clear_background(self):
        self.assertTrue(read_logo(self.logo((20, 40, 120), transparent=True)).has_transparency)
        self.assertFalse(read_logo(self.logo((20, 40, 120), transparent=False)).has_transparency)


class PhotoFocusTest(unittest.TestCase):
    def photo(self, directory: Path, name: str, blob: tuple[int, int, int, int]) -> Path:
        image = Image.new("RGB", (400, 300), (200, 200, 200))
        image.paste((20, 20, 20), blob)
        path = directory / name
        image.save(path)
        return path

    def test_the_focal_point_follows_where_the_detail_is(self):
        with tempfile.TemporaryDirectory() as directory:
            left = focal_point(self.photo(Path(directory), "left.png", (20, 100, 120, 200)))
            right = focal_point(self.photo(Path(directory), "right.png", (280, 100, 380, 200)))
            self.assertLess(left[0], 40)
            self.assertGreater(right[0], 60)

    def test_a_listed_photo_gets_its_focal_point_and_a_logo_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            self.photo(Path(directory), "shelf.png", (280, 100, 380, 200))
            source = '<img src="shelf.png" style="object-fit: cover"><img data-logo src="shelf.png"><img src="https://example.com/a.png">'
            focused = focus_photos(source, Path(directory))
            self.assertIn("object-fit: cover; object-position:", focused)
            self.assertEqual(focused.count("object-position"), 1)

    def test_a_focal_point_the_deck_set_is_kept(self):
        with tempfile.TemporaryDirectory() as directory:
            self.photo(Path(directory), "shelf.png", (280, 100, 380, 200))
            source = '<img src="shelf.png" style="object-position: 10% 10%">'
            self.assertEqual(focus_photos(source, Path(directory)), source)


class DeckPreparationGuideTest(unittest.TestCase):
    def context(self, directory: Path, **fields) -> dict:
        return {"requester": {"name": "이샘플", "email": "a@example.com"}, "today": "2026-10-04", "company": {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": False, **fields}

    def run_guide(self, topic: str, **fields) -> tuple[str, Path]:
        directory = Path(tempfile.mkdtemp())
        context_path = directory / "office-runtime-context.json"
        context_path.write_text(json.dumps(self.context(directory, **fields)), encoding="utf-8")
        environment = os.environ | {RUNTIME_CONTEXT_VARIABLE: str(context_path)}
        text = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", topic], capture_output=True, text=True, env=environment, check=True).stdout
        return text, directory / HOST_CONTRACT["deckPreparation"]["requestFile"]

    def test_the_slides_guide_asks_a_host_that_prepares_decks_once(self):
        guide, request = self.run_guide("slides", preparesDecks=True, deckDesign=None, images=[])
        self.assertTrue(request.is_file(), guide[:300])
        self.assertEqual(Path(json.loads(request.read_text(encoding="utf-8"))["design"]).name, "design.json")
        _, prepared = self.run_guide("slides", preparesDecks=True, deckDesign=decided(accent={"trust": 1.0}), images=[])
        self.assertFalse(prepared.exists())
        _, unprepared = self.run_guide("slides", preparesDecks=False, deckDesign=None, images=[])
        self.assertFalse(unprepared.exists())

    def test_an_unprepared_design_guide_says_so_instead_of_printing_none(self):
        text, request = self.run_guide("design", preparesDecks=True, deckDesign=None, images=[])
        self.assertIn("gathering", text)
        self.assertIn("command of its own", text)
        self.assertNotIn("Images: none", text)
        self.assertTrue(request.is_file())

    def test_the_design_guide_names_the_decision_the_candidates_and_every_image(self):
        directory = Path(tempfile.mkdtemp())
        photo = directory / "greenhouse.jpg"
        Image.new("RGB", (1600, 1000), (40, 120, 60)).save(photo)
        missing = directory / "gone.jpg"
        text, _ = self.run_guide(
            "design",
            preparesDecks=True,
            deckDesign=decided(accent={"fresh": 0.8, "trust": 0.2}, imagery={"photo": 0.9, "icon": 0.1}),
            images=[{"path": str(photo), "name": "greenhouse.jpg", "source": "dataroom", "title": "Greenhouse rows", "summary": "Strawberry rows", "width": 1600, "height": 1000}, {"path": str(missing), "name": "gone.jpg", "source": "dataroom", "width": 10, "height": 10}],
        )
        self.assertIn("accent: fresh (fresh 0.80, trust 0.20)", text)
        self.assertIn("imagery: photo", text)
        self.assertIn("primary: ground", text)
        self.assertIn(f"{photo} (1600x1000, dataroom) Greenhouse rows: Strawberry rows", text)
        self.assertIn(f"not readable from here, so not listed: {missing}", text)
        self.assertIn("Never produce", text)

    def test_the_design_guide_asks_for_the_logo_on_the_cover(self):
        directory = Path(tempfile.mkdtemp())
        profile = directory / "company-profile.json"
        logo = directory / "logo.png"
        mark = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
        mark.paste((20, 40, 120, 255), (40, 20, 160, 80))
        mark.save(logo)
        profile.write_text(json.dumps({"logoImage": "logo.png"}), encoding="utf-8")
        text, _ = self.run_guide("design", company={"en": str(profile)}, preparesDecks=False, deckDesign=None, images=[])
        self.assertIn("<img data-logo>", text)


if __name__ == "__main__":
    unittest.main()
