import json
from pathlib import Path
import tempfile
import unittest

from doc_fixture import write_json
from schemas.claims import written_claims
from schemas.schema_document import load_schema
from test_schema_documents import QUOTE_VALUES, run_office_with_context, runtime_context, sample_schema

POSTMORTEM = {
    "language": "en",
    "title": "Checkout Outage Postmortem",
    "period": "2026-09-30/2026-09-30",
    "sections": [
        {"heading": "Root Cause", "blocks": [
            {"type": "paragraph", "text": "A change at 13:55 lowered max_connections to 20. The pool ran out at 14:12."},
        ]},
        {"heading": "Timeline", "blocks": [
            {"type": "table", "columns": [{"name": "Time", "type": "date"}, {"name": "Event", "type": "text"}, {"name": "Failed", "type": "quantity"}],
             "rows": [["2026-09-30 14:02", "Alert fired", 120]]},
        ]},
        {"heading": "Impact", "blocks": [
            {"type": "fields", "fields": [
                {"label": "Failed checkouts", "type": "quantity", "value": 1240},
                {"label": "Affected service", "type": "text", "value": "checkout"},
            ]},
        ]},
        {"heading": "Action Items", "blocks": [
            {"type": "items", "items": [{"text": "Add a connection-pool alert", "owner": "Jordan Example", "due": "2026-10-16"}]},
        ]},
    ],
}


def claim_texts(claims):
    return [claim["text"] for claim in claims]


class WrittenClaimsTest(unittest.TestCase):
    def test_only_the_values_the_model_wrote_as_text_are_claims(self):
        claims = written_claims(sample_schema(), {"buyer": "견본상사", "contact": None, "lines": [{"item": "노트북", "quantity": 2, "price": 1000}]})
        self.assertEqual(claims, [
            {"path": "buyer", "at": "Buyer", "text": "견본상사"},
            {"path": "lines[0].item", "at": "Lines > item", "text": "노트북"},
        ])

    def test_a_paragraph_is_one_claim_per_sentence(self):
        claims = written_claims(load_schema("report"), POSTMORTEM)
        paragraph = [claim for claim in claims if claim["path"].startswith("sections[0].blocks[0].text")]
        self.assertEqual([claim["path"] for claim in paragraph], ["sections[0].blocks[0].text#0", "sections[0].blocks[0].text#1"])
        self.assertEqual(paragraph[1]["text"], "The pool ran out at 14:12.")
        self.assertIn("Root Cause", paragraph[1]["at"])

    def test_a_cell_is_a_claim_only_when_its_column_or_field_is_text(self):
        texts = claim_texts(written_claims(load_schema("report"), POSTMORTEM))
        self.assertIn("Alert fired", texts)
        self.assertIn("checkout", texts)
        self.assertNotIn("2026-09-30 14:02", texts)
        self.assertNotIn(120, texts)
        self.assertIn("Failed checkouts", texts)

    def test_a_choice_such_as_a_block_kind_is_not_a_claim(self):
        texts = claim_texts(written_claims(load_schema("report"), POSTMORTEM))
        self.assertNotIn("paragraph", texts)
        self.assertNotIn("en", texts)

    def test_an_item_carries_its_text_and_owner(self):
        texts = claim_texts(written_claims(load_schema("report"), POSTMORTEM))
        self.assertIn("Add a connection-pool alert", texts)
        self.assertIn("Jordan Example", texts)

    def test_merge_writes_the_claims_beside_the_file_and_no_known_or_derived_value(self):
        with tempfile.TemporaryDirectory() as directory:
            write_json(Path(directory, "values.json"), QUOTE_VALUES)
            write_json(Path(directory, "context.json"), runtime_context())
            result = run_office_with_context(["merge", "kr/quote", "values.json", "quote.pdf"], directory, Path(directory, "context.json"))
            snapshot = json.loads(Path(directory, result["details"]["source"]).read_text(encoding="utf-8"))
        texts = claim_texts(snapshot["claims"])
        self.assertEqual(texts, ["견본상사", "한시범 과장", "납품 후 30일 이내 현금", "노트북", "대", "모니터", "대", "교육 용역", "식"])
        self.assertNotIn("샘플테크 주식회사", texts)
        self.assertNotIn("SAMPLE-1", texts)


if __name__ == "__main__":
    unittest.main()


class DeclarationClaimsTest(unittest.TestCase):
    def test_titles_and_text_cells_are_claims_and_numbers_and_members_typed_otherwise_are_not(self):
        from sheet.declaration_claims import declaration_claims
        declaration = {
            "kind": "workbook",
            "title": "지역별 매출",
            "tables": [{"name": "Data", "columns": [{"name": "Year", "type": "date"}, {"name": "Region"}, {"name": "Revenue", "type": "amount"}],
                        "rows": [["2025", "수도권", 820], ["2026", "호남", None]]}],
            "views": [{"sheet": "Summary", "title": "By quarter", "rows": ["Region"]}],
            "charts": [{"view": "By quarter", "type": "line", "title": "호남 실적은 시스템 장애로 지연되었습니다."}],
        }
        claims = declaration_claims(declaration)
        self.assertEqual([claim["text"] for claim in claims], ["지역별 매출", "수도권", "호남", "By quarter", "호남 실적은 시스템 장애로 지연되었습니다."])
        self.assertEqual(claims[1]["path"], "tables[0].rows[0][1]")
        self.assertEqual(claims[1]["at"], "Data > Region")
