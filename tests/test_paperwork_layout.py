import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, run_office, write_json
from render_fixture import can_render


PAGE_TEXTS = """
import json, sys
import pypdfium2
document = pypdfium2.PdfDocument(sys.argv[1])
print(json.dumps([page.get_textpage().get_text_range() for page in document], ensure_ascii=False))
"""


def korean_statement(row_count: int, with_remarks: bool) -> dict:
    values = {
        "form": "kr/transaction-statement",
        "title": "거 래 명 세 서",
        "profile": {"name": "주식회사 견본상회"},
        "recipient": {"lines": ["예시유통 주식회사"]},
        "meta": [{"label": "거래일자", "value": "2026-03-02"}],
        "items": {
            "headers": ["품명", "수량", "단가", "공급가액"],
            "aligns": ["L", "R", "R", "R"],
            "rows": [[f"견본 부품 {index + 1}", "2", "1,500", "3,000"] for index in range(row_count)],
            "totals": [{"label": "공급가액 합계", "value": f"{3000 * row_count:,}원"}],
        },
        "notes": ["위와 같이 계산합니다."],
        "signature": {"date": "2026년 3월 2일", "line": "주식회사 견본상회 대표이사 최견본"},
    }
    if with_remarks:
        values["sections"] = [{"title": "비고", "bullets": ["납품 장소는 예시유통 물류센터입니다.", "잔여 수량은 다음 달에 납품합니다."]}]
    return values


def english_invoice(row_count: int) -> dict:
    return {
        "form": "intl/purchase-order",
        "title": "Invoice",
        "profile": {"name": "Sample Works Ltd."},
        "recipient": {"lines": ["Example Imports LLC"]},
        "meta": [{"label": "Invoice date", "value": "March 2, 2026"}, {"label": "Due date", "value": "April 1, 2026"}],
        "items": {
            "headers": ["Description", "Qty", "Unit price", "Amount"],
            "aligns": ["L", "R", "R", "R"],
            "rows": [[f"Sample service line {index + 1}", "1", "120.00", "120.00"] for index in range(row_count)],
            "totals": [{"label": "Total", "value": f"USD {120 * row_count:,.2f}"}],
        },
        "sections": [{"title": "Payment", "paragraphs": ["Transfer the total to the account on file within 30 days."]}],
        "notes": ["Thank you for your business."],
        "signature": {"date": "March 2, 2026", "line": "Sample Works Ltd. Director Alex Sample"},
    }


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class PaperworkLayoutTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def page_texts(self, values: dict) -> list[str]:
        write_json(self.directory / "values.json", values)
        envelope = run_office(["merge", values["form"], "values.json", "form.pdf"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "form.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)
        return json.loads(completed.stdout)

    def assert_closing_stays_with_what_it_closes(self, pages: list[str], values: dict, label: str) -> None:
        signer = values["signature"]["line"]
        signing_page = next(page for page in pages if signer in page)
        with self.subTest(label):
            self.assertIn(values["signature"]["date"], signing_page)
            for note in values["notes"]:
                self.assertIn(note, signing_page)
            closed = [values["items"]["totals"][-1]["value"], *(section["title"] for section in values.get("sections", []))]
            self.assertTrue(any(text in signing_page for text in closed), f"the signature page holds only the closing: {signing_page!r}")

    def test_the_closing_never_starts_a_page_without_the_content_it_closes(self):
        for row_count in range(17, 27):
            values = korean_statement(row_count, with_remarks=row_count % 2 == 0)
            self.assert_closing_stays_with_what_it_closes(self.page_texts(values), values, f"kr rows={row_count}")
        for row_count in range(20, 28, 2):
            values = english_invoice(row_count)
            self.assert_closing_stays_with_what_it_closes(self.page_texts(values), values, f"intl rows={row_count}")

    def test_a_figure_never_breaks_inside_itself(self):
        figures = ["29,370,000원", "1,234,567,890원", "USD 98,765.43", "₩4,400,000"]
        long_description = "예산코드와 관련 품의 번호, 납품 장소, 검수 일정까지 한 칸에 적은 아주 긴 적요 문장으로 열 너비를 다 차지하려는 행입니다 " * 2
        values = {
            "form": "kr/expense-approval",
            "title": "지 출 결 의 서",
            "profile": {"name": "주식회사 견본상회"},
            "items": {
                "headers": ["적요", "거래처", "금액"],
                "aligns": ["L", "L", "R"],
                "rows": [[long_description, "예시시스템 주식회사", figure] for figure in figures],
            },
        }
        text = "".join(self.page_texts(values))
        for figure in figures:
            self.assertIn(figure, text)
        self.assertIn("예시시스템", text)


if __name__ == "__main__":
    unittest.main()
