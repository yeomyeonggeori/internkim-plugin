import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, run_office, write_form_values
from render_fixture import can_render

from balance.fit import fit_rhythm
from balance.issues import LAST_PAGE_SPARSE, LARGE_EMPTY_BAND, PAGE_ENDS_EARLY, PAGE_SPARSE, balance_issues
from balance.measure import PageMeasure
from balance.rhythm import Rhythm


PROFILE = {"name": "주식회사 견본상회", "address": "서울특별시 예시구 견본로 1", "phone": "02-0000-0000", "email": "hello@example.com", "representative": "최견본", "representativeTitle": "대표이사", "bankAccount": "예시은행 000-000-000000"}
KOREAN_SENTENCE = "이번 분기에는 예시 고객사 세 곳과 협의를 마쳤고, 남은 일정은 담당자 박예시가 정리해 공유합니다."
ENGLISH_SENTENCE = "This quarter the team agreed the plan with three sample customers, and the remaining schedule is shared by Park Yesi."
LINE_POSITIONS = """
import json, sys
import pypdfium2
document = pypdfium2.PdfDocument(sys.argv[1])
page = document[0]
height = page.get_size()[1]
found = {}
for needle in sys.argv[2:]:
    textpage = page.get_textpage()
    match = textpage.search(needle).get_next()
    box = textpage.get_charbox(match[0]) if match else None
    found[needle] = [height - box[3], height - box[1]] if box else None
print(json.dumps(found))
"""
FORCED_ORPHAN = """
import sys
from pathlib import Path
from doc.blocks.markdown import Heading, Paragraph
from doc.blocks.pdf import PageLayout, render_document_pdf
blocks = [Heading(1, "Title")] + [Paragraph("filler paragraph " * 12) for _ in range(int(sys.argv[2]))]
render_document_pdf(blocks, Path(sys.argv[1]), Path("."), "Title", layout=PageLayout(is_balanced=False))
"""


def page(number: int, fill: float, lines: int | None = 10, gap: float = 0.03) -> PageMeasure:
    return PageMeasure(number, 1000.0, fill * 1000.0, lines, gap * 1000.0)


def report_values(language: str, paragraph_count: int, item_count: int = 0) -> dict:
    sentence = KOREAN_SENTENCE if language == "ko" else ENGLISH_SENTENCE
    blocks = [{"type": "paragraph", "text": sentence} for _ in range(paragraph_count)]
    if item_count:
        blocks.append({"type": "items", "items": [{"text": f"Sample item {index + 1}"} for index in range(item_count)]})
    return {"language": language, "title": "주간 보고" if language == "ko" else "Weekly report", "period": None, "recipient": None, "sections": [{"heading": "현황" if language == "ko" else "Status", "blocks": blocks}]}


def letter_values(language: str, paragraph_count: int) -> dict:
    sentence = "당사는 11월 2일부터 새 사무실에서 업무를 시작합니다." if language == "ko" else "We open our new office on November 2."
    return {"language": language, "recipient": "예시유통 주식회사" if language == "ko" else "Example Imports LLC", "title": "안내" if language == "ko" else "Notice", **({} if language == "ko" else {"salutation": "Dear Sir or Madam,"}), "sections": [{"heading": None, "blocks": [{"type": "paragraph", "text": sentence} for _ in range(paragraph_count)]}]}


def quote_values(row_count: int) -> dict:
    return {"recipient": "예시유통 주식회사", "recipientRegistrationNumber": "111-11-11111", "contact": "박예시", "validDays": 30, "delivery": "발주 후 2주", "deliveryPlace": "예시유통 물류센터", "paymentTerms": "납품 후 30일 이내",
            "items": [{"name": f"견본 부품 {index + 1}", "spec": "A형", "quantity": 10, "unit": "개", "unitPrice": 15000} for index in range(row_count)]}


def minutes_values(action_count: int) -> dict:
    return {"meetingName": "예시 주간 회의", "startsAt": "2026-10-02 14:00", "endsAt": "15:00", "place": "본사 회의실", "attendees": ["이샘플", "박예시"], "agenda": ["지난주 진행 확인"],
            "discussion": [KOREAN_SENTENCE] * 3, "decisions": ["다음 회의는 10월 9일에 연다"], "actions": [{"task": f"예시 과제 {index + 1}", "owner": "박예시", "due": "2026-10-09"} for index in range(action_count)]}


class FitRhythmTest(unittest.TestCase):
    def test_a_short_single_page_grows_and_lifts(self):
        rhythm = fit_rhythm(lambda candidate: [page(1, 0.2 + 0.25 * candidate.airiness)])
        self.assertGreater(rhythm.airiness, 0.5)
        self.assertGreater(rhythm.lift_points, 0)

    def test_growth_never_pushes_the_content_to_a_second_page(self):
        def draw(candidate: Rhythm):
            fill = 0.3 + 0.9 * max(candidate.airiness, 0)
            return [page(1, 1.0), page(2, 0.1)] if fill > 0.8 else [page(1, fill)]

        rhythm = fit_rhythm(draw)
        self.assertEqual(len(draw(rhythm)), 1)

    def test_a_full_page_keeps_the_neutral_rhythm(self):
        self.assertEqual(fit_rhythm(lambda candidate: [page(1, 0.9)]), Rhythm())

    def test_a_small_overflow_is_pulled_back_with_the_mildest_tightening(self):
        def draw(candidate: Rhythm):
            overflow = 0.12 + 0.2 * candidate.airiness
            return [page(1, 1.0), page(2, overflow)] if overflow > 0.02 else [page(1, 0.99)]

        rhythm = fit_rhythm(draw)
        self.assertEqual(len(draw(rhythm)), 1)
        self.assertGreater(rhythm.airiness, -1.0)

    def test_an_overflow_tightening_cannot_absorb_stays_neutral(self):
        self.assertEqual(fit_rhythm(lambda candidate: [page(1, 1.0), page(2, 0.1)]), Rhythm())

    def test_a_substantial_last_page_is_left_alone(self):
        self.assertEqual(fit_rhythm(lambda candidate: [page(1, 1.0), page(2, 0.55)]), Rhythm())


class BalanceIssueTest(unittest.TestCase):
    def codes(self, pages):
        return [issue.kind for issue in balance_issues(pages)]

    def test_each_measurement_has_its_threshold(self):
        cases = {
            "sparse single page": ([page(1, 0.3)], PAGE_SPARSE),
            "nearly empty last page": ([page(1, 1.0), page(2, 0.08)], LAST_PAGE_SPARSE),
            "orphan lines on the last page": ([page(1, 1.0), page(2, 0.25, lines=2)], LAST_PAGE_SPARSE),
            "page ending early": ([page(1, 0.6), page(2, 0.5)], PAGE_ENDS_EARLY),
            "wide empty band": ([page(1, 0.8, gap=0.3)], LARGE_EMPTY_BAND),
        }
        for label, (pages, expected) in cases.items():
            with self.subTest(label):
                self.assertIn(expected, self.codes(pages))

    def test_balanced_documents_raise_nothing(self):
        balanced = [[page(1, 0.62)], [page(1, 0.97)], [page(1, 1.0), page(2, 0.4)], [page(1, 0.95), page(2, 0.25, lines=9)], [page(1, 0.85, gap=0.14)]]
        for pages in balanced:
            with self.subTest(fills=[entry.fill for entry in pages]):
                self.assertEqual(self.codes(pages), [])


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class RenderedBalanceTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_form_values(self.directory / "unused.json", {"profile": PROFILE})

    def checked(self, schema: str, values: dict, output: str = "out.pdf") -> dict:
        (self.directory / "values.json").write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
        merged = run_office(["merge", schema, "values.json", output], self.directory)
        self.assertEqual(merged["status"], "ok", merged["issues"])
        return run_office(["check", output], self.directory)

    def test_short_documents_are_set_in_the_page(self):
        cases = {
            "korean report, one paragraph": ("intl/report", report_values("ko", 1)),
            "english report, two paragraphs and items": ("intl/report", report_values("en", 2, 3)),
            "korean notice letter": ("intl/letter", letter_values("ko", 1)),
            "english letter, two paragraphs": ("intl/letter", letter_values("en", 2)),
            "quote, one row": ("kr/quote", quote_values(1)),
            "quote, three rows": ("kr/quote", quote_values(3)),
            "minutes, one action": ("kr/meeting-minutes", minutes_values(1)),
        }
        for label, (schema, values) in cases.items():
            with self.subTest(label):
                details = self.checked(schema, values)["details"]
                self.assertEqual(len(details["pageFill"]), 1)
                self.assertGreaterEqual(details["pageFill"][0], 0.55, details["pageFill"])

    def test_letters_of_every_length_look_finished(self):
        for language in ("ko", "en"):
            sentence = "당사는 11월 2일부터 새 사무실에서 업무를 시작하며 자세한 안내는 별도로 드립니다. " if language == "ko" else "We open our new office on November 2 and will send the details separately. "
            for label, paragraphs, repeat in (("one line", 1, 0), ("one paragraph", 1, 2), ("three paragraphs", 3, 3), ("two pages", 12, 6)):
                with self.subTest(language=language, length=label):
                    text = "이사 안내입니다." if (language == "ko" and repeat == 0) else sentence * max(repeat, 1)
                    values = letter_values(language, 0) | {"sections": [{"heading": None, "blocks": [{"type": "paragraph", "text": text} for _ in range(paragraphs)]}]}
                    details = self.checked("intl/letter", values)["details"]
                    if len(details["pageFill"]) == 1:
                        self.assertGreaterEqual(details["pageFill"][0], 0.55, details["pageFill"])
                    else:
                        self.assertGreater(details["lastPageFill"], 0.15, details["pageFill"])

    def test_a_korean_letter_ends_with_the_end_mark_and_the_sender_seal_mark(self):
        self.checked("intl/letter", letter_values("ko", 1))
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "read", "out.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)
        text = json.loads(completed.stdout)["details"]["pages"][0]["text"]
        self.assertIn("끝.", text)
        self.assertIn("(인)", text)

    def test_an_english_letter_has_a_salutation_and_a_complimentary_close(self):
        self.checked("intl/letter", letter_values("en", 1))
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "read", "out.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)
        text = json.loads(completed.stdout)["details"]["pages"][0]["text"]
        self.assertIn("Dear Sir or Madam,", text)
        self.assertIn("Sincerely,", text)
        self.assertNotIn("(인)", text)

    def test_a_small_overflow_never_leaves_a_near_empty_last_page(self):
        for language, counts in (("ko", range(12, 21)), ("en", range(12, 21))):
            for paragraph_count in counts:
                with self.subTest(language=language, paragraphs=paragraph_count):
                    details = self.checked("intl/report", report_values(language, paragraph_count, 3))["details"]
                    self.assertGreaterEqual(details["lastPageFill"], 0.3 if len(details["pageFill"]) > 1 else 0.0)
                    self.assertGreater(details["lastPageFill"], 0.15)

    def test_a_long_closing_section_does_not_move_whole_to_the_next_page(self):
        for action_count in (11, 13, 16, 22):
            with self.subTest(actions=action_count):
                details = self.checked("kr/meeting-minutes", minutes_values(action_count))["details"]
                self.assertTrue(all(fill >= 0.7 for fill in details["pageFill"][:-1]), details["pageFill"])

    def test_the_closing_line_sits_under_the_signature(self):
        for row_count in (1, 2, 6):
            with self.subTest(rows=row_count):
                self.checked("kr/quote", quote_values(row_count))
                completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", LINE_POSITIONS, "out.pdf", "(인)", "본 견적은"], cwd=self.directory, capture_output=True, text=True, check=True)
                positions = json.loads(completed.stdout.strip().splitlines()[-1])
                self.assertLess(positions["본 견적은"][0] - positions["(인)"][1], 70, positions)

    def test_the_check_reports_a_last_page_the_layout_did_not_balance(self):
        subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", FORCED_ORPHAN, "orphan.pdf", "34"], cwd=self.directory, check=True)
        (self.directory / "orphan.pdf.source.json").write_text(json.dumps({"schema": "intl/report"}), encoding="utf-8")
        checked = run_office(["check", "orphan.pdf"], self.directory)
        pages = checked["details"]["pageFill"]
        if len(pages) > 1 and pages[-1] < 0.15:
            self.assertIn("LAST_PAGE_SPARSE", [issue["code"] for issue in checked["issues"]])
        self.assertEqual(checked["details"]["lastPageFill"], pages[-1])

    def test_a_file_that_is_not_a_schema_document_gets_measurements_but_no_balance_warning(self):
        subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", FORCED_ORPHAN, "plain.pdf", "34"], cwd=self.directory, check=True)
        checked = run_office(["check", "plain.pdf"], self.directory)
        self.assertIn("pageFill", checked["details"])
        self.assertNotIn("LAST_PAGE_SPARSE", [issue["code"] for issue in checked["issues"]])

    def test_word_documents_are_balanced_by_the_same_rules(self):
        short = self.checked("intl/report", report_values("ko", 1), "short.docx")
        self.assertGreaterEqual(short["details"]["pageFill"][0], 0.55)
        for paragraph_count in (14, 15, 16, 17):
            with self.subTest(paragraphs=paragraph_count):
                details = self.checked("intl/report", report_values("en", paragraph_count, 3), "long.docx")["details"]
                self.assertGreater(details["lastPageFill"], 0.15)


class SchemaLocationTest(unittest.TestCase):
    def test_every_bundled_schema_sits_in_a_country_folder_or_intl(self):
        schemas = Path(__file__).resolve().parents[1] / "skills" / "office" / "assets" / "schemas"
        misplaced = [str(path.relative_to(schemas)) for path in schemas.rglob("*.schema.json") if path.parent == schemas or not (path.parent.name == "intl" or (len(path.parent.name) == 2 and path.parent.name.isalpha() and path.parent.name.islower()))]
        self.assertEqual(misplaced, [])

    def test_the_universal_letter_and_report_choose_their_form_by_a_language_field(self):
        schemas = Path(__file__).resolve().parents[1] / "skills" / "office" / "assets" / "schemas"
        for kind in ("letter", "report"):
            with self.subTest(kind):
                document = json.loads((schemas / "intl" / f"{kind}.schema.json").read_text(encoding="utf-8"))
                self.assertEqual(document["name"], f"intl/{kind}")
                self.assertIn("language", [field["name"] for field in document["fields"]])


class StylingTest(unittest.TestCase):
    def test_document_styles_carry_no_one_sided_accent(self):
        office = Path(__file__).resolve().parents[1] / "skills" / "office"
        sources = [office / "assets" / "document-pdf" / "document-pdf.css", office / "scripts" / "doc" / "blocks" / "writers.py"]
        for source in sources:
            with self.subTest(source.name):
                text = source.read_text(encoding="utf-8")
                self.assertNotIn("border-left", text)
                self.assertNotIn("gradient", text)


if __name__ == "__main__":
    unittest.main()
