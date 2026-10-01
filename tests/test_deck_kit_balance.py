import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from deck.deck_kit import kit_length, slide_size  # noqa: E402


COVER_SECTION = """<section data-layout="cover">
  <p class="eyebrow">주식회사 예시랩 2026년 3분기 실적 보고</p>
  <h1>분기 매출 <em>41.3억 원</em>, 목표 40억을 돌파했습니다</h1>
  <p class="lead">클라우드 중심의 매출 성장과 수익률 개선을 보고합니다.</p>
  <p class="meta">발표 박예시 본부장 · 2026년 10월 1일</p>
</section>
"""
COVER_DECK = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>표지</title></head><body data-theme="corporate">
""" + COVER_SECTION + "</body></html>"
INDENTED_DECK = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>들여쓰기</title>
<style>
body { margin: 0; font-family: sans-serif; }
section { width: 1600px; height: 900px; box-sizing: border-box; padding: 80px; background: #fff; }
.box { display: flex; flex-direction: column; font-size: 24px; }
.box > p:first-child { font-size: 40px; }
.box > p + p { font-size: 30px; }
</style></head><body>
<section>
  <div class="box">
    <p>첫째줄</p>
    <p>둘째줄</p>
  </div>
</section>
</body></html>"""



def build(directory: Path, source: str, output_format: str) -> dict:
    (directory / "slides.html").write_text(source, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build", "--format", output_format], capture_output=True, text=True, cwd=directory)
    return json.loads(completed.stdout)


def drawn_sizes(pdf_path: Path, text: str, page_index: int) -> list[float]:
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_index]
        pixels_per_point = slide_size()[0] / page.width
        footer_top = slide_size()[1] - kit_length("footer-height")
        words = page.extract_words(extra_attrs=["size"])
        return [word["size"] * pixels_per_point for word in words if text in word["text"] and word["bottom"] * pixels_per_point < footer_top]


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class IndentedMarkupTest(unittest.TestCase):
    def test_indentation_between_flex_items_does_not_change_which_selectors_match(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = build(Path(directory), INDENTED_DECK, "pdf")
            if envelope["details"]["review"]["renderSource"] != "layout":
                self.skipTest("the renderer could not run on this host")
            pdf_path = Path(directory) / "build" / f"{Path(directory).name}.pdf"
            self.assertAlmostEqual(drawn_sizes(pdf_path, "첫째줄", 0)[0], 40, delta=0.5)
            self.assertAlmostEqual(drawn_sizes(pdf_path, "둘째줄", 0)[0], 30, delta=0.5)



@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class CoverTitleTest(unittest.TestCase):
    def test_a_number_stays_with_its_unit_and_the_cover_title_breaks_after_its_clause(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory) / "cover"
            deck_path.mkdir()
            envelope = build(deck_path, COVER_DECK, "pptx")
            if envelope["details"]["review"]["renderSource"] != "layout":
                self.skipTest("the renderer could not run on this host")
            layout = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))
        title = next(block for block in layout["slides"][0]["blocks"] if "41.3" in "".join(run["text"] for paragraph in block["paragraphs"] for run in paragraph["runs"]))
        lines = [line["text"] for paragraph in title["paragraphs"] for line in paragraph["lines"]]
        self.assertTrue(lines[0].endswith("41.3억 원,"), lines)
        self.assertFalse(any(line.startswith("원") for line in lines), lines)

if __name__ == "__main__":
    unittest.main()
