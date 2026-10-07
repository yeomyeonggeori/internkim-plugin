from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from host_fixture import FakeHost  # noqa: E402
from task_context_fixture import environment_with_context, write_context_at  # noqa: E402
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


FACTS = {"requester": {"name": "이샘플", "email": "a@example.com"}, "today": "2026-10-04", "request": ["딸기 농장 소개 발표자료 만들어 줘"]}


def typeface_answer(body: dict) -> dict:
    return {"answers": {name: {"type": "choice", "choice": "freesentation", "probabilities": {"freesentation": 0.8, "paperlogy": 0.2}} for name in body["questions"]}, "modelName": "jev", "usage": {"costUSD": 0.001}}


class DeckPreparationGuideTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.state = self.directory / "task" / "office"

    def run_guide(self, topic: str, facts: dict | None = None, prepared: dict | None = None) -> str:
        context_path = write_context_at(self.directory / "task" / "task-context.json", FACTS | (facts or {}))
        if prepared is not None:
            self.state.mkdir(parents=True, exist_ok=True)
            (self.state / "deck-preparation.json").write_text(json.dumps(prepared), encoding="utf-8")
        return subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", topic], capture_output=True, text=True, env=environment_with_context(context_path), check=True).stdout

    def data_room_tools(self, photo: Path) -> dict:
        listing = {"result": {"documents": [{"documentID": "p-1", "title": "Greenhouse rows", "summary": "Strawberry rows", "date": "2026-08-02", "categoryCode": "OP", "filePath": "photos/greenhouse.jpg"}]}, "files": [], "isError": False}
        download = {"result": {"downloadURL": photo.as_uri()}, "files": [], "isError": False}
        return {"company_info_get": lambda body: {"result": {}, "files": [], "isError": False}, "company_document_list": lambda body: listing, "company_document_download": lambda body: download}

    def test_the_design_guide_prepares_the_deck_once_with_the_data_room_photos(self):
        photo = self.directory / "source.jpg"
        Image.new("RGB", (1600, 1000), (40, 120, 60)).save(photo)
        with FakeHost(decide=typeface_answer, tools=self.data_room_tools(photo)) as host:
            text = self.run_guide("design")
            again = self.run_guide("design")
        asked = host.requests_to("decide")
        self.assertEqual(len(asked), 1)
        self.assertEqual(list(asked[0]["questions"]), ["type"])
        self.assertEqual(asked[0]["state"]["request"], FACTS["request"])
        self.assertEqual([image["name"] for image in asked[0]["state"]["images"]], ["greenhouse.jpg"])
        kept = self.state / "deck-images" / "greenhouse.jpg"
        self.assertTrue(kept.is_file())
        for answer in (text, again):
            self.assertIn("Typeface: Freesentation", answer)
            self.assertIn(f"{kept} (1600x1000, dataroom, OP, 2026-08-02) Greenhouse rows: Strawberry rows", answer)

    def test_a_host_without_a_script_host_prepares_nothing_and_sets_paperlogy(self):
        text = self.run_guide("design")
        self.assertIn("Typeface: Paperlogy", text)
        self.assertIn("Photos: none", text)
        self.assertFalse((self.state / "deck-preparation.json").exists())

    def test_the_slides_guide_points_at_the_design_guide_and_asks_nothing(self):
        with FakeHost(decide=typeface_answer) as host:
            text = self.run_guide("slides")
        self.assertIn("office guide design", text)
        self.assertEqual(host.requests, [])

    def test_the_design_guide_names_the_typeface_the_stages_and_every_image(self):
        photo = self.directory / "greenhouse.jpg"
        Image.new("RGB", (1600, 1000), (40, 120, 60)).save(photo)
        missing = self.directory / "gone.jpg"
        prepared = {
            "deckDesign": decided(type={"freesentation": 0.8, "paperlogy": 0.2}),
            "images": [{"path": str(photo), "name": "greenhouse.jpg", "source": "dataroom", "title": "Greenhouse rows", "summary": "Strawberry rows", "width": 1600, "height": 1000}, {"path": str(missing), "name": "gone.jpg", "source": "dataroom", "width": 10, "height": 10}],
        }
        text = self.run_guide("design", prepared=prepared)
        self.assertIn("Typeface: Freesentation", text)
        for stage in ("Stage 1, the style sheet", "Stage 2, the outline", "Stage 3, pages", "Layout library", "Avoid"):
            self.assertIn(stage, text)
        self.assertIn(f"{photo} (1600x1000, dataroom) Greenhouse rows: Strawberry rows", text)
        self.assertIn(f"not readable from here, so not listed: {missing}", text)

    def test_the_design_guide_says_the_build_places_the_logo(self):
        profile = self.directory / "company-profile.json"
        logo = self.directory / "logo.png"
        mark = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
        mark.paste((20, 40, 120, 255), (40, 20, 160, 80))
        mark.save(logo)
        profile.write_text(json.dumps({"logoImage": "logo.png"}), encoding="utf-8")
        text = self.run_guide("design", facts={"company": {"en": str(profile)}})
        self.assertIn("The build places it on the cover and the closing page", text)
        self.assertIn("write no <img data-logo>", text)


if __name__ == "__main__":
    unittest.main()
