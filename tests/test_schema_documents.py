from datetime import date
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, write_json

from core.office_result import OfficeFailure
from schemas.expression import Scope, evaluate, parse_expression
from schemas.given_values import blank_fields, input_json_schema, normalized_values, validated_values
from schemas.resolution import Instance, compute_derived, render_template
from schemas.schema_document import load_schema, schema_from_document
from schemas.typed_values import BLANK


def scope(values, lists=None):
    return Scope(lambda name: values.get(name), lambda name: (lists or {}).get(name), lambda value: value.quantize(Decimal(1)), lambda value: f"words {value}")


def sample_schema():
    return schema_from_document({
        "name": "sample/order",
        "kind": "form",
        "fields": [
            {"name": "buyer", "label": "Buyer", "type": "organization"},
            {"name": "contact", "label": "Contact", "type": "person", "optional": True},
            {"name": "lines", "label": "Lines", "type": "list", "fields": [
                {"name": "item", "type": "text"},
                {"name": "quantity", "type": "quantity"},
                {"name": "price", "type": "amount", "unit": "KRW"},
            ]},
        ],
        "known": {"issued": "today", "company": "company"},
        "derived": [
            {"name": "lines.amount", "type": "amount", "unit": "KRW", "expression": "lines.quantity * lines.price"},
            {"name": "total", "type": "amount", "unit": "KRW", "expression": "sum(lines.amount)"},
        ],
    }, None)


def sample_instance(given):
    schema = sample_schema()
    instance = Instance(schema, normalized_values(schema.fields, given), {"issued": date(2026, 10, 4), "company": {"name": "Sample Co"}}, "ko")
    compute_derived(instance)
    return instance


def with_company_files(context_path):
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    for language, profile in (context.get("company") or {}).items():
        if isinstance(profile, dict):
            profile_path = Path(context_path).with_name(f"company-profile.{language}.json")
            write_json(profile_path, profile)
            context["company"][language] = str(profile_path)
    write_json(context_path, context)


def run_office_with_context(arguments, working_directory, context_path):
    with_company_files(context_path)
    environment = dict(os.environ, OFFICE_RUNTIME_CONTEXT=str(context_path))
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=working_directory, env=environment)
    return json.loads(completed.stdout)


def runtime_context(today="2026-10-04", number="SAMPLE-1"):
    return {
        "requester": {"name": "이샘플"},
        "today": today,
        "company": {"ko": {"name": "샘플테크 주식회사", "representative": "최견본", "representativeTitle": "대표이사", "bankAccount": "예시은행 123-456"}},
        "registeredDocuments": [{"documentNumber": number}] if number else [],
    }


QUOTE_VALUES = {
    "recipient": "견본상사",
    "contact": "한시범 과장",
    "validDays": 30,
    "delivery": None,
    "deliveryPlace": None,
    "paymentTerms": "납품 후 30일 이내 현금",
    "items": [
        {"name": "노트북", "quantity": 10, "unit": "대", "unitPrice": 1350000},
        {"name": "모니터", "quantity": 10, "unit": "대", "unitPrice": "289,000"},
        {"name": "교육 용역", "quantity": 1, "unit": "식", "unitPrice": 400000, "taxExempt": True},
    ],
}


class ExpressionTest(unittest.TestCase):
    def test_arithmetic_follows_precedence(self):
        self.assertEqual(evaluate(parse_expression("a + b * 2", "e"), scope({"a": Decimal(1), "b": Decimal(3)})), Decimal(7))

    def test_a_missing_operand_makes_the_result_missing_rather_than_zero(self):
        self.assertIsNone(evaluate(parse_expression("a * b", "e"), scope({"a": Decimal(2), "b": None})))

    def test_a_sum_over_a_list_with_a_missing_value_is_missing(self):
        lists = {"lines.amount": [Decimal(1), None]}
        self.assertIsNone(evaluate(parse_expression("sum(lines.amount)", "e"), scope({}, lists)))

    def test_a_sum_over_an_empty_list_is_zero(self):
        self.assertEqual(evaluate(parse_expression("sum(lines.amount)", "e"), scope({}, {"lines.amount": []})), Decimal(0))

    def test_division_by_zero_is_missing(self):
        self.assertIsNone(evaluate(parse_expression("a / b", "e"), scope({"a": Decimal(1), "b": Decimal(0)})))

    def test_a_date_moves_by_days(self):
        self.assertEqual(evaluate(parse_expression("addDays(start, days)", "e"), scope({"start": "2026-10-04", "days": Decimal(30)})), date(2026, 11, 3))

    def test_an_unknown_function_is_refused_when_the_schema_is_read(self):
        with self.assertRaises(OfficeFailure):
            parse_expression("median(a)", "derived[0].expression")

    def test_names_may_be_any_language_or_quoted(self):
        self.assertEqual(evaluate(parse_expression("`unit price` * 매출", "e"), scope({"unit price": Decimal(2), "매출": Decimal(3)})), Decimal(6))


class GuideTest(unittest.TestCase):
    def guide(self, arguments):
        return subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True).stdout

    def test_a_schema_guide_answers_however_it_is_asked_for(self):
        for arguments in (["guide", "intl/report"], ["guide", "merge", "intl/report"], ["merge", "intl/report", "--help"]):
            self.assertIn("office merge intl/report <values.json> <output>", self.guide(arguments), arguments)


class InputSchemaTest(unittest.TestCase):
    def test_the_model_sees_only_the_given_fields(self):
        properties = input_json_schema(sample_schema())["properties"]
        self.assertEqual(sorted(properties), ["buyer", "contact", "lines"])
        self.assertEqual(sorted(input_json_schema(sample_schema())["properties"]["lines"]["items"]["properties"]), ["item", "price", "quantity"])

    def test_every_structure_is_closed_and_every_value_nullable(self):
        schema = input_json_schema(sample_schema())
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["lines"]["items"]["additionalProperties"])
        self.assertIn("null", schema["properties"]["buyer"]["type"])
        self.assertIn("null", schema["properties"]["lines"]["items"]["properties"]["price"]["type"])

    def test_an_optional_field_may_be_left_out(self):
        self.assertEqual(input_json_schema(sample_schema())["required"], ["buyer", "lines"])

    def test_a_bundled_schema_holds_no_runtime_or_derived_field_in_its_input(self):
        schema = load_schema("kr/quote")
        given = set(input_json_schema(schema)["properties"])
        self.assertFalse(given & (set(schema.known) | {entry.name for entry in schema.derived}))


class GivenValueTest(unittest.TestCase):
    def test_a_field_the_runtime_fills_is_refused_with_its_reason(self):
        with self.assertRaises(OfficeFailure) as raised:
            validated_values(sample_schema(), {"buyer": "A", "lines": [], "total": 5})
        self.assertIn("filled by the runtime or computed", raised.exception.issues[0].message)

    def test_a_wrong_value_names_its_path(self):
        with self.assertRaises(OfficeFailure) as raised:
            validated_values(sample_schema(), {"buyer": "A", "lines": [{"item": "x", "quantity": 1, "price": "about ten"}]})
        self.assertEqual(raised.exception.issues[0].location, "values.lines[0].price")

    def test_a_number_written_with_separators_is_read_as_the_number(self):
        given = {"buyer": "A", "lines": [{"item": "x", "quantity": 2, "price": "1,350,000"}]}
        validated_values(sample_schema(), given)
        self.assertEqual(sample_instance(given).derived["total"], Decimal(2700000))


class BlankFieldTest(unittest.TestCase):
    def test_a_needed_value_left_null_is_a_blank(self):
        self.assertEqual(blank_fields(sample_schema().fields, {"buyer": None, "lines": []}), [{"field": "buyer", "label": "Buyer"}])

    def test_an_optional_value_left_out_is_not_a_blank(self):
        self.assertEqual(blank_fields(sample_schema().fields, {"buyer": "A", "lines": []}), [])

    def test_an_optional_value_written_as_null_is_left_out_rather_than_blank(self):
        self.assertEqual(blank_fields(sample_schema().fields, {"buyer": "A", "contact": None, "lines": []}), [])

    def test_a_blank_inside_a_list_names_its_row(self):
        blanks = blank_fields(sample_schema().fields, {"buyer": "A", "lines": [{"item": "x", "quantity": None, "price": 1}]})
        self.assertEqual(blanks, [{"field": "lines[0].quantity", "label": "quantity"}])


class TemplateTest(unittest.TestCase):
    def test_a_line_naming_an_optional_value_left_out_disappears(self):
        self.assertIsNone(render_template(sample_instance({"buyer": "A", "lines": []}), "{contact} 님"))

    def test_a_cell_holding_only_a_blank_value_is_empty(self):
        self.assertEqual(render_template(sample_instance({"buyer": None, "lines": []}), "{buyer}"), "")

    def test_a_blank_inside_text_is_a_line_to_fill_by_hand(self):
        self.assertEqual(render_template(sample_instance({"buyer": None, "lines": []}), "To {buyer}"), f"To {BLANK}")

    def test_known_and_derived_values_are_formatted_by_type(self):
        instance = sample_instance({"buyer": "A", "lines": [{"item": "x", "quantity": 3, "price": 1000}]})
        self.assertEqual(render_template(instance, "{issued} {total} {company.name}"), "2026년 10월 4일 3,000원 Sample Co")

    def test_the_first_alternative_that_renders_is_used(self):
        instance = sample_instance({"buyer": "A", "lines": []})
        self.assertEqual(render_template(instance, ["{contact} at {buyer}", "{buyer}"]), "A")


class QuoteMergeTest(unittest.TestCase):
    def merge(self, directory, values, context):
        write_json(Path(directory, "values.json"), values)
        write_json(Path(directory, "context.json"), context)
        return run_office_with_context(["merge", "kr/quote", "values.json", "quote.pdf"], directory, Path(directory, "context.json"))

    def pdf_text(self, directory):
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "read", "quote.pdf"], capture_output=True, text=True, cwd=directory)
        return json.dumps(json.loads(completed.stdout), ensure_ascii=False)

    def test_amounts_tax_and_totals_are_computed_and_blanks_listed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.merge(directory, QUOTE_VALUES, runtime_context())
            self.assertEqual(result["status"], "ok", result)
            self.assertEqual([blank["label"] for blank in result["details"]["blanks"]], ["납기", "납품장소"])
            text = self.pdf_text(directory)
            for expected in ("16,790,000원", "1,639,000원", "18,429,000원", "SAMPLE-1", "2026년 10월 4일", "최견본"):
                self.assertIn(expected, text)

    def test_a_task_whose_company_profile_was_never_read_is_told_to_read_it(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.merge(directory, QUOTE_VALUES, runtime_context() | {"company": {}})
            self.assertEqual(result["status"], "error")
            issue = result["issues"][0]
            self.assertEqual(issue["code"], "COMPANY_NOT_READ")
            self.assertIn("company_info_get", issue["suggestion"])
            self.assertIn("'ko'", issue["suggestion"])
            self.assertFalse(Path(directory, "quote.pdf").exists())

    def test_a_runtime_field_in_the_values_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.merge(directory, {**QUOTE_VALUES, "number": "X-1"}, runtime_context())
            self.assertEqual(result["status"], "error")
            self.assertIn("filled by the runtime", result["issues"][0]["message"])

    def test_completing_a_blank_keeps_the_number_and_date_of_the_first_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            self.merge(directory, QUOTE_VALUES, runtime_context())
            completed = {**QUOTE_VALUES, "delivery": "발주 후 2주", "deliveryPlace": "견본상사 본사"}
            result = self.merge(directory, completed, runtime_context(today="2026-10-06", number="SAMPLE-2"))
            self.assertEqual(result["details"]["blanks"], [])
            text = self.pdf_text(directory)
            self.assertIn("SAMPLE-1", text)
            self.assertIn("2026년 10월 4일", text)
            self.assertNotIn("SAMPLE-2", text)


    def test_the_company_comes_from_the_profile_file_the_runtime_context_names(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = runtime_context()["company"]["ko"] | {"name": "프로필파일 주식회사"}
            write_json(Path(directory, "company-profile.json"), profile)
            context = runtime_context() | {"company": {"ko": str(Path(directory, "company-profile.json"))}}
            result = self.merge(directory, QUOTE_VALUES, context)
            self.assertEqual(result["status"], "ok", result)
            self.assertIn("프로필파일 주식회사", self.pdf_text(directory))

    def test_a_number_not_yet_registered_is_drawn_as_the_blank_the_result_lists(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.merge(directory, QUOTE_VALUES, runtime_context(number=""))
            self.assertIn("number (document.number)", [blank["label"] for blank in result["details"]["blanks"]])
            self.assertIn("문서번호 __________", self.pdf_text(directory))

    def test_the_registered_number_is_the_last_one_the_runtime_context_lists(self):
        with tempfile.TemporaryDirectory() as directory:
            context = runtime_context() | {"registeredDocuments": [{"documentNumber": "QT-2026-0001"}, {"documentNumber": "QT-2026-0002"}]}
            result = self.merge(directory, QUOTE_VALUES, context)
            self.assertNotIn("number (document.number)", [blank["label"] for blank in result["details"]["blanks"]])
            self.assertIn("문서번호 QT-2026-0002", self.pdf_text(directory))

    def test_an_optional_column_left_empty_is_reported_apart_from_the_blanks(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.merge(directory, QUOTE_VALUES, runtime_context())
            self.assertIn({"field": "items[].spec", "label": "품목: 규격, empty in 3 of 3 rows"}, result["details"]["emptyOptional"])
            self.assertNotIn("items[].spec", [blank["field"] for blank in result["details"]["blanks"]])

    def test_a_number_registered_after_the_first_merge_is_taken_on_the_next(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.merge(directory, QUOTE_VALUES, runtime_context(number=""))
            self.assertIn("number (document.number)", [blank["label"] for blank in first["details"]["blanks"]])
            self.merge(directory, QUOTE_VALUES, runtime_context(number="SAMPLE-3"))
            self.assertIn("SAMPLE-3", self.pdf_text(directory))


class InvoiceMergeTest(unittest.TestCase):
    def test_a_tax_rate_the_request_does_not_state_leaves_tax_and_total_blank(self):
        values = {"billTo": "Example Retail Inc.", "currency": "USD", "paymentDays": 30, "poNumber": "PO-1", "taxRatePercent": None,
                  "items": [{"description": "Consulting", "quantity": 10, "unitPrice": 100}]}
        context = runtime_context() | {"company": {"en": {"name": "Sample Co", "representative": "Sample Person", "representativeTitle": "CEO"}}}
        with tempfile.TemporaryDirectory() as directory:
            write_json(Path(directory, "values.json"), values)
            write_json(Path(directory, "context.json"), context)
            result = run_office_with_context(["merge", "intl/invoice", "values.json", "invoice.pdf"], directory, Path(directory, "context.json"))
            self.assertEqual(result["status"], "ok", result)
            self.assertIn("Tax rate", [blank["label"] for blank in result["details"]["blanks"]])
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "read", "invoice.pdf"], capture_output=True, text=True, cwd=directory)
            text = json.dumps(json.loads(completed.stdout), ensure_ascii=False)
            self.assertIn("Subtotal 1,000 USD", text)
            self.assertIn("Total due __________ USD", text)
            self.assertIn("Tax rate __________", text)


class LayoutPlacementTest(unittest.TestCase):
    def test_a_schema_whose_layout_never_places_a_required_field_is_refused(self):
        schema = {"name": "sample", "kind": "document", "language": "en", "fields": [{"name": "title"}, {"name": "owner", "type": "person"}],
                  "known": {"date": "today"}, "layout": {"parts": [{"type": "heading", "text": "{title}"}]}}
        with tempfile.TemporaryDirectory() as directory:
            write_json(Path(directory, "sample.schema.json"), schema)
            write_json(Path(directory, "values.json"), {"title": "T", "owner": None})
            write_json(Path(directory, "context.json"), runtime_context())
            result = run_office_with_context(["merge", "sample.schema.json", "values.json", "out.pdf"], directory, Path(directory, "context.json"))
        self.assertEqual(result["status"], "error")
        self.assertIn("never places owner, date", result["issues"][0]["message"])

    def test_every_bundled_schema_places_each_field_it_can_report_blank(self):
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", "from schemas.schema_document import load_schema, bundled_schema_names; [load_schema(name) for name in bundled_schema_names()]"], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)


class MinutesMergeTest(unittest.TestCase):
    def test_sections_are_numbered_in_the_order_they_appear(self):
        values = {"meetingName": "Review", "startsAt": "2026-10-04 10:00", "endsAt": "2026-10-04 11:00", "place": None, "attendees": ["박예시"], "agenda": ["예산"], "decisions": ["유지"], "actions": []}
        with tempfile.TemporaryDirectory() as directory:
            write_json(Path(directory, "values.json"), values)
            write_json(Path(directory, "context.json"), runtime_context())
            result = run_office_with_context(["merge", "kr/meeting-minutes", "values.json", "minutes.pdf"], directory, Path(directory, "context.json"))
            self.assertEqual(result["status"], "ok", result)
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "read", "minutes.pdf"], capture_output=True, text=True, cwd=directory)
            text = json.loads(completed.stdout)["details"]["pages"][0]["text"]
            self.assertIn("1. 안건", text)
            self.assertIn("2. 결정사항", text)


class ReportMergeTest(unittest.TestCase):
    def merge_report(self, directory, values):
        write_json(Path(directory, "values.json"), values)
        write_json(Path(directory, "context.json"), runtime_context())
        return run_office_with_context(["merge", "intl/report", "values.json", "status.pdf"], directory, Path(directory, "context.json"))

    def test_a_period_of_one_day_is_written_once(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.merge_report(directory, {"language": "en", "title": "Outage", "period": "2026-09-30/2026-09-30", "sections": []})
            self.assertEqual(result["status"], "ok", result)
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "read", "status.pdf"], capture_output=True, text=True, cwd=directory)
            text = json.loads(completed.stdout)["details"]["pages"][0]["text"]
            self.assertIn("Period: September 30, 2026\n", text)

    def test_a_table_cell_left_null_is_a_blank_and_its_total_stays_blank(self):
        values = {"language": "en", "title": "Status", "sections": [{"heading": "Spend", "blocks": [{"type": "table", "columns": [{"name": "Item", "type": "text"}, {"name": "Cost", "type": "amount", "unit": "USD"}], "rows": [["A", 10], ["B", None]], "totals": True}]}]}
        with tempfile.TemporaryDirectory() as directory:
            write_json(Path(directory, "values.json"), values)
            write_json(Path(directory, "context.json"), runtime_context())
            result = run_office_with_context(["merge", "intl/report", "values.json", "status.docx"], directory, Path(directory, "context.json"))
            self.assertEqual(result["status"], "ok", result)
            self.assertEqual([blank["label"] for blank in result["details"]["blanks"]], ["B Cost"])


if __name__ == "__main__":
    unittest.main()
