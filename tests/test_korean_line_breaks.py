import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, run_office, write_form_values
from render_fixture import can_render


PARAGRAPH = "당사는 2026년 11월 2일부터 서울특별시 예시구 견본로 1로 사무실을 옮겨 업무를 시작합니다. 이전 기간에는 전화와 전자우편으로 문의를 받으며 방문 일정은 담당자가 별도로 안내드립니다."
PROFILE = {"name": "주식회사 견본상회", "address": "부산광역시 예시구 샘플길 3", "phone": "02-0000-0000", "email": "hello@example.com", "representative": "최견본", "representativeTitle": "대표이사"}
PAGE_LINES = """
import json, sys
import pypdfium2
lines = []
for page in pypdfium2.PdfDocument(sys.argv[1]):
    lines += page.get_textpage().get_text_range().replace("\\r", "").split("\\n")
print(json.dumps(lines, ensure_ascii=False))
"""


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class KoreanLineBreakTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_form_values(self.directory / "unused.json", {"profile": PROFILE})

    def lines(self, pdf: str) -> list[str]:
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_LINES, pdf], cwd=self.directory, capture_output=True, text=True, check=True)
        return json.loads(completed.stdout.strip().splitlines()[-1])

    def assert_breaks_only_between_words(self, lines: list[str], paragraph: str, label: str) -> None:
        body = [" ".join(line.split()) for line in lines if len(line.split()) >= 1 and " ".join(line.split()) in paragraph and len(line) > 6]
        self.assertGreater(len(body), 1, f"{label}: {lines}")
        for line in body:
            start = paragraph.index(line)
            end = start + len(line)
            self.assertTrue(start == 0 or paragraph[start - 1] == " ", f"{label}: a line starts inside a word: {line!r}")
            self.assertTrue(end == len(paragraph) or paragraph[end] == " ", f"{label}: a line ends inside a word: {line!r}")

    def test_a_letter_breaks_korean_only_at_spaces_for_any_text_length(self):
        words = PARAGRAPH.split()
        for skipped in (0, 2, 5, 9):
            with self.subTest(skipped=skipped):
                paragraph = " ".join(words[skipped:])
                values = {"language": "ko", "recipient": "예시유통 주식회사", "title": "안내", "sections": [{"heading": None, "blocks": [{"type": "paragraph", "text": paragraph}]}]}
                (self.directory / "values.json").write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
                self.assertEqual(run_office(["merge", "intl/letter", "values.json", "letter.pdf"], self.directory)["status"], "ok")
                self.assert_breaks_only_between_words(self.lines("letter.pdf"), paragraph, "letter")

    def test_a_pdf_made_from_markdown_breaks_korean_only_at_spaces_at_every_width(self):
        for margin in (10, 22, 35, 50, 70):
            with self.subTest(margin=margin):
                (self.directory / "spec.json").write_text(json.dumps({"title": "제목", "marginMillimeters": margin, "sections": [{"paragraphs": [PARAGRAPH]}]}, ensure_ascii=False), encoding="utf-8")
                self.assertEqual(run_office(["create", "note.pdf", "spec.json"], self.directory)["status"], "ok")
                self.assert_breaks_only_between_words(self.lines("note.pdf"), PARAGRAPH, f"margin {margin}")

    def test_a_form_paragraph_breaks_korean_only_at_spaces(self):
        values = {"form": "kr/transaction-statement", "title": "거 래 명 세 서", "profile": PROFILE, "recipient": {"lines": ["예시유통 주식회사"]},
                  "items": {"headers": ["품명", "수량"], "aligns": ["L", "R"], "rows": [["견본 부품", "2"]]},
                  "sections": [{"title": "비고", "paragraphs": [PARAGRAPH]}]}
        write_form_values(self.directory / "values.json", values)
        self.assertEqual(run_office(["merge", "kr/transaction-statement", "values.json", "form.pdf"], self.directory)["status"], "ok")
        self.assert_breaks_only_between_words(self.lines("form.pdf"), PARAGRAPH, "form")


if __name__ == "__main__":
    unittest.main()
