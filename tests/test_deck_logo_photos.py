from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
import pypdfium2

from staged_deck_fixture import write_staged_deck
from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from task_context_fixture import CONTEXT_VARIABLE, write_context_at  # noqa: E402


LOGO_COLOR = (20, 60, 150)
PHOTO_COLOR = (200, 120, 40)
STYLE = """
section { position: relative; display: block; padding: 0; }
h1 { position: absolute; left: 96px; top: 380px; margin: 0; font-size: 56px; }
.photo { position: absolute; right: 0; top: 0; width: 640px; height: 900px; object-fit: cover; }
.filler { position: absolute; left: 96px; right: 560px; top: 160px; bottom: 96px; background: var(--surface); padding: 40px; font-size: 28px; }
.filler, h1 { color: var(--text); }
"""


FILLER = '<div class="filler"><p>Shelf checks, counted by sensors instead of people.</p></div>'
DARK_COVER = {"backgrounds": {"cover": "#14213D"}}


def deck(first_slide: str, second_slide: str | None = '<h1>Stock checks take 47 minutes less a day</h1>', middle: str | None = None) -> list[str]:
    return [f"{FILLER}{slide}" for slide in (first_slide, middle, second_slide) if slide is not None]


def company_context(directory: Path, images: list[str]) -> Path:
    company_path = directory / "company"
    company_path.mkdir()
    logo = Image.new("RGBA", (240, 80), (0, 0, 0, 0))
    logo.paste(LOGO_COLOR + (255,), (20, 10, 220, 70))
    logo.save(company_path / "logo.png")
    (company_path / "company-profile.json").write_text(json.dumps({"name": "Sample", "logoImage": "logo.png"}), encoding="utf-8")
    context_path = write_context_at(company_path / "task-context.json", {"today": "2026-10-04", "company": {"en": str(company_path / "company-profile.json")}})
    state = company_path / "office"
    state.mkdir()
    (state / "deck-preparation.json").write_text(json.dumps({"images": [{"path": image} for image in images]}), encoding="utf-8")
    return context_path


def run(arguments: list[str], deck_path: Path, with_logo: bool) -> dict:
    environment = dict(os.environ)
    environment.pop(CONTEXT_VARIABLE, None)
    images = [str(path) for path in sorted((deck_path / "images").glob("*.jpg"))]
    if with_logo or images:
        context_path = company_context(deck_path, images)
        if not with_logo:
            (context_path.parent / "logo.png").unlink()
        environment[CONTEXT_VARIABLE] = str(context_path)
    return json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=deck_path, env=environment).stdout)


def prepare(directory: str, sections: list[str], design: dict | None = None, photos: dict[int, list[str]] | None = None) -> Path:
    deck_path = Path(directory)
    if photos:
        (deck_path / "images").mkdir()
        Image.new("RGB", (800, 1200), PHOTO_COLOR).save(deck_path / "images" / "photo.jpg")
    return write_staged_deck(deck_path, sections, STYLE, design, photos)


def pages_of(envelope: dict) -> list[Image.Image]:
    document = pypdfium2.PdfDocument(envelope["outputPath"])
    return [document[index].render(scale=4 / 3).to_pil().convert("RGB") for index in range(len(document))]


def has_color_near(page: Image.Image, color: tuple[int, int, int], region: tuple[int, int, int, int]) -> bool:
    return any(all(abs(channel - wanted) <= 40 for channel, wanted in zip(pixel, color)) for _, pixel in (page.crop(region).getcolors(maxcolors=1 << 20) or []))


class LogoCheckTest(unittest.TestCase):
    def test_a_cover_needs_no_logo_markup_because_the_build_places_the_logo(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = run(["check", "."], prepare(directory, deck("<h1>Shelves report themselves</h1>")), with_logo=True)
            self.assertNotIn("LOGO_UNUSED", [issue["code"] for issue in envelope["issues"]])
            self.assertNotEqual(envelope["status"], "error", envelope["summary"])

    def test_a_company_without_a_logo_is_never_asked_for_one(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = run(["check", "."], prepare(directory, deck("<h1>Shelves report themselves</h1>")), with_logo=False)
            self.assertNotIn("LOGO_UNUSED", [issue["code"] for issue in envelope["issues"]])


BOTTOM_LEFT = (40, 780, 420, 880)
BOTTOM_RIGHT = (1180, 780, 1560, 880)
TOP_RIGHT = (1180, 20, 1560, 120)
WHOLE_PAGE = (0, 0, 1600, 900)


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class LogoAndPhotoRenderTest(unittest.TestCase):
    def pages(self, sections: list[str], with_logo: bool = True, design: dict | None = None) -> list:
        with tempfile.TemporaryDirectory() as directory:
            return pages_of(run(["create", "build/logo.pdf", "."], prepare(directory, sections, design), with_logo=with_logo))

    def test_the_build_places_the_logo_on_the_cover_and_the_closing_slide(self):
        pages = self.pages(deck("<h1>Shelves report themselves</h1>"))
        self.assertTrue(has_color_near(pages[0], LOGO_COLOR, BOTTOM_LEFT))
        self.assertTrue(has_color_near(pages[1], LOGO_COLOR, BOTTOM_LEFT))

    def test_a_logo_the_deck_places_itself_is_dropped_and_no_middle_slide_carries_one(self):
        pages = self.pages(deck("<h1>Cover</h1>", middle="<h1>Middle</h1><img data-logo>"))
        self.assertEqual([has_color_near(page, LOGO_COLOR, WHOLE_PAGE) for page in pages], [True, False, True])

    def test_a_one_slide_deck_carries_the_logo_once(self):
        pages = self.pages(deck("<h1>Only slide</h1>", second_slide=None))
        self.assertEqual(len(pages), 1)
        self.assertTrue(has_color_near(pages[0], LOGO_COLOR, WHOLE_PAGE))

    def test_the_logo_moves_to_a_corner_that_no_text_covers(self):
        covering = '<h1 style="top: 790px; left: 40px">A title standing where the logo would sit</h1>'
        pages = self.pages(deck(covering))
        self.assertFalse(has_color_near(pages[0], LOGO_COLOR, BOTTOM_LEFT))
        self.assertTrue(has_color_near(pages[0], LOGO_COLOR, BOTTOM_RIGHT) or has_color_near(pages[0], LOGO_COLOR, TOP_RIGHT))

    def test_a_logo_on_a_dark_slide_sits_on_a_white_plate(self):
        pages = self.pages(deck("<h1>Dark cover</h1>"), design=DARK_COVER)
        self.assertTrue(has_color_near(pages[0], (255, 255, 255), BOTTOM_LEFT))
        self.assertTrue(has_color_near(pages[0], LOGO_COLOR, BOTTOM_LEFT))

    def test_a_listed_photo_is_drawn_in_its_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            photo_path = str(Path(directory) / "images" / "photo.jpg")
            sections = deck(f'<img class="photo" src="{photo_path}" alt=""><h1>Shelves report themselves</h1>')
            envelope = run(["create", "build/photo.pdf", "."], prepare(directory, sections, photos={1: [photo_path]}), with_logo=False)
            self.assertNotEqual(envelope["status"], "error", envelope["summary"])
            self.assertTrue(has_color_near(pages_of(envelope)[0], PHOTO_COLOR, (1000, 100, 1500, 800)))


if __name__ == "__main__":
    unittest.main()
