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

from design_gate_fixture import design_markdown
from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from core.host_contract import RUNTIME_CONTEXT_VARIABLE  # noqa: E402


LOGO_COLOR = (20, 60, 150)
PHOTO_COLOR = (200, 120, 40)
STYLE = """
body { margin: 0; }
section { position: relative; background: var(--ground); color: var(--text); font-family: var(--font-body); }
h1 { position: absolute; left: 96px; top: 380px; margin: 0; font-size: 56px; }
img[data-logo] { position: absolute; left: 96px; top: 60px; height: 64px; }
.photo { position: absolute; right: 0; top: 0; width: 640px; height: 900px; object-fit: cover; }
.dark { background: #14213D; }
"""


def deck(first_slide: str, second_slide: str = '<h1>Stock checks take 47 minutes less a day</h1>') -> str:
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Logo</title><style>{STYLE}</style></head><body><section>{first_slide}</section><section>{second_slide}</section></body></html>'


def company_context(directory: Path) -> Path:
    company_path = directory / "company"
    company_path.mkdir()
    logo = Image.new("RGBA", (240, 80), (0, 0, 0, 0))
    logo.paste(LOGO_COLOR + (255,), (20, 10, 220, 70))
    logo.save(company_path / "logo.png")
    (company_path / "company-profile.json").write_text(json.dumps({"name": "Sample", "logoImage": "logo.png"}), encoding="utf-8")
    context_path = company_path / "office-runtime-context.json"
    context_path.write_text(json.dumps({"requester": {"name": "", "email": ""}, "today": "2026-10-04", "company": {"en": str(company_path / "company-profile.json")}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": False}), encoding="utf-8")
    return context_path


def run(arguments: list[str], deck_path: Path, with_logo: bool) -> dict:
    environment = dict(os.environ)
    environment.pop(RUNTIME_CONTEXT_VARIABLE, None)
    if with_logo:
        environment[RUNTIME_CONTEXT_VARIABLE] = str(company_context(deck_path))
    return json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=deck_path, env=environment).stdout)


def prepare(directory: str, source: str, with_photo: bool = False) -> Path:
    deck_path = Path(directory)
    (deck_path / "DESIGN.md").write_text(design_markdown(), encoding="utf-8")
    (deck_path / "slides.html").write_text(source, encoding="utf-8")
    if with_photo:
        (deck_path / "images").mkdir()
        Image.new("RGB", (800, 1200), PHOTO_COLOR).save(deck_path / "images" / "photo.jpg")
    return deck_path


def pages_of(envelope: dict) -> list[Image.Image]:
    document = pypdfium2.PdfDocument(envelope["outputPath"])
    return [document[index].render(scale=4 / 3).to_pil().convert("RGB") for index in range(len(document))]


def has_color_near(page: Image.Image, color: tuple[int, int, int], region: tuple[int, int, int, int]) -> bool:
    return any(all(abs(channel - wanted) <= 40 for channel, wanted in zip(pixel, color)) for _, pixel in (page.crop(region).getcolors(maxcolors=1 << 20) or []))


class LogoCheckTest(unittest.TestCase):
    def test_a_cover_without_the_logo_is_refused_when_the_company_has_one(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = run(["check", "slides.html"], prepare(directory, deck("<h1>Shelves report themselves</h1>")), with_logo=True)
            self.assertIn("LOGO_UNUSED", [issue["code"] for issue in envelope["issues"]])
            self.assertEqual(envelope["status"], "error")

    def test_a_cover_with_the_logo_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = run(["check", "slides.html"], prepare(directory, deck("<img data-logo><h1>Shelves report themselves</h1>")), with_logo=True)
            self.assertNotIn("LOGO_UNUSED", [issue["code"] for issue in envelope["issues"]])

    def test_a_company_without_a_logo_is_never_asked_for_one(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = run(["check", "slides.html"], prepare(directory, deck("<h1>Shelves report themselves</h1>")), with_logo=False)
            self.assertNotIn("LOGO_UNUSED", [issue["code"] for issue in envelope["issues"]])


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class LogoAndPhotoRenderTest(unittest.TestCase):
    def test_the_logo_is_drawn_where_the_deck_placed_it(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = run(["create", "build/logo.pdf", "slides.html"], prepare(directory, deck("<img data-logo><h1>Shelves report themselves</h1>")), with_logo=True)
            pages = pages_of(envelope)
            self.assertTrue(has_color_near(pages[0], LOGO_COLOR, (96, 60, 400, 130)))

    def test_a_logo_the_deck_places_on_a_dark_slide_sits_on_a_white_plate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = deck('<div class="dark" style="position:absolute;inset:0"><img data-logo></div><h1>Dark cover</h1>')
            envelope = run(["create", "build/logo.pdf", "slides.html"], prepare(directory, source), with_logo=True)
            page = pages_of(envelope)[0]
            self.assertTrue(has_color_near(page, (255, 255, 255), (96, 60, 400, 130)))
            self.assertTrue(has_color_near(page, LOGO_COLOR, (96, 60, 400, 130)))

    def test_a_listed_photo_is_drawn_in_its_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            source = deck('<img class="photo" src="images/photo.jpg" alt=""><h1>Shelves report themselves</h1>')
            envelope = run(["create", "build/photo.pdf", "slides.html"], prepare(directory, source, with_photo=True), with_logo=False)
            self.assertTrue(has_color_near(pages_of(envelope)[0], PHOTO_COLOR, (1000, 100, 1500, 800)))


if __name__ == "__main__":
    unittest.main()
