import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

from doc_fixture import OFFICE_ENTRY, SCRIPTS_PATH, run_office, write_json
from render_fixture import can_render
from test_paperwork_templates import ContractRun, codes, complete_values, contract_templates, stated_terms

from paperwork.jurisdictions import find_jurisdiction
from paperwork.paperwork_pdf import paperwork_html


REFERENCES_PATH = SCRIPTS_PATH.parent / "references"
BLANK_SPAN = '<span class="blank"></span>'
BLANK_LINE = "__________"
PAGE_TEXT = """
import json, sys
import pypdfium2
print(json.dumps("".join(page.get_textpage().get_text_range() for page in pypdfium2.PdfDocument(sys.argv[1])), ensure_ascii=False))
"""
MISSING_VALUE_WORDING = re.compile(r"ask the requester|ask when|ask for what|미기재|Not provided|never invent|stay empty strings|as empty strings", re.IGNORECASE)


def purchase_order(**changes) -> dict:
    values = {
        "form": "kr/purchase-order",
        "title": "발 주 서",
        "documentNumber": "PO-20261003-001",
        "profile": {"name": "주식회사 예시랩", "representative": "이샘플", "address": "서울특별시 중구 예시로 1", "missingFields": []},
        "recipient": {"label": "수신", "lines": ["주식회사 견본디스플레이", None]},
        "meta": [
            {"label": "발주일자", "value": "2026-10-03"},
            {"label": "납기일", "value": None},
            {"label": "납품장소", "value": "본사 5층"},
            {"label": "결제조건", "value": None},
        ],
        "items": {
            "headers": ["품명", "규격", "수량", "단가", "공급가액", "세액"],
            "rows": [["모니터", "27인치", "15", "320,000", "4,800,000", "480,000"], ["모니터 암", "", "15", None, None, None]],
            "totals": [{"label": "공급가액 합계", "value": None}, {"label": "부가세(10%)", "value": None}, {"label": "총 발주금액", "value": None}],
        },
        "notes": ["위와 같이 발주합니다."],
        "signature": {"date": "2026년 10월 3일", "line": "주식회사 예시랩 대표이사 이샘플", "stamp": True},
    }
    return values | changes


def blank_locations(envelope: dict) -> list[str]:
    return [blank["location"] for blank in envelope["details"]["blanks"]]


class FormBlankHtmlTest(unittest.TestCase):
    def test_a_value_left_null_is_drawn_as_a_blank_and_never_as_a_word(self):
        drawn = paperwork_html(purchase_order(), find_jurisdiction("kr"))

        self.assertEqual(drawn.count(BLANK_SPAN), 6)
        self.assertNotIn("None", drawn)
        self.assertNotIn("미기재", drawn)

    def test_a_signer_and_date_left_null_are_blank_lines_beside_the_seal_mark(self):
        drawn = paperwork_html(purchase_order(signature={"date": None, "line": None, "stamp": True}), find_jurisdiction("kr"))

        self.assertIn(f'<p class="date">{BLANK_SPAN}</p>', drawn)
        self.assertIn(f"<span>{BLANK_SPAN}</span><span class=\"seal\">(인)", drawn)

    def test_a_company_name_the_profile_lacks_leaves_the_letterhead_name_blank(self):
        drawn = paperwork_html(purchase_order(profile={"name": "", "missingFields": ["name"]}), find_jurisdiction("kr"))

        self.assertIn(f'<p class="name">{BLANK_SPAN}</p>', drawn)


class FormBlankListTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def check(self, values: dict) -> dict:
        write_json(self.directory / "values.json", values)
        return run_office(["check", "values.json"], self.directory)

    def test_check_lists_every_blank_with_the_label_it_stands_under(self):
        envelope = self.check(purchase_order())

        self.assertEqual(envelope["details"]["blanks"], [
            {"location": "meta[1].value", "label": "납기일"},
            {"location": "meta[3].value", "label": "결제조건"},
            {"location": "recipient.lines[1]", "label": "수신"},
            {"location": "items.rows[1][3]", "label": "단가 (2)"},
            {"location": "items.rows[1][4]", "label": "공급가액 (2)"},
            {"location": "items.rows[1][5]", "label": "세액 (2)"},
            {"location": "items.totals[0].value", "label": "공급가액 합계"},
            {"location": "items.totals[1].value", "label": "부가세(10%)"},
            {"location": "items.totals[2].value", "label": "총 발주금액"},
            {"location": "signature.stamp", "label": "seal"},
        ])

    def test_a_blank_row_is_left_unchecked_and_never_called_unreadable(self):
        envelope = self.check(purchase_order())

        self.assertEqual(envelope["issues"], [])
        self.assertEqual([fact["location"] for fact in envelope["details"]["facts"]], ["items.rows[0][4]", "items.rows[0][5]"])

    def test_the_letterhead_fields_the_profile_reports_missing_are_blanks(self):
        profile = {"name": "주식회사 예시랩", "missingFields": ["address", "bankAccount", "phone"]}
        envelope = self.check(purchase_order(profile=profile))

        self.assertEqual(blank_locations(envelope)[:2], ["profile.address", "profile.phone"])

    def test_a_form_with_no_blank_lists_none(self):
        values = purchase_order()
        values["recipient"]["lines"][1] = "한예시 과장 님"
        values["meta"][1]["value"] = "2026-11-14"
        values["meta"][3]["value"] = "납품 후 익월 말 현금 지급"
        values["items"]["rows"][1] = ["모니터 암", "", "15", "45,000", "675,000", "67,500"]
        values["items"]["totals"] = [{"label": "공급가액 합계", "value": "5,475,000원"}, {"label": "부가세(10%)", "value": "547,500원"}, {"label": "총 발주금액", "value": "6,022,500원"}]
        values["signature"]["stamp"] = False

        envelope = self.check(values)

        self.assertEqual(envelope["details"]["blanks"], [])
        self.assertEqual(envelope["issues"], [])


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class FormBlankMergeTest(FormBlankListTest):
    def merge(self, values: dict) -> tuple[dict, str]:
        write_json(self.directory / "values.json", values)
        envelope = run_office(["merge", "kr/purchase-order", "values.json", "발주서.pdf"], self.directory)
        text = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXT, "발주서.pdf"], cwd=self.directory, capture_output=True, text=True, check=True).stdout
        return envelope, json.loads(text)

    def test_merge_delivers_the_form_with_its_blanks_and_lists_them(self):
        envelope, text = self.merge(purchase_order(profile={"name": "", "missingFields": ["name"]}))

        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        self.assertEqual(blank_locations(envelope)[0], "profile.name")
        for printed in ("납기일", "결제조건", "모니터 암", "(인)"):
            self.assertIn(printed, text)
        self.assertNotIn("None", text)

    def test_filling_the_blanks_completes_the_same_document_in_place(self):
        values = purchase_order()
        self.merge(values)
        values["meta"][1]["value"] = "2026-11-14"
        values["meta"][3]["value"] = "납품 후 익월 말 현금 지급"

        envelope, text = self.merge(values)

        self.assertNotIn("meta[1].value", blank_locations(envelope))
        self.assertIn("2026-11-14", text)
        self.assertIn("PO-20261003-001", text)


class ContractBlankTest(ContractRun):
    def test_every_term_a_clause_states_may_be_left_as_a_blank_to_fill_by_hand(self):
        for name, template in contract_templates().items():
            for term in template.terms:
                if term.is_derived or term.name not in stated_terms(template):
                    continue
                values = complete_values(template) | {term.name: None}
                envelope, text = self.merged_text(name, values)
                whole = "\n".join(self.paragraphs(text) + text["cells"])
                self.assertIn(BLANK_LINE, whole, f"{name}: {term.name}")
                self.assertNotIn("None", whole, f"{name}: {term.name}")
                self.assertEqual(blank_locations(envelope), [f"values.{term.name}"], f"{name}: {term.name}")
                self.assertIsNone(envelope["details"]["terms"][term.name], f"{name}: {term.name}")

    def test_an_amount_left_blank_leaves_its_words_blank_too(self):
        values = complete_values(contract_templates()["kr/service-agreement"]) | {"totalAmount": None}
        envelope, text = self.merged_text("kr/service-agreement", values)

        self.assertIn(f"① 본 용역의 계약금액은 금 {BLANK_LINE}원整 (₩{BLANK_LINE}, 부가가치세 포함)으로 한다.", self.paragraphs(text))
        self.assertEqual(blank_locations(envelope), ["values.totalAmount"])

    def test_a_term_left_out_is_still_refused_and_the_refusal_offers_the_blank(self):
        values = complete_values(contract_templates()["kr/nda"])
        values.pop("returnDays")
        envelope = self.run_form("check", "kr/nda", values)

        self.assertEqual(codes(envelope), [("MISSING_TERM", "values.returnDays")])
        self.assertIn("null", envelope["issues"][0]["suggestion"])


class MissingValuePrincipleTest(unittest.TestCase):
    def test_no_form_spec_restates_how_a_missing_value_is_handled(self):
        for path in sorted((REFERENCES_PATH / "paperwork").rglob("*.md")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                self.assertIsNone(MISSING_VALUE_WORDING.search(line), f"{path.relative_to(REFERENCES_PATH)}:{number}: {line}")

    def test_the_paperwork_reference_states_the_blank_principle_once(self):
        text = (REFERENCES_PATH / "paperwork.md").read_text(encoding="utf-8")

        self.assertIn("details.blanks", text)
        self.assertIn("null", text)


if __name__ == "__main__":
    unittest.main()
