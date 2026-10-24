import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

from PIL import Image

from doc_fixture import OFFICE_ENTRY, run_office, write_form_values
from render_fixture import can_render


SHAPES = {"square": (100, 100), "wide": (300, 100), "tall": (100, 300)}
TOLERANCE = 0.03
PROFILE = {"name": "주식회사 견본상회", "address": "서울특별시 예시구 견본로 1", "phone": "02-0000-0000", "email": "hello@example.com", "representative": "최견본", "representativeTitle": "대표이사", "bankAccount": "예시은행 000-000-000000"}
IMAGE_RATIOS = """
import json, sys
import pypdfium2
ratios = []
for page in pypdfium2.PdfDocument(sys.argv[1]):
    for item in page.get_objects():
        if item.type == 3:
            left, bottom, right, top = item.get_bounds()
            ratios.append((right - left) / (top - bottom))
print(json.dumps(ratios))
"""


def write_image(path: Path, shape: tuple[int, int]) -> None:
    Image.new("RGBA", shape, (180, 40, 40, 255)).save(path)


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class ImageRatioTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def profile_with_images(self, shape: tuple[int, int]) -> None:
        write_image(self.directory / "logo.png", shape)
        write_image(self.directory / "seal.png", shape)
        write_form_values(self.directory / "unused.json", {"profile": {**PROFILE, "logoPath": str(self.directory / "logo.png"), "stampPath": str(self.directory / "seal.png")}})

    def drawn_ratios(self, pdf: str) -> list[float]:
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", IMAGE_RATIOS, pdf], cwd=self.directory, capture_output=True, text=True, check=True)
        return json.loads(completed.stdout.strip().splitlines()[-1])

    def merge(self, schema: str, values: dict, output: str) -> None:
        (self.directory / "values.json").write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(run_office(["merge", schema, "values.json", output], self.directory)["status"], "ok")

    def assert_ratios(self, ratios: list[float], shape: tuple[int, int], expected_count: int, label: str) -> None:
        self.assertEqual(len(ratios), expected_count, f"{label}: {ratios}")
        for ratio in ratios:
            self.assertAlmostEqual(ratio / (shape[0] / shape[1]), 1.0, delta=TOLERANCE, msg=f"{label}: drawn {ratio:.2f} for {shape}")

    def letter_values(self, paragraphs: int = 1) -> dict:
        return {"language": "ko", "recipient": "예시유통 주식회사", "title": "안내", "sections": [{"heading": None, "blocks": [{"type": "paragraph", "text": "이사 안내입니다."} for _ in range(paragraphs)]}]}

    def quote_values(self) -> dict:
        return {"recipient": "예시유통 주식회사", "recipientRegistrationNumber": "111-11-11111", "contact": "박예시", "validDays": 30, "delivery": "발주 후 2주", "deliveryPlace": "예시유통 물류센터", "paymentTerms": "납품 후 30일 이내",
                "items": [{"name": "견본 부품", "spec": "A형", "quantity": 10, "unit": "개", "unitPrice": 15000}]}

    def test_a_letter_pdf_draws_its_logo_and_seal_at_their_own_ratio(self):
        for name, shape in SHAPES.items():
            with self.subTest(name):
                self.profile_with_images(shape)
                self.merge("intl/letter", self.letter_values(), "letter.pdf")
                self.assert_ratios(self.drawn_ratios("letter.pdf"), shape, 2, f"letter {name}")

    def test_a_form_pdf_draws_its_logo_and_stamp_at_their_own_ratio(self):
        for name, shape in SHAPES.items():
            with self.subTest(name):
                self.profile_with_images(shape)
                self.merge("kr/quote", self.quote_values(), "quote.pdf")
                self.assert_ratios(self.drawn_ratios("quote.pdf"), shape, 2, f"quote {name}")

    def test_a_markdown_picture_in_a_pdf_keeps_its_ratio(self):
        for name, shape in SHAPES.items():
            with self.subTest(name):
                write_image(self.directory / "picture.png", shape)
                (self.directory / "note.md").write_text("# 제목\n\n본문입니다.\n\n![사진](picture.png)\n\n끝.\n", encoding="utf-8")
                self.assertEqual(run_office(["create", "note.pdf", "note.md"], self.directory)["status"], "ok")
                self.assert_ratios(self.drawn_ratios("note.pdf"), shape, 1, f"markdown {name}")

    def test_a_letter_docx_draws_its_logo_and_seal_at_their_own_ratio(self):
        for name, shape in SHAPES.items():
            with self.subTest(name):
                self.profile_with_images(shape)
                self.merge("intl/letter", self.letter_values(), "letter.docx")
                with zipfile.ZipFile(self.directory / "letter.docx") as package:
                    document = package.read("word/document.xml").decode("utf-8")
                extents = [(int(width), int(height)) for width, height in re.findall(r'<wp:extent cx="(\d+)" cy="(\d+)"', document)]
                self.assertEqual(len(extents), 2, extents)
                for width, height in extents:
                    self.assertAlmostEqual((width / height) / (shape[0] / shape[1]), 1.0, delta=TOLERANCE, msg=f"docx {name}: {width}x{height}")


if __name__ == "__main__":
    unittest.main()
