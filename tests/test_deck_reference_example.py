import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

from render_fixture import can_render


TESTS_PATH = Path(__file__).resolve().parent
OFFICE_PATH = TESTS_PATH.parent / "skills" / "office"
OFFICE_ENTRY = OFFICE_PATH / "scripts" / "office"
DECK_REFERENCE_PATH = OFFICE_PATH / "references" / "deck.md"
SLIDE_PLACEHOLDER = '<!-- one <section data-layout="..."> per slide -->'


def html_blocks(markdown: str) -> list[str]:
    return re.findall(r"```html\n(.*?)```", markdown, re.DOTALL)


def reference_deck() -> str:
    skeleton, layouts = html_blocks(DECK_REFERENCE_PATH.read_text(encoding="utf-8"))[:2]
    return skeleton.replace(SLIDE_PLACEHOLDER, layouts.strip())


def write_referenced_images(deck_source: str, deck_path: Path) -> None:
    for source in re.findall(r'src="([^"]+)"', deck_source):
        image_path = deck_path / source
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (960, 640), (70, 110, 150)).save(image_path)


class ReferenceExampleTest(unittest.TestCase):
    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_the_reference_example_deck_builds_acceptable_as_written(self):
        deck_source = reference_deck()
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory) / "reference"
            deck_path.mkdir()
            (deck_path / "slides.html").write_text(deck_source, encoding="utf-8")
            write_referenced_images(deck_source, deck_path)
            arguments = ["deck", "build", "--format", "all", "--slide-count", str(deck_source.count("<section"))]
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=deck_path)
            envelope = json.loads(completed.stdout)
            check = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "check", str(deck_path / "build" / "reference.pptx")], capture_output=True, text=True).stdout)
        if envelope["details"]["review"]["renderSource"] != "layout":
            self.skipTest("the renderer could not run on this host")
        self.assertTrue(envelope["details"]["acceptance"]["acceptable"], envelope["summary"])
        self.assertEqual([issue["code"] for issue in check["issues"]], [])


FOUR_CARD_DECK = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>네 기능</title></head><body data-theme="corporate">
<section data-layout="cover"><h1>네 기능으로 재고 업무를 줄입니다</h1><p class="meta">이샘플</p></section>
<section data-layout="cards"><h2>네 기능이 재고 업무를 나눠 맡습니다</h2>
  <div class="card"><p class="label">알림</p><h3>품절 전 알림</h3><p>품절 3일 전에 알립니다.</p></div>
  <div class="card"><p class="label">추천</p><h3>발주 추천</h3><p>적정 수량을 제안합니다.</p></div>
  <div class="card"><p class="value">47분</p><h3>확인 시간 절감</h3><p>하루 평균 절감 시간입니다.</p></div>
  <div class="card"><p class="label">보고</p><h3>주간 보고서</h3><p>매주 월요일 아침에 보냅니다.</p></div>
  <p class="takeaway">네 기능 모두 11월에 출시합니다.</p></section>
<section data-layout="closing"><h2>11월 출시를 승인해 주십시오</h2></section>
</body></html>"""


class CardGridTest(unittest.TestCase):
    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_four_cards_form_a_two_by_two_grid_that_fills_the_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory) / "grid"
            deck_path.mkdir()
            (deck_path / "slides.html").write_text(FOUR_CARD_DECK, encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build", "--format", "pptx"], capture_output=True, text=True, cwd=deck_path)
            envelope = json.loads(completed.stdout)
            read = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "read", str(deck_path / "build" / "grid.pptx"), "--slides", "2"], capture_output=True, text=True).stdout)
        if envelope["details"]["review"]["renderSource"] != "layout":
            self.skipTest("the renderer could not run on this host")
        self.assertTrue(envelope["details"]["acceptance"]["acceptable"], envelope["summary"])
        boxes = sorted((shape["box"] for shape in read["details"]["slides"][0]["shapes"] if shape["kind"] == "shape"), key=lambda box: box["w"] * box["h"], reverse=True)[:4]
        self.assertEqual(len({box["x"] for box in boxes}), 2, boxes)
        self.assertEqual(len({box["y"] for box in boxes}), 2, boxes)


if __name__ == "__main__":
    unittest.main()
