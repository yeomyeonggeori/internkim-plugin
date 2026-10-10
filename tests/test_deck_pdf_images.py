import json
from pathlib import Path
import re
import tempfile
import unittest

from PIL import Image

from free_deck_fixture import build_pptx, run_office_json, write_free_deck
from render_fixture import can_render


PHOTO_STYLE = """
.cover-photo { position: absolute; right: 0; top: 0; width: 800px; height: 900px; object-fit: cover; }
"""
COVER = '<img class="cover-photo" src="images/shelves.png" alt="진열대"><h1>진열대가 비기 전에 알려 드립니다</h1><p>사업개발팀 최견본</p>'
STATEMENT = '<h2>재고 확인이 하루 47분 줄어듭니다</h2><table style="flex: 1"><tr><th>매장</th><th>하루 절감</th></tr><tr><td>강남점</td><td>52분</td></tr><tr><td>판교점</td><td>41분</td></tr></table>'
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
            deck_path = write_free_deck(Path(directory), [COVER, STATEMENT], PHOTO_STYLE)
            write_photo(deck_path / "images" / "shelves.png")
            envelope = run_office_json(["create", "build/deck.pdf", "."], deck_path)
            images = [image for image in embedded_images(Path(envelope["outputPath"])) if image["width"] > 100]
        self.assertTrue(images, envelope["summary"])
        self.assertTrue(all(image["jpeg"] for image in images))
        self.assertTrue(all(image["height"] <= 2 * 900 + 2 for image in images), images)

    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_the_build_draws_grouped_thousands_as_the_check_reads_them(self):
        chart = '<h2>매출이 늘었습니다</h2><figure data-chart="column" data-labels="1월, 2월" data-values="1,200, 1,350" data-unit="만원"></figure>'
        with tempfile.TemporaryDirectory() as directory:
            deck_path = write_free_deck(Path(directory), [COVER, chart, STATEMENT], PHOTO_STYLE)
            write_photo(deck_path / "images" / "shelves.png")
            build_pptx(deck_path)
            layout = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))
        chart = layout["slides"][1]["charts"][0]
        self.assertEqual((chart["series"][0]["values"], chart["units"]), ([1200, 1350], ["만원"]))


if __name__ == "__main__":
    unittest.main()
