from __future__ import annotations

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

from core.host_contract import HOST_CONTRACT, RUNTIME_CONTEXT_VARIABLE  # noqa: E402
from deck.deck_logo import read_logo  # noqa: E402
from deck.deck_photos import focal_point, focus_photos  # noqa: E402
from deck.typeface import TYPEFACE, decided_type  # noqa: E402


def decided(**options_by_axis: dict[str, float]) -> dict:
    return {"choices": {axis: {"option": max(probabilities, key=probabilities.get), "probabilities": probabilities} for axis, probabilities in options_by_axis.items()}}


class TypefaceTest(unittest.TestCase):
    def test_each_type_choice_names_bundled_fonts(self):
        from fonts.registry import bundled_family

        for faces in TYPEFACE["types"].values():
            for role in ("display", "body"):
                self.assertIsNotNone(bundled_family(faces[role]), faces[role])
            for weight in faces["weights"]:
                self.assertIn(weight, [face.weight for face in bundled_family(faces["display"]).faces])

    def test_an_unsure_or_unknown_type_decision_falls_back_to_paperlogy(self):
        self.assertEqual(decided_type(decided(type={"a2z": 0.9, "paperlogy": 0.1})), "a2z")
        self.assertEqual(decided_type(decided(type={"a2z": 0.3, "paperlogy": 0.2})), "paperlogy")
        self.assertEqual(decided_type(decided(type={"helvetica": 1.0})), "paperlogy")
        self.assertEqual(decided_type(None), "paperlogy")


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
        self.assertEqual(Path(json.loads(request.read_text(encoding="utf-8"))["design"]).name, "typeface.json")
        _, prepared = self.run_guide("slides", preparesDecks=True, deckDesign=decided(type={"paperlogy": 1.0}), images=[])
        self.assertFalse(prepared.exists())
        _, unprepared = self.run_guide("slides", preparesDecks=False, deckDesign=None, images=[])
        self.assertFalse(unprepared.exists())

    def test_an_unprepared_design_guide_says_so_instead_of_printing_none(self):
        text, request = self.run_guide("design", preparesDecks=True, deckDesign=None, images=[])
        self.assertIn("gathering", text)
        self.assertIn("command of its own", text)
        self.assertNotIn("Images: none", text)
        self.assertTrue(request.is_file())

    def test_the_design_guide_names_the_typeface_the_stages_and_every_image(self):
        directory = Path(tempfile.mkdtemp())
        photo = directory / "greenhouse.jpg"
        Image.new("RGB", (1600, 1000), (40, 120, 60)).save(photo)
        missing = directory / "gone.jpg"
        text, _ = self.run_guide(
            "design",
            preparesDecks=True,
            deckDesign=decided(type={"freesentation": 0.8, "paperlogy": 0.2}),
            images=[{"path": str(photo), "name": "greenhouse.jpg", "source": "dataroom", "title": "Greenhouse rows", "summary": "Strawberry rows", "width": 1600, "height": 1000}, {"path": str(missing), "name": "gone.jpg", "source": "dataroom", "width": 10, "height": 10}],
        )
        self.assertIn("Typeface: Freesentation", text)
        for stage in ("Stage 1, the style sheet", "Stage 2, the outline", "Stage 3, pages", "Layout library", "Avoid"):
            self.assertIn(stage, text)
        self.assertIn(f"{photo} (1600x1000, dataroom) Greenhouse rows: Strawberry rows", text)
        self.assertIn(f"not readable from here, so not listed: {missing}", text)

    def test_the_design_guide_says_the_build_places_the_logo(self):
        directory = Path(tempfile.mkdtemp())
        profile = directory / "company-profile.json"
        logo = directory / "logo.png"
        mark = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
        mark.paste((20, 40, 120, 255), (40, 20, 160, 80))
        mark.save(logo)
        profile.write_text(json.dumps({"logoImage": "logo.png"}), encoding="utf-8")
        text, _ = self.run_guide("design", company={"en": str(profile)}, preparesDecks=False, deckDesign=None, images=[])
        self.assertIn("The build places it on the cover and the closing page", text)
        self.assertIn("write no <img data-logo>", text)


if __name__ == "__main__":
    unittest.main()
