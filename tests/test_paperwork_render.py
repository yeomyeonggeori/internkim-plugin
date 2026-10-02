import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, run_office, write_json
from render_fixture import can_render, pdf_page_count


SEAL_AND_LOGO = """
import sys
from PIL import Image, ImageDraw
logo = Image.new("RGB", (240, 80), "white"); ImageDraw.Draw(logo).rectangle([0, 0, 80, 80], fill=(30, 80, 160)); logo.save("logo.png")
seal = Image.new("RGBA", (160, 160), (0, 0, 0, 0)); ImageDraw.Draw(seal).ellipse([8, 8, 152, 152], outline=(200, 30, 30), width=10); seal.save("seal.png")
"""
PAGE_TEXTS = """
import json, sys
import pypdfium2
document = pypdfium2.PdfDocument(sys.argv[1])
print(json.dumps([page.get_textpage().get_text_range() for page in document], ensure_ascii=False))
"""


def quote(directory: Path, sections: list[dict]) -> dict:
    return {
        "title": "견 적 서",
        "documentNumber": "Q-20261002-001",
        "profile": {"name": "주식회사 예시상사", "logoPath": str(directory / "logo.png"), "stampPath": str(directory / "seal.png"), "legalAttributes": [{"label": "사업자등록번호", "value": "123-45-67890"}], "representative": "이샘플", "address": "서울특별시 중구 예시로 1"},
        "approvalLine": ["담당", "팀장"],
        "recipient": {"lines": ["주식회사 견본물산", "박예시 님"]},
        "meta": [{"label": "합계금액", "value": "일금 사백사십만원整 (₩4,400,000)"}],
        "items": {"headers": ["품명", "수량", "금액"], "aligns": ["L", "R", "R"], "rows": [["사무용 의자", "10", "4,000,000"]], "totals": [{"label": "총 합계", "value": "4,400,000원"}]},
        "sections": sections,
        "signature": {"date": "2026년 10월 2일", "line": "주식회사 예시상사 대표이사 이샘플", "stamp": True},
        "footer": "본 견적은 30일간 유효합니다.",
    }


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class PaperworkRenderTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", SEAL_AND_LOGO], cwd=self.directory, check=True)

    def render(self, sections: list[dict]) -> list[str]:
        write_json(self.directory / "quote.json", quote(self.directory, sections))
        envelope = run_office(["paperwork", "render", "quote.json", "quote.pdf"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "quote.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)
        return json.loads(completed.stdout)

    def test_a_one_page_form_carries_its_letterhead_table_seal_and_footer_without_a_page_number(self):
        pages = self.render([{"title": "특기사항", "bullets": ["설치비 포함"]}])
        self.assertEqual(len(pages), 1)
        for expected in ("주식회사 예시상사", "사업자등록번호 123-45-67890", "견 적 서", "문서번호 Q-20261002-001", "합계금액", "사무용 의자", "4,400,000원", "• 설치비 포함", "(인)", "본 견적은 30일간 유효합니다."):
            self.assertIn(expected, pages[0])
        self.assertNotIn("- 1 -", pages[0])
        drawn = (self.directory / "quote.pdf").read_bytes()
        self.assertGreaterEqual(len(re.findall(rb"/Subtype\s*/Image", drawn)), 2)
        self.assertIn(b"/SMask", drawn)

    def test_a_form_that_runs_past_a_page_numbers_every_page(self):
        long_sections = [{"title": f"제{number}조", "paragraphs": ["여러 쪽에 걸친 문서의 쪽 번호를 확인하는 문단입니다. " * 6]} for number in range(1, 16)]
        pages = self.render(long_sections)
        self.assertGreater(len(pages), 1)
        self.assertEqual(pdf_page_count(self.directory / "quote.pdf"), len(pages))
        for number, text in enumerate(pages, start=1):
            self.assertIn(f"- {number} -", text)


if __name__ == "__main__":
    unittest.main()
