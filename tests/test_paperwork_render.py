import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, run_office, write_form_values, write_runtime_context
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
        "profile": {"name": "주식회사 예시상사", "logoImage": "logo.png", "sealImage": "seal.png", "legalAttributes": [{"label": "사업자등록번호", "value": "123-45-67890"}], "representative": "이샘플", "address": "서울특별시 중구 예시로 1"},
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
        write_form_values(self.directory / "quote.json", quote(self.directory, sections))
        envelope = run_office(["merge", "kr/purchase-order", "quote.json", "quote.pdf"], self.directory)
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

    def test_an_approval_box_carries_the_approver_the_request_names_under_the_role(self):
        values = quote(self.directory, [])
        values["approvalLine"] = [{"role": "담당", "name": "최견본"}, {"role": "팀장", "name": "박예시"}, "대표이사"]
        write_form_values(self.directory / "quote.json", values)
        self.assertEqual(run_office(["merge", "kr/purchase-order", "quote.json", "quote.pdf"], self.directory)["status"], "ok")
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "quote.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)
        text = "".join(json.loads(completed.stdout))
        for expected in ("담당", "최견본", "팀장", "박예시", "대표이사"):
            self.assertIn(expected, text)

    def test_an_international_form_prints_its_fixed_labels_in_english(self):
        values = quote(self.directory, [{"title": "Notes", "bullets": ["Installation included"]}])
        values.update({
            "form": "intl/purchase-order",
            "title": "Quotation",
            "profile": {"name": "Sample Electronics", "registrationNumber": "123-45-67890", "representative": "Alex Sample", "sealImage": "seal.png"},
            "approvalLine": ["Prepared", "Approved"],
            "recipient": {"lines": ["Example Trading Co."]},
            "meta": [{"label": "Total", "value": "USD 4,400"}],
            "items": {"headers": ["Item", "Qty", "Amount"], "rows": [["Office chair", "10", "4,000"]], "totals": [{"label": "Total", "value": "4,400"}]},
            "signature": {"date": "October 2, 2026", "line": "Sample Electronics CEO Alex Sample", "stamp": True},
            "footer": "Valid for 30 days.",
        })
        write_form_values(self.directory / "quote.json", values)
        envelope = run_office(["merge", "intl/purchase-order", "quote.json", "quote.pdf"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "quote.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)
        text = "".join(json.loads(completed.stdout))
        self.assertEqual(re.findall(r"[\uac00-\ud7a3]+", text), [])
        for expected in ("No. Q-20261002-001", "Registration No. 123-45-67890", "Representative Alex Sample", "To"):
            self.assertIn(expected, text)

    def test_a_form_names_hangul_only_where_its_content_holds_it(self):
        values = quote(self.directory, [])
        values.update({"profile": {"name": "Sample Electronics"}, "recipient": {"lines": ["주식회사 견본물산"]}, "meta": [], "signature": {"line": "Alex Sample"}, "footer": "", "title": "Quotation", "approvalLine": []})
        values.pop("items")
        write_form_values(self.directory / "quote.json", values)
        self.assertEqual(run_office(["merge", "intl/purchase-order", "quote.json", "quote.pdf"], self.directory)["status"], "ok")
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "quote.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)
        self.assertEqual(re.findall(r"[\uac00-\ud7a3]+", "".join(json.loads(completed.stdout))), ["주식회사", "견본물산"])

    def priced(self, form: str, supply: int, tax: int, words: str) -> dict:
        values = quote(self.directory, [])
        values.update({
            "form": form,
            "meta": [{"label": "합계금액", "value": words}, {"label": "발행일자", "value": "2026-03-02"}],
            "items": {"headers": ["품명", "수량", "단가", "공급가액", "세액"], "rows": [["견본 품목", "1", f"{supply:,}", f"{supply:,}", f"{tax:,}"]],
                      "totals": [{"label": "공급가액 합계", "value": f"{supply:,}원"}, {"label": "부가세", "value": f"{tax:,}원"}, {"label": "총 합계", "value": f"{supply + tax:,}원"}]},
        })
        return values

    def merged_text(self, values: dict) -> tuple[dict, str]:
        write_form_values(self.directory / "form.json", values)
        envelope = run_office(["merge", values["form"], "form.json", "form.pdf"], self.directory)
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "form.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)
        return envelope, "".join(json.loads(completed.stdout))

    def test_an_amount_left_unspelled_is_written_in_words_from_the_grand_total(self):
        cases = [
            ("kr/purchase-order", 9_091_637, 909_163, "일금 일천만팔백원整 (₩10,000,800) (부가세 포함)"),
            ("kr/invoice", 910_911_822, 91_091_182, "일금 일십억이백만삼천사원整 (₩1,002,003,004) (부가세 포함)"),
            ("kr/purchase-order", 50_000, 5_000, "일금 오만오천원整 (₩55,000) (부가세 포함)"),
        ]
        for form, supply, tax, expected in cases:
            with self.subTest(form=form):
                envelope, text = self.merged_text(self.priced(form, supply, tax, ""))
                self.assertEqual(envelope["status"], "ok", envelope["issues"])
                self.assertIn(expected, text)

    def test_the_words_follow_the_last_total_line_when_a_form_has_more_than_three(self):
        values = self.priced("kr/purchase-order", 1_000_000, 90_000, "")
        values["items"]["totals"] = [{"label": "공급가액 합계", "value": "1,000,000원"}, {"label": "특별할인", "value": "100,000원"}, {"label": "부가세", "value": "90,000원"}, {"label": "총 합계", "value": "990,000원"}]
        envelope, text = self.merged_text(values)
        self.assertIn("일금 구십구만원整 (₩990,000) (부가세 포함)", text)

    def test_a_misspelled_amount_is_reported_by_merge(self):
        envelope, text = self.merged_text(self.priced("kr/invoice", 25_228_000, 2_522_800, "일금 이천칠백칠십오만영백팔십원整"))
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["AMOUNT_IN_WORDS_MISMATCH"])
        self.assertIn("이천칠백칠십오만팔백", envelope["issues"][0]["suggestion"])

    def test_a_form_that_runs_past_a_page_numbers_every_page(self):
        long_sections = [{"title": f"제{number}조", "paragraphs": ["여러 쪽에 걸친 문서의 쪽 번호를 확인하는 문단입니다. " * 6]} for number in range(1, 16)]
        pages = self.render(long_sections)
        self.assertGreater(len(pages), 1)
        self.assertEqual(pdf_page_count(self.directory / "quote.pdf"), len(pages))
        for number, text in enumerate(pages, start=1):
            self.assertIn(f"- {number} -", text)



ANSWERED_PROFILE = {
    "language": "ko",
    "name": "주식회사 샘플테크",
    "representative": "이샘플",
    "representativeTitle": "대표이사",
    "address": "서울특별시 강남구 예시로 123, 샘플빌딩 8층",
    "legalAttributes": [{"label": "사업자등록번호", "value": "123-45-67890"}, {"label": "법인등록번호", "value": "110111-1234567"}],
    "phone": "02-1234-5678",
    "fax": "02-1234-5679",
    "email": "contact@example.com",
    "website": "https://www.example.com",
    "missingFields": [],
    "sealImage": "seal.png",
    "logoImage": "logo.png",
}


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class CompanyProfileFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.answered = self.directory / "answered" / "company_info_get-1"
        self.answered.mkdir(parents=True)
        subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", SEAL_AND_LOGO], cwd=self.answered, check=True)

    def merge(self, answered_profile: dict | None, **changes) -> tuple[dict, str, bytes]:
        if answered_profile is not None:
            (self.answered / "company-profile.json").write_text(json.dumps(answered_profile, ensure_ascii=False), encoding="utf-8")
            write_runtime_context(self.directory, self.answered / "company-profile.json")
        values = {
            "form": "kr/purchase-order",
            "title": "견 적 서",
            "recipient": {"lines": ["주식회사 견본물산"]},
            "items": {"headers": ["품명", "수량", "금액"], "rows": [["사무용 의자", "10", "4,000,000"]]},
            "signature": {"date": "2026년 10월 3일", "line": "주식회사 샘플테크 대표이사 이샘플", "stamp": True},
        } | changes
        (self.directory / "values.json").write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
        envelope = run_office(["merge", "kr/purchase-order", "values.json", "quote.pdf"], self.directory)
        if envelope["status"] == "error":
            return envelope, "", b""
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "quote.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)
        return envelope, "".join(json.loads(completed.stdout)), (self.directory / "quote.pdf").read_bytes()

    def test_the_letterhead_prints_every_field_the_company_profile_answers(self):
        envelope, text, _ = self.merge(ANSWERED_PROFILE)

        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        for printed in ("주식회사 샘플테크", "사업자등록번호 123-45-67890", "법인등록번호 110111-1234567", "대표이사 이샘플", "서울특별시 강남구 예시로 123", "전화 02-1234-5678", "팩스 02-1234-5679", "contact@example.com", "https://www.example.com"):
            self.assertIn(printed, text)

    def test_every_legal_attribute_prints_whatever_its_place_in_the_profile(self):
        attributes = [{"label": "업태", "value": "서비스업, 도소매업"}, {"label": "종목", "value": "소프트웨어 개발 및 공급, 컴퓨터 및 주변기기"},
                      {"label": "사업자등록번호", "value": "123-45-67890"}, {"label": "법인등록번호", "value": "110111-1234567"}]
        envelope, text, _ = self.merge(ANSWERED_PROFILE | {"legalAttributes": attributes})

        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        flattened = "".join(text.split())
        for attribute in attributes:
            self.assertIn("".join(f"{attribute['label']} {attribute['value']}".split()), flattened)

    def test_the_seal_and_logo_kept_beside_the_profile_are_drawn(self):
        envelope, _, drawn = self.merge(ANSWERED_PROFILE)

        self.assertEqual(envelope["details"]["blanks"], [])
        self.assertGreaterEqual(len(re.findall(rb"/Subtype\s*/Image", drawn)), 2)

    def test_a_company_without_a_kept_seal_leaves_the_seal_place_blank(self):
        envelope, text, _ = self.merge(ANSWERED_PROFILE | {"sealImage": "", "logoImage": ""})

        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        self.assertEqual(envelope["details"]["blanks"], [{"location": "signature.stamp", "label": "seal"}])
        self.assertIn("(인)", text)

    def test_a_company_profile_copied_into_the_values_is_refused(self):
        envelope, _, _ = self.merge(ANSWERED_PROFILE, profile={"name": "주식회사 샘플테크"})

        self.assertEqual(envelope["status"], "error")
        self.assertIn("values.profile", [issue["location"] for issue in envelope["issues"]])

    def test_a_company_path_in_the_values_is_refused(self):
        envelope, _, _ = self.merge(ANSWERED_PROFILE, company=str(self.answered / "company-profile.json"))

        self.assertEqual(envelope["status"], "error")
        self.assertIn("values.company", [issue["location"] for issue in envelope["issues"]])

    def test_without_a_runtime_context_the_letterhead_is_left_blank_and_listed(self):
        envelope, _, _ = self.merge(None)

        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        locations = [blank["location"] for blank in envelope["details"]["blanks"]]
        self.assertIn("profile.name", locations)
        self.assertIn("signature.stamp", locations)

    def test_a_task_whose_company_profile_was_never_read_is_told_to_read_it(self):
        context = {"requester": {"name": "이샘플", "email": "sample@example.com"}, "today": "2026-10-04", "company": {}, "registeredDocuments": [], "attachments": []}
        (self.directory / "office-runtime-context.json").write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
        envelope, _, _ = self.merge(None)

        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["issues"][0]["code"], "COMPANY_NOT_READ")

    def test_an_english_form_reads_the_profile_for_english(self):
        english = self.directory / "english"
        english.mkdir()
        (english / "company-profile.json").write_text(json.dumps({"name": "Sample Tech Inc."}), encoding="utf-8")
        (self.answered / "company-profile.json").write_text(json.dumps(ANSWERED_PROFILE, ensure_ascii=False), encoding="utf-8")
        context = {"requester": {"name": "이샘플", "email": "sample@example.com"}, "today": "2026-10-04", "registeredDocuments": [], "attachments": [],
                   "company": {"ko": str(self.answered / "company-profile.json"), "en": str(english / "company-profile.json")}}
        (self.directory / "office-runtime-context.json").write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
        values = {"form": "intl/purchase-order", "title": "Quotation", "recipient": {"lines": ["Example Buyer Ltd."]},
                  "items": {"headers": ["Item", "Qty", "Amount"], "rows": [["Chair", "10", "4,000"]]}}
        (self.directory / "values.json").write_text(json.dumps(values), encoding="utf-8")
        envelope = run_office(["merge", "intl/purchase-order", "values.json", "quote.pdf"], self.directory)
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "quote.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)

        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        self.assertIn("Sample Tech Inc.", "".join(json.loads(completed.stdout)))

    def test_an_image_name_never_leaves_the_profile_directory(self):
        (self.directory / "outside.png").write_bytes((self.answered / "seal.png").read_bytes())
        envelope, _, _ = self.merge(ANSWERED_PROFILE | {"sealImage": "../../outside.png", "logoImage": ""})

        self.assertEqual(envelope["details"]["blanks"], [{"location": "signature.stamp", "label": "seal"}])

if __name__ == "__main__":
    unittest.main()
