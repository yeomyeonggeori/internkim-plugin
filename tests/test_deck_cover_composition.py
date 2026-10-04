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

from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from core.host_contract import RUNTIME_CONTEXT_VARIABLE  # noqa: E402


COVER_PARTS = '<p class="eyebrow">October 2026</p><h1>Shelves report themselves before they run empty</h1><p class="meta">Sample team</p>'
PANEL_POINT = (1520, 820)
COVER_LOGO_REGION = (1300, 40, 1600, 160)
FOOTER_LOGO_REGION = (1200, 800, 1600, 900)
TEXT_SIDE_POINT = (60, 450)
LOGO_COLOR = (20, 110, 200)


def cover_deck(section_attributes: str = "", extra: str = "") -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Cover</title></head><body data-palette="trust" data-tone="formal">'
        f'<section data-layout="cover"{section_attributes}>{COVER_PARTS}{extra}</section>'
        '<section data-layout="statement"><h2>Stock checks take 47 minutes less a day</h2></section></body></html>'
    )


def check_codes(source: str) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        (Path(directory) / "slides.html").write_text(source, encoding="utf-8")
        envelope = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "check", "slides.html"], capture_output=True, text=True, cwd=directory).stdout)
    return [issue["code"] for issue in envelope["issues"]]


def build(source: str, photo_size: tuple[int, int] | None = None, logo: bool = False) -> tuple[dict, list[Image.Image]]:
    with tempfile.TemporaryDirectory() as directory:
        deck_path = Path(directory)
        (deck_path / "slides.html").write_text(source, encoding="utf-8")
        if photo_size:
            (deck_path / "images").mkdir()
            Image.new("RGB", photo_size, (200, 180, 40)).save(deck_path / "images" / "photo.jpg")
        environment = dict(os.environ)
        environment.pop(RUNTIME_CONTEXT_VARIABLE, None)
        if logo:
            environment[RUNTIME_CONTEXT_VARIABLE] = str(company_context(deck_path))
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "build/cover.pdf", "slides.html"], capture_output=True, text=True, cwd=deck_path, env=environment)
        envelope = json.loads(completed.stdout)
        document = pypdfium2.PdfDocument(envelope["outputPath"])
        pages = [document[index].render(scale=4 / 3).to_pil().convert("RGB") for index in range(len(document))]
    return envelope, pages


def company_context(deck_path: Path) -> Path:
    company_path = deck_path / "company"
    company_path.mkdir()
    logo = Image.new("RGBA", (240, 80), (0, 0, 0, 0))
    logo.paste(LOGO_COLOR, (20, 10, 220, 70))
    logo.save(company_path / "logo.png")
    (company_path / "company-profile.json").write_text(json.dumps({"name": "Sample", "logoImage": "logo.png"}), encoding="utf-8")
    context_path = company_path / "office-runtime-context.json"
    context_path.write_text(json.dumps({"requester": {"name": "", "email": ""}, "today": "2026-10-04", "company": {"en": str(company_path / "company-profile.json")}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": False}), encoding="utf-8")
    return context_path


def brightness(page: Image.Image, point: tuple[int, int]) -> float:
    return sum(page.getpixel(point)) / 3


def has_color_near(page: Image.Image, color: tuple[int, int, int]) -> bool:
    return any(all(abs(channel - wanted) <= 40 for channel, wanted in zip(pixel, color)) for _, pixel in page.getcolors(maxcolors=1 << 20) or [])


class CoverCheckTest(unittest.TestCase):
    def test_a_cover_carries_one_of_a_photo_figures_or_an_icon(self):
        figures = '<div class="kpi"><p class="value">47 min</p><p class="label">saved a day</p></div>'
        self.assertNotIn("COVER_MIXED", check_codes(cover_deck(extra=figures)))
        self.assertNotIn("COVER_MIXED", check_codes(cover_deck(' data-icon="warehouse"')))
        self.assertIn("COVER_MIXED", check_codes(cover_deck(' data-icon="warehouse"', figures)))

    def test_a_cover_icon_must_be_one_the_kit_ships(self):
        self.assertIn("ICON_UNKNOWN", check_codes(cover_deck(' data-icon="robot-arm"')))

    def test_no_motif_is_drawn_by_name_any_more(self):
        self.assertNotIn("MOTIF_NOT_DRAWN", check_codes(cover_deck(' data-motif="rings"')))


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class CoverRenderTest(unittest.TestCase):
    def test_a_cover_without_a_carrier_is_its_title_alone(self):
        _, pages = build(cover_deck(' data-motif="rings"'))
        self.assertLessEqual(abs(brightness(pages[0], PANEL_POINT) - brightness(pages[0], TEXT_SIDE_POINT)), 3)

    def test_figures_on_the_cover_fill_a_dark_panel(self):
        _, pages = build(cover_deck(extra='<div class="kpi"><p class="value">47 min</p><p class="label">saved a day</p></div>'))
        self.assertLess(brightness(pages[0], PANEL_POINT), 90)
        self.assertGreater(brightness(pages[0], TEXT_SIDE_POINT), 200)

    def test_an_icon_on_the_cover_fills_an_accent_panel(self):
        _, pages = build(cover_deck(' data-icon="warehouse"'))
        self.assertLess(brightness(pages[0], (1100, 100)), 200)

    def test_a_wide_photo_fills_the_cover_under_a_shade_and_a_tall_one_a_panel(self):
        _, wide = build(cover_deck(extra='<img src="images/photo.jpg" alt="">'), photo_size=(2400, 1350))
        self.assertLess(brightness(wide[0], TEXT_SIDE_POINT), 90)
        self.assertGreater(brightness(wide[0], (1580, 450)), 120)
        _, tall = build(cover_deck(extra='<img src="images/photo.jpg" alt="">'), photo_size=(900, 1300))
        self.assertGreater(brightness(tall[0], TEXT_SIDE_POINT), 200)

    def test_a_small_photo_is_reported_soft(self):
        envelope, _ = build(cover_deck(extra='<img src="images/photo.jpg" alt="">'), photo_size=(480, 270))
        self.assertIn("IMAGE_LOW_RESOLUTION", [issue["code"] for issue in envelope["issues"]])

    def test_the_company_logo_is_placed_on_the_cover_and_in_the_footers(self):
        _, pages = build(cover_deck(), logo=True)
        self.assertTrue(has_color_near(pages[0].crop(COVER_LOGO_REGION), LOGO_COLOR))
        self.assertTrue(has_color_near(pages[1].crop(FOOTER_LOGO_REGION), LOGO_COLOR))
        _, unbranded = build(cover_deck())
        self.assertFalse(has_color_near(unbranded[0].crop(COVER_LOGO_REGION), LOGO_COLOR))
        self.assertFalse(has_color_near(unbranded[1].crop(FOOTER_LOGO_REGION), LOGO_COLOR))


if __name__ == "__main__":
    unittest.main()
