from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, run_office, write_form_values
from render_fixture import can_render
from test_paperwork_layout import PAGE_TEXTS

from schemas.form_layout import paperwork_document
from schemas.given_values import normalized_values
from schemas.resolution import Instance, compute_derived
from schemas.schema_document import schema_from_document


LONG_KOREAN = "예산코드와 관련 품의 번호, 납품 장소, 검수 일정까지 한 칸에 적은 아주 긴 적요 문장입니다 "
LONG_ENGLISH = "Description of the work package including the purchase order reference, the delivery site and the inspection schedule "


def schema_with_list(list_fields, columns, meta=()):
    return schema_from_document({
        "name": "sample/schedule",
        "kind": "form",
        "fields": [{"name": "tasks", "label": "Tasks", "type": "list", "fields": list_fields}],
        "known": {"issueDate": "today"},
        "layout": {"meta": list(meta), "items": {"list": "tasks", "columns": columns}},
    }, None)


def laid_out(schema, rows):
    instance = Instance(schema, normalized_values(schema.fields, {"tasks": rows}), {"issueDate": date(2026, 10, 4)}, "ko")
    compute_derived(instance)
    return paperwork_document(instance)


class ValueKindsFromTheSchemaTest(unittest.TestCase):
    def test_a_date_column_is_a_date_kind_and_a_text_column_is_not(self):
        schema = schema_with_list(
            [{"name": "title", "type": "text"}, {"name": "due", "type": "date"}],
            [{"header": "Task", "value": "{title}"}, {"header": "Due", "value": "{due}", "align": "C"}],
        )
        document = laid_out(schema, [{"title": "Survey", "due": "2026-11-30"}])
        self.assertEqual(document["items"]["kinds"], ["text", "date"])
        self.assertEqual(document["items"]["rows"], [["Survey", "2026년 11월 30일"]])

    def test_figures_and_percentages_are_their_own_kinds(self):
        schema = schema_with_list(
            [{"name": "title", "type": "text"}, {"name": "hours", "type": "quantity"}, {"name": "share", "type": "percent"}, {"name": "fee", "type": "amount", "unit": "KRW"}],
            [{"header": "Task", "value": "{title}"}, {"header": "Hours", "value": "{hours}"}, {"header": "Share", "value": "{share}"}, {"header": "Fee", "value": "{fee}"}],
        )
        document = laid_out(schema, [{"title": "Survey", "hours": 4, "share": 20, "fee": 1000}])
        self.assertEqual(document["items"]["kinds"], ["text", "quantity", "percent", "amount"])

    def test_a_meta_row_made_only_of_dates_is_a_date_and_mixed_text_is_not(self):
        schema = schema_with_list(
            [{"name": "title", "type": "text"}],
            [{"header": "Task", "value": "{title}"}],
            meta=[{"label": "Issued", "value": "{issueDate}"}, {"label": "Note", "value": "issued {issueDate}"}],
        )
        document = laid_out(schema, [{"title": "Survey"}])
        self.assertEqual([row["kind"] for row in document["meta"]], ["date", "text"])


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class DateStaysWholeTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def text_of(self, values: dict) -> str:
        write_form_values(self.directory / "values.json", values)
        envelope = run_office(["merge", values["form"], "values.json", "form.pdf"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", PAGE_TEXTS, "form.pdf"], cwd=self.directory, capture_output=True, text=True, check=True)
        return "".join(json.loads(completed.stdout))

    def form(self, headers, aligns, kinds, row, form="kr/expense-approval", title="지 출 결 의 서"):
        return {"form": form, "title": title, "profile": {"name": "주식회사 견본상회"}, "items": {"headers": headers, "aligns": aligns, "kinds": kinds, "rows": [row]}}

    def test_a_korean_date_in_a_narrow_column_stays_on_one_line(self):
        dates = ["2026년 10월 4일", "2026년 12월 31일"]
        values = self.form(["적요", "담당", "착수", "비고", "완료"], ["L", "L", "C", "L", "C"], ["text", "text", "date", "text", "date"], [LONG_KOREAN, "예시 담당자", dates[0], LONG_KOREAN, dates[1]])
        text = self.text_of(values)
        for value in dates:
            self.assertIn(value, text)

    def test_an_english_date_in_a_narrow_column_stays_on_one_line(self):
        dates = ["October 4, 2026", "December 31, 2026"]
        values = self.form(["Work", "Owner", "Start", "Notes", "End"], ["L", "L", "C", "L", "C"], ["text", "text", "date", "text", "date"], [LONG_ENGLISH, "Sample Owner", dates[0], LONG_ENGLISH, dates[1]], form="intl/purchase-order", title="Order")
        text = self.text_of(values)
        for value in dates:
            self.assertIn(value, text)

    def test_the_column_takes_the_width_the_date_needs_beside_other_wide_columns(self):
        dates = [f"2026년 {month}월 {day}일" for month, day in ((1, 1), (11, 30), (12, 31))]
        values = self.form(["내용", "일자", "내용 2", "내용 3"], ["L", "C", "L", "L"], ["text", "date", "text", "text"], [LONG_KOREAN, dates[1], LONG_KOREAN, LONG_KOREAN])
        values["items"]["rows"] = [[LONG_KOREAN, value, LONG_KOREAN, LONG_KOREAN] for value in dates]
        text = self.text_of(values)
        for value in dates:
            self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
