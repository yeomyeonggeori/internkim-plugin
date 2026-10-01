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

if __name__ == "__main__":
    unittest.main()
