import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
import pypdfium2

from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
DECK = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>사진 시험</title></head><body data-theme="editorial">
<section data-layout="cover"><p class="eyebrow">2026년 10월</p><h1>진열대가 비기 전에 알려 드립니다</h1><p class="meta">사업개발팀 최견본</p><img src="images/shelves.png" alt="진열대"></section>
<section data-layout="statement"><h2>재고 확인이 하루 47분 줄어듭니다</h2></section>
</body></html>"""
PHOTO_SIZE = (4000, 2800)
IMAGE_PATTERN = re.compile(rb"/Subtype\s*/Image(.{0,400}?)stream", re.S)


def write_photo(path: Path) -> None:
    path.parent.mkdir(parents=True)
    photo = Image.effect_noise(PHOTO_SIZE, 64).convert("RGB")
    photo.save(path)


def embedded_images(pdf_path: Path) -> list[dict]:
    images = []
    for match in IMAGE_PATTERN.finditer(pdf_path.read_bytes()):
        dictionary = match.group(1)
        width = re.search(rb"/Width\s+(\d+)", dictionary)
        height = re.search(rb"/Height\s+(\d+)", dictionary)
        images.append({"width": int(width.group(1)) if width else 0, "height": int(height.group(1)) if height else 0, "jpeg": b"DCTDecode" in dictionary})
    return images


class PdfImageTest(unittest.TestCase):
    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_a_photo_is_embedded_at_twice_its_drawn_size_as_jpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            (deck_path / "slides.html").write_text(DECK, encoding="utf-8")
            write_photo(deck_path / "images" / "shelves.png")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build"], capture_output=True, text=True, cwd=deck_path)
            envelope = json.loads(completed.stdout)
            images = [image for image in embedded_images(Path(envelope["outputPath"])) if image["width"] > 100]
        self.assertTrue(images, envelope["summary"])
        self.assertTrue(all(image["jpeg"] for image in images))
        self.assertTrue(all(image["height"] <= 2 * 900 + 2 for image in images), images)


    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_the_cover_rings_reach_the_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            (deck_path / "slides.html").write_text(DECK.replace('<img src="images/shelves.png" alt="진열대">', ""), encoding="utf-8")
            envelope = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build"], capture_output=True, text=True, cwd=deck_path).stdout)
            page = pypdfium2.PdfDocument(envelope["outputPath"])[0].render(scale=4 / 3).to_pil().convert("L")
        panel = page.getpixel((1500, 300))
        ring_point = (round(1600 - 342 * 0.7071), round(900 - 342 * 0.7071))
        brightest = max(page.getpixel((ring_point[0] + dx, ring_point[1] + dy)) for dx in range(-3, 4) for dy in range(-3, 4))
        self.assertGreater(brightest - panel, 12)


    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_the_kit_draws_grouped_thousands_as_the_check_reads_them(self):
        chart = '<section data-layout="chart"><h2>매출이 늘었습니다</h2><figure data-chart="column" data-labels="1월, 2월" data-values="1,200, 1,350" data-unit="만원"></figure></section>'
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            (deck_path / "slides.html").write_text(DECK.replace('<section data-layout="statement">', chart + '<section data-layout="statement">'), encoding="utf-8")
            write_photo(deck_path / "images" / "shelves.png")
            subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build", "--format", "pptx"], capture_output=True, text=True, cwd=deck_path)
            layout = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))
        chart = layout["slides"][1]["charts"][0]
        self.assertEqual((chart["series"][0]["values"], chart["unit"]), ([1200, 1350], "만원"))


if __name__ == "__main__":
    unittest.main()
