from __future__ import annotations

import json
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

from deck.deck_definitions import COVER_MOTIF_DESCRIPTIONS  # noqa: E402
from deck.deck_kit import kit_names  # noqa: E402


SLIDE_WIDTH = 1600
PANEL_LEFT = 984
RING_RADIUS = 342


def cover_deck(cover_attributes: str = "", extra: str = "") -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Cover</title></head><body data-theme="editorial">'
        f'<section data-layout="cover"{cover_attributes}><p class="eyebrow">October 2026</p><h1>Shelves report themselves before they run empty</h1><p class="meta">Sample team</p>{extra}</section>'
        '<section data-layout="statement"><h2>Stock checks take 47 minutes less a day</h2></section></body></html>'
    )


def build_cover(source: str) -> tuple[dict, Image.Image]:
    with tempfile.TemporaryDirectory() as directory:
        deck_path = Path(directory) / "cover"
        deck_path.mkdir()
        (deck_path / "slides.html").write_text(source, encoding="utf-8")
        envelope = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "build/cover.pdf", "slides.html"], capture_output=True, text=True, cwd=deck_path).stdout)
        page = pypdfium2.PdfDocument(envelope["outputPath"])[0].render(scale=4 / 3).to_pil().convert("L")
    return envelope, page


def check_source(source: str) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        (Path(directory) / "slides.html").write_text(source, encoding="utf-8")
        return json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "check", "slides.html"], capture_output=True, text=True, cwd=directory).stdout)


def panel_tone(page: Image.Image) -> int:
    return page.getpixel((1500, 300))


def background_tone(page: Image.Image) -> int:
    return page.getpixel((60, 450))


def ring_contrast(page: Image.Image) -> int:
    ring_point = (round(SLIDE_WIDTH - RING_RADIUS * 0.7071), round(900 - RING_RADIUS * 0.7071))
    brightest = max(page.getpixel((ring_point[0] + dx, ring_point[1] + dy)) for dx in range(-3, 4) for dy in range(-3, 4))
    return brightest - panel_tone(page)


class CoverMotifGuideTest(unittest.TestCase):
    def test_the_guide_describes_every_motif_the_kit_draws(self):
        self.assertEqual(tuple(COVER_MOTIF_DESCRIPTIONS), kit_names("coverMotifs"))

    def test_the_check_refuses_a_motif_the_kit_would_not_draw(self):
        for attributes, extra in ((' data-motif="waves"', ""), ("", '<p class="lead" data-motif="rings">Lead</p>')):
            codes = [issue["code"] for issue in check_source(cover_deck(attributes, extra))["issues"]]
            self.assertIn("MOTIF_NOT_DRAWN", codes, attributes + extra)
        codes = [issue["code"] for issue in check_source(cover_deck(' data-motif="rings"'))["issues"]]
        self.assertNotIn("MOTIF_NOT_DRAWN", codes)


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class CoverMotifRenderTest(unittest.TestCase):
    def test_a_cover_without_a_chosen_motif_or_photo_is_text_on_the_background(self):
        _, page = build_cover(cover_deck())
        self.assertLessEqual(abs(panel_tone(page) - background_tone(page)), 2)
        self.assertLessEqual(ring_contrast(page), 2)

    def test_the_rings_are_drawn_only_when_chosen(self):
        _, page = build_cover(cover_deck(' data-motif="rings"'))
        self.assertGreater(abs(panel_tone(page) - background_tone(page)), 40)
        self.assertGreater(ring_contrast(page), 12)

    def test_a_plain_panel_is_a_choice_too(self):
        _, page = build_cover(cover_deck(' data-motif="panel"'))
        self.assertGreater(abs(panel_tone(page) - background_tone(page)), 40)
        self.assertLessEqual(ring_contrast(page), 2)


if __name__ == "__main__":
    unittest.main()
