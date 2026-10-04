import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY
from render_fixture import can_render
from test_paperwork_layout import PAGE_TEXTS
from test_schema_documents import run_office_with_context, runtime_context, write_json


LEAD_IN = "아래와 같이 견적합니다."


def quote_values(item_count: int, recipient: str) -> dict:
    return {
        "recipient": recipient,
        "validDays": 14,
        "delivery": "발주 후 2주",
        "deliveryPlace": "예시 물류센터",
        "paymentTerms": "납품 후 30일 이내 현금",
        "items": [{"name": f"견본 품목 {number}", "quantity": number, "unit": "개", "unitPrice": 1000 * number} for number in range(1, item_count + 1)],
    }


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class QuoteLeadInTest(unittest.TestCase):
    def pdf_text(self, values: dict) -> str:
        with tempfile.TemporaryDirectory() as directory:
            write_json(Path(directory, "values.json"), values)
            write_json(Path(directory, "context.json"), runtime_context())
            result = run_office_with_context(["merge", "kr/quote", "values.json", "quote.pdf"], directory, Path(directory, "context.json"))
            self.assertEqual(result["status"], "ok", result["issues"])
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "quote.pdf"], cwd=directory, capture_output=True, text=True, check=True)
            return "".join(json.loads(completed.stdout))

    def assert_lead_in_introduces_the_table(self, item_count: int, recipient: str) -> None:
        text = self.pdf_text(quote_values(item_count, recipient))
        positions = [text.index(marker) for marker in ("입금계좌", LEAD_IN, "품명", "견본 품목 1", "총 합계", "(인)")]
        self.assertEqual(positions, sorted(positions), f"{item_count} items: {text!r}")
        self.assertEqual(text.count(LEAD_IN), 1)

    def test_a_one_row_quote_says_as_below_before_its_table(self):
        self.assert_lead_in_introduces_the_table(1, "견본상사")

    def test_a_four_row_quote_says_as_below_before_its_table(self):
        self.assert_lead_in_introduces_the_table(4, "예시유통 주식회사")

    def test_a_quote_that_runs_to_a_second_page_says_as_below_before_its_table(self):
        self.assert_lead_in_introduces_the_table(32, "최견본 상회")

    def test_a_closing_sentence_that_speaks_of_what_is_above_still_follows_the_table(self):
        with tempfile.TemporaryDirectory() as directory:
            values = {"form": "kr/transaction-statement", "title": "거 래 명 세 서", "profile": {"name": "주식회사 견본상회"}, "recipient": {"lines": ["예시유통 주식회사"]},
                      "items": {"headers": ["품명", "금액"], "rows": [["견본", "1,000"]]}, "notes": ["위와 같이 계산합니다."], "signature": {"date": "2026년 3월 2일", "line": "주식회사 견본상회"}}
            write_json(Path(directory, "values.json"), {key: value for key, value in values.items() if key != "profile"})
            write_json(Path(directory, "profile.json"), values["profile"])
            context = runtime_context()
            context["company"] = {"ko": str(Path(directory, "profile.json"))}
            write_json(Path(directory, "context.json"), context)
            result = run_office_with_context(["merge", "kr/transaction-statement", "values.json", "statement.pdf"], directory, Path(directory, "context.json"))
            self.assertEqual(result["status"], "ok", result["issues"])
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "statement.pdf"], cwd=directory, capture_output=True, text=True, check=True)
            text = "".join(json.loads(completed.stdout))
            self.assertLess(text.index("견본"), text.index("위와 같이 계산합니다."))


if __name__ == "__main__":
    unittest.main()
