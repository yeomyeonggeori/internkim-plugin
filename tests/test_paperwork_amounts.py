from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import SCRIPTS_PATH, run_office, write_json


from paperwork.amounts import korean_amount_in_words, korean_number_words
from paperwork.jurisdictions import find_jurisdiction


def quote(supply_total_text="1,000,000원", vat_text="100,000원", grand_total_text="1,100,000원", words="일금 일백일십만원정 (₩1,100,000) (부가세 포함)"):
    return {
        "title": "견 적 서",
        "profile": {"name": "예시상사"},
        "meta": [{"label": "합계금액", "value": words}, {"label": "견적일자", "value": "2026-09-30"}],
        "items": {
            "headers": ["품명", "규격", "수량", "단위", "단가", "공급가액", "세액"],
            "rows": [
                ["의자", "표준", "10", "개", "50,000", "500,000", "50,000"],
                ["책상", "표준", "5", "개", "100,000", "500,000", "50,000"],
            ],
            "totals": [
                {"label": "공급가액 합계", "value": supply_total_text},
                {"label": "부가세(10%)", "value": vat_text},
                {"label": "총 합계 (부가세 포함)", "value": grand_total_text},
            ],
        },
    }


def mismatches(envelope):
    return {fact["code"]: (fact["expected"], fact["found"]) for fact in envelope["details"]["facts"] if not fact["holds"]}


def fifteen_won_rows(row_vats, vat_total, grand_total="48"):
    headers = ["품명", "수량", "단가", "공급가액"] + ([] if row_vats is None else ["세액"])
    rows = [["품목", "1", "15", "15"] + ([] if row_vats is None else [row_vat]) for row_vat in (row_vats or ["", "", ""])]
    totals = [{"label": "공급가액 합계", "value": "45"}, {"label": "부가세", "value": vat_total}, {"label": "총 합계", "value": grand_total}]
    return {"title": "견 적 서", "items": {"headers": headers, "rows": rows, "totals": totals}}


class AmountArithmeticTest(unittest.TestCase):
    def test_a_korean_amount_drops_the_fraction_below_one_won(self):
        money = find_jurisdiction("kr").money
        self.assertEqual(money.rounded(Decimal("0.9")), 0)
        self.assertEqual(money.rounded(Decimal("-0.9")), 0)
        self.assertEqual(money.rounded(Decimal("1.5") * Decimal("333")), 499)

    def test_an_international_amount_rounds_half_up_to_the_cent(self):
        money = find_jurisdiction("intl").money
        self.assertEqual(money.rounded(Decimal("0.125")), Decimal("0.13"))
        self.assertEqual(money.rounded(Decimal("2.674")), Decimal("2.67"))


class KoreanWordsTest(unittest.TestCase):
    def test_edge_values(self):
        self.assertEqual(korean_amount_in_words(0), "일금 영원정")
        self.assertEqual(korean_amount_in_words(10_000), "일금 일만원정")
        self.assertEqual(korean_amount_in_words(1_000_000), "일금 일백만원정")
        self.assertEqual(korean_amount_in_words(123_456_789), "일금 일억이천삼백사십오만육천칠백팔십구원정")

    def test_empty_groups_are_skipped(self):
        self.assertEqual(korean_number_words(100_000_001), "일억일")
        self.assertEqual(korean_number_words(10_010), "일만일십")


DIGIT_VALUES = {digit: value for value, digit in enumerate("영일이삼사오육칠팔구")}
SMALL_UNIT_VALUES = {"십": 10, "백": 100, "천": 1000}
LARGE_UNIT_VALUES = {"만": 10**4, "억": 10**8, "조": 10**12, "경": 10**16}


def spoken_value(words):
    total, group, digit = 0, 0, 0
    for character in words:
        if character in DIGIT_VALUES:
            digit = DIGIT_VALUES[character]
        elif character in SMALL_UNIT_VALUES:
            group, digit = group + digit * SMALL_UNIT_VALUES[character], 0
        else:
            total, group, digit = total + (group + digit) * LARGE_UNIT_VALUES[character], 0, 0
    return total + group + digit


def sample_amounts():
    rounds = [10**power for power in range(17)]
    edges = [base * multiple + offset for base in rounds for multiple in (1, 2, 9) for offset in (-1, 0, 1) if base * multiple + offset > 0]
    inner_zeros = [27_750_800, 10_000_800, 100_000_080, 1_002_003_004, 5_000_000_001, 30_000_000_000_700, 12_340_000_5678, 90_090_090_090]
    generator = __import__("random").Random(20261003)
    randoms = [generator.randrange(1, 10**digits) for digits in range(1, 18) for _ in range(40)]
    return sorted(set(edges + inner_zeros + randoms))


class KoreanWordsPropertyTest(unittest.TestCase):
    def test_spoken_words_read_back_to_the_same_number(self):
        for amount in sample_amounts():
            with self.subTest(amount=amount):
                self.assertEqual(spoken_value(korean_number_words(amount)), amount)

    def test_zero_is_never_spoken_inside_a_number(self):
        for amount in sample_amounts():
            with self.subTest(amount=amount):
                self.assertNotIn("영", korean_number_words(amount))

    def test_every_digit_is_followed_by_its_place(self):
        for amount in sample_amounts():
            words = korean_number_words(amount)
            with self.subTest(amount=amount):
                for position, character in enumerate(words[:-1]):
                    if character in DIGIT_VALUES:
                        self.assertNotIn(words[position + 1], DIGIT_VALUES)


class CheckCommandTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def check(self, document, form="kr/quote"):
        write_json(self.directory / "quote.json", {"form": form, **document})
        return run_office(["check", "quote.json"], self.directory)

    def test_a_correct_quote_passes(self):
        envelope = self.check(quote(words="일금 일백일십만원정 (₩1,100,000) (부가세 포함)"))
        self.assertEqual((envelope["status"], envelope["issues"]), ("ok", []))
        self.assertEqual(envelope["details"]["vatRatePercent"], 10)

    def test_a_wrong_vat_and_total_are_reported_with_expected_and_found(self):
        envelope = self.check(quote(vat_text="90,000원", grand_total_text="1,200,000원"))
        issues = {issue["code"]: issue for issue in envelope["issues"]}
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(set(issues), {"VAT_MISMATCH", "GRAND_TOTAL_MISMATCH", "AMOUNT_IN_WORDS_MISMATCH"})
        self.assertEqual(mismatches(envelope)["VAT_MISMATCH"], (100_000, 90_000))
        self.assertEqual(mismatches(envelope)["GRAND_TOTAL_MISMATCH"], (1_090_000, 1_200_000))
        self.assertEqual(issues["VAT_MISMATCH"]["suggestion"], "correct the VAT line: write 100000")
        self.assertEqual(issues["VAT_MISMATCH"]["location"], "items.totals[1].value")

    def test_a_wrong_row_and_supply_total_are_reported(self):
        document = quote()
        document["items"]["rows"][1][5] = "400,000"
        codes = {issue["code"]: issue["location"] for issue in self.check(document)["issues"]}
        self.assertEqual(codes["ROW_AMOUNT_MISMATCH"], "items.rows[1][5]")
        self.assertEqual(codes["SUPPLY_TOTAL_MISMATCH"], "items.totals[0].value")

    def test_row_vats_set_the_vat_total_and_each_row_is_truncated(self):
        document = fifteen_won_rows(row_vats=["1", "1", "1"], vat_total="3")
        self.assertEqual(self.check(document)["issues"], [])
        document = fifteen_won_rows(row_vats=["1", "2", "1"], vat_total="4")
        envelope = self.check(document)
        issues = {issue["code"]: issue for issue in envelope["issues"]}
        self.assertEqual(mismatches(envelope)["ROW_VAT_MISMATCH"], (1, 2))
        self.assertEqual(issues["ROW_VAT_MISMATCH"]["location"], "items.rows[1][4]")
        self.assertNotIn("VAT_MISMATCH", issues)

    def test_the_vat_total_must_equal_the_row_vat_sum_not_the_truncated_supply_vat(self):
        envelope = self.check(fifteen_won_rows(row_vats=["1", "1", "1"], vat_total="4", grand_total="49"))
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["VAT_MISMATCH"])
        self.assertEqual(mismatches(envelope), {"VAT_MISMATCH": (3, 4)})

    def test_without_row_vats_the_vat_total_is_truncated_from_the_supply_total(self):
        self.assertEqual(self.check(fifteen_won_rows(row_vats=None, vat_total="4", grand_total="49"))["issues"], [])
        envelope = self.check(fifteen_won_rows(row_vats=None, vat_total="3", grand_total="48"))
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["VAT_MISMATCH"])
        self.assertEqual(mismatches(envelope), {"VAT_MISMATCH": (4, 3)})

    def test_a_row_without_tax_is_checked_against_zero_and_left_out_of_the_tax_total(self):
        document = quote(supply_total_text="1,180,000원", vat_text="100,000원", grand_total_text="1,280,000원", words="일금 일백이십팔만원정")
        document["items"]["rows"].append(["견본 도서", "문고판", "12", "권", "15,000", "180,000", "0"])
        document["items"]["untaxedRows"] = [2]
        self.assertEqual(self.check(document)["issues"], [])
        document["items"]["rows"][2][6] = "18,000"
        envelope = self.check(document)
        self.assertEqual(mismatches(envelope)["ROW_VAT_MISMATCH"], (0, 18_000))
        self.assertEqual(mismatches(envelope)["VAT_MISMATCH"], (118_000, 100_000))

    def test_a_row_without_tax_is_checked_as_taxed_unless_the_values_say_so(self):
        document = quote(supply_total_text="1,180,000원", vat_text="100,000원", grand_total_text="1,280,000원", words="일금 일백이십팔만원정")
        document["items"]["rows"].append(["견본 도서", "문고판", "12", "권", "15,000", "180,000", "0"])
        self.assertEqual(mismatches(self.check(document))["ROW_VAT_MISMATCH"], (18_000, 0))

    def test_without_a_tax_column_untaxed_rows_leave_the_supply_total_tax_base(self):
        document = fifteen_won_rows(row_vats=None, vat_total="3", grand_total="48")
        document["items"]["untaxedRows"] = [0]
        self.assertEqual(self.check(document)["issues"], [])
        document["items"]["untaxedRows"] = []
        self.assertEqual(mismatches(self.check(document)), {"VAT_MISMATCH": (4, 3)})

    def test_an_international_zero_rated_row_carries_no_tax_at_the_stated_rate(self):
        items = {
            "headers": ["Item", "Qty", "Unit price", "Amount", "Tax"],
            "rows": [["Consulting", "2", "500.00", "1,000.00", "200.00"], ["Exported hardware", "1", "750.00", "750.00", "0.00"]],
            "untaxedRows": [1],
            "totals": [{"label": "Subtotal", "value": "1,750.00"}, {"label": "VAT", "value": "200.00"}, {"label": "Total", "value": "1,950.00"}],
        }
        self.assertEqual(self.check({"items": items, "taxRatePercent": 20}, form="intl/invoice")["issues"], [])

    def test_a_spelled_total_with_the_old_hanja_suffix_matches(self):
        envelope = self.check(quote(words="일금 일백일십만원整 (₩1,100,000) (부가세 포함)"))
        self.assertEqual(envelope["issues"], [])

    def test_a_cell_without_a_number_is_unreadable(self):
        document = quote()
        document["items"]["rows"][0][2] = "열 개"
        self.assertIn("AMOUNT_UNREADABLE", [issue["code"] for issue in self.check(document)["issues"]])

    def test_a_contract_amount_in_words_is_checked(self):
        envelope = self.check({"totalAmount": "50,000,000", "totalAmountKorean": "일금 오천만원整"})
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["AMOUNT_IN_WORDS_MISMATCH"])
        self.assertEqual(mismatches(envelope)["AMOUNT_IN_WORDS_MISMATCH"][0], "오천만")
        self.assertEqual(self.check({"totalAmount": "50,000,000", "totalAmountKorean": "오천만"})["issues"], [])

    def test_an_input_without_amounts_warns(self):
        self.assertEqual([issue["code"] for issue in self.check({"title": "회의록"})["issues"]], ["NO_AMOUNTS_FOUND"])

    def test_values_that_name_no_form_are_refused(self):
        write_json(self.directory / "quote.json", quote())
        envelope = run_office(["check", "quote.json"], self.directory)
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("MISSING_FIELD", "values.form")])

    def test_an_international_form_checks_tax_only_at_the_rate_it_states(self):
        rows = {"headers": ["Item", "Qty", "Unit price", "Amount"], "rows": [["Hours", "3", "33.335", "100.01"]], "totals": [{"label": "Subtotal", "value": "100.01"}, {"label": "Tax", "value": "7"}, {"label": "Total", "value": "107.01"}]}
        unstated = self.check({"items": rows}, form="intl/invoice")
        self.assertEqual((unstated["issues"], unstated["details"]["vatRatePercent"]), ([], None))
        self.assertNotIn("VAT_MISMATCH", {fact["code"] for fact in unstated["details"]["facts"]})
        stated = self.check({"items": rows, "taxRatePercent": 8}, form="intl/invoice")
        self.assertEqual(mismatches(stated), {"VAT_MISMATCH": (8, 7)})
        self.assertEqual(stated["details"]["vatRatePercent"], 8)

    def test_the_guide_lists_the_command_rules_and_codes(self):
        guide = run_guide("form")
        for text in ("office check <values.json>", "truncates toward zero", "rounds half up", "VAT_MISMATCH", "AMOUNT_IN_WORDS_MISMATCH"):
            self.assertIn(text, guide)


def run_guide(topic):
    return subprocess.run([sys.executable, str(SCRIPTS_PATH / "office"), "guide", topic], capture_output=True, text=True, check=True).stdout


if __name__ == "__main__":
    unittest.main()
