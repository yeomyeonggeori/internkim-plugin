from pathlib import Path
import sys
import tempfile
import unittest

import pypdfium2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_fixture import can_render  # noqa: E402
from staged_deck_fixture import build_deck, issues_at, run_office, write_staged_deck  # noqa: E402

from pdf.drawn_text import undrawn_characters  # noqa: E402

FADED_LINE = "영업이익률 8.4% → 7.1%: 알루미늄 원자재 단가 상승 영향"
FADED_STYLE = ".faded { opacity: 0.7; margin: 0; } .plain { margin: 0; }"
FADED_PAGE = (
    f'<h2>수익성은 원자재 단가에 눌렸습니다</h2><p class="plain">{FADED_LINE}</p><p class="faded">{FADED_LINE}</p>'
    '<table style="flex: 1"><tr><th>분기</th><th>영업이익률</th></tr><tr><td>2분기</td><td>8.4%</td></tr><tr><td>3분기</td><td>7.1%</td></tr></table>'
)


def pdf_with_page_content(content: bytes) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    document = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    table = len(document)
    document += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    document += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    return document + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, table)


CLIPPED_TEXT = b"q 72 600 60 60 re W n BT /F1 48 Tf 72 620 Td (Hello) Tj ET Q"
INVISIBLE_TEXT = b"BT /F1 24 Tf 72 700 Td (Visible words) Tj ET BT 3 Tr /F1 24 Tf 72 600 Td (Scanned words) Tj ET"


def darkest_value_on_line(pdf_path: Path, line_number: int) -> int:
    page = pypdfium2.PdfDocument(str(pdf_path))[1]
    image = page.render(scale=1).to_pil().convert("L")
    text_page = page.get_textpage()
    found = text_page.search(FADED_LINE)
    for _ in range(line_number):
        match = found.get_next()
    start, count = match
    boxes = [text_page.get_charbox(index) for index in range(start, start + count)]
    height = page.get_height()
    left, right = int(min(box[0] for box in boxes)), int(max(box[2] for box in boxes)) + 1
    top, bottom = int(height - max(box[3] for box in boxes)), int(height - min(box[1] for box in boxes)) + 1
    return image.crop((left, top, right, bottom)).getextrema()[0]


class DrawnTextCheckTest(unittest.TestCase):
    def check(self, content: bytes) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "made.pdf"
            path.write_bytes(pdf_with_page_content(content))
            return run_office(["check", str(path)], Path(directory))

    def test_text_a_clip_cuts_off_is_reported_with_its_word(self):
        envelope = self.check(CLIPPED_TEXT)
        messages = [issue["message"] for issue in issues_at(envelope, "TEXT_NOT_DRAWN")]
        self.assertEqual(len(messages), 1, envelope["summary"])
        self.assertIn('"Hello" draws nothing for "o"', messages[0])

    def test_invisible_text_such_as_a_scan_text_layer_is_not_reported(self):
        envelope = self.check(INVISIBLE_TEXT)
        self.assertEqual(issues_at(envelope, "TEXT_NOT_DRAWN"), [], envelope["summary"])


@unittest.skipUnless(can_render(), "the renderer is not available")
class TranslucentTextInPdfTest(unittest.TestCase):
    def test_text_in_a_translucent_block_draws_every_character_and_stays_faded(self):
        with tempfile.TemporaryDirectory() as directory:
            deck = write_staged_deck(Path(directory), ["<h1>Quarterly sales review</h1>", FADED_PAGE, "<h2>Thank you</h2>"], FADED_STYLE)
            envelope = build_deck(deck, extension="pdf")
            pdf_path = Path(envelope["outputPath"])
            undrawn = undrawn_characters(pdf_path)
            plain, faded = darkest_value_on_line(pdf_path, 1), darkest_value_on_line(pdf_path, 2)
        self.assertEqual(issues_at(envelope, "TEXT_NOT_DRAWN"), [], envelope["summary"])
        self.assertEqual(undrawn, [])
        self.assertGreater(faded, plain + 20)


if __name__ == "__main__":
    unittest.main()
