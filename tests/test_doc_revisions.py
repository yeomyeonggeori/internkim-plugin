import unittest
import zipfile

from doc_fixture import ContractFixture, block_texts, read_details, run_office, write_json


TRACKED_EDITS = [
    {"op": "replace_text", "find": "30일", "replace": "14일"},
    {"op": "set_text", "block": 5, "text": "계약 금액은 금 일천이백만 원(₩12,000,000)이며 부가가치세는 별도로 한다."},
    {"op": "insert_paragraph", "after": 7, "text": "단, 갑의 사정으로 검수가 지연된 기간은 지급 기한에 산입하지 아니한다."},
    {"op": "insert_table_row", "block": 8, "after": 1, "cells": ["중도금", "2,000,000"]},
    {"op": "delete_block", "block": 9},
]


class ReadRevisionsTest(ContractFixture):
    def test_revisions_list_type_author_date_block_and_text(self):
        details = read_details(self.directory, "contract.docx", "--revisions")
        self.assertEqual(details["revisionCount"], 2)
        self.assertEqual(details["revisions"], [
            {"id": "r1", "type": "formatting", "on": "properties", "author": "이샘플", "date": "2026-09-01T09:05:00Z", "block": 2, "text": "제1조 (목적)", "changed": ["bold"]},
            {"id": "r2", "type": "insertion", "on": "text", "author": "이샘플", "date": "2026-09-01T09:00:00Z", "block": 3, "text": " 세부 범위는 별첨 과업지시서에 따른다."},
        ])

    def test_check_names_who_left_changes_pending(self):
        issues = run_office(["doc", "check", "contract.docx"], self.directory)["issues"]
        pending = [issue for issue in issues if issue["code"] == "TRACKED_CHANGES_PRESENT"]
        self.assertIn("authors 이샘플 (2)", pending[0]["message"])


class TrackedEditTest(ContractFixture):
    def apply_tracked(self):
        write_json(self.directory / "edits.json", TRACKED_EDITS)
        envelope = run_office(["doc", "apply", "contract.docx", "edits.json", "--track", "--author", "박예시", "--output", "tracked.docx"], self.directory)
        self.assertEqual(envelope["status"], "ok")

    def test_tracked_edits_read_as_final_text_and_list_as_changes_by_their_author(self):
        self.apply_tracked()
        texts = block_texts(self.directory, "tracked.docx")
        self.assertEqual(texts[5], ("paragraph", "계약 금액은 금 일천이백만 원(₩12,000,000)이며 부가가치세는 별도로 한다."))
        self.assertEqual(texts[7], ("paragraph", "갑은 검수 완료일로부터 14일 이내에 을에게 계약 금액을 지급한다."))
        revisions = read_details(self.directory, "tracked.docx", "--revisions")["revisions"]
        edits = [(revision["type"], revision["text"]) for revision in revisions if revision["author"] == "박예시" and revision["on"] == "text"]
        self.assertEqual(edits[:6], [
            ("deletion", "일천만"), ("insertion", "일천이백만"), ("deletion", "10"), ("insertion", "12"),
            ("deletion", "30일"), ("insertion", "14일"),
        ])
        with zipfile.ZipFile(self.directory / "tracked.docx") as archive:
            document_xml = archive.read("word/document.xml").decode()
        self.assertIn('w:author="박예시"', document_xml)
        self.assertIn("<w:delText>30일</w:delText>", document_xml)

    def test_rejecting_every_change_restores_the_original_text(self):
        original = block_texts(self.directory, "contract.docx")
        self.apply_tracked()
        write_json(self.directory / "reject.json", [{"op": "reject_revisions", "author": "박예시"}])
        self.assertEqual(run_office(["doc", "apply", "tracked.docx", "reject.json"], self.directory)["status"], "ok")
        self.assertEqual(block_texts(self.directory, "tracked.docx"), original)
        self.assertEqual(read_details(self.directory, "tracked.docx")["revisionCount"], 2)

    def test_accepting_every_change_leaves_the_edited_text_and_no_marks(self):
        self.apply_tracked()
        write_json(self.directory / "accept.json", [{"op": "accept_revisions", "all": True}])
        self.assertEqual(run_office(["doc", "apply", "tracked.docx", "accept.json"], self.directory)["status"], "ok")
        texts = block_texts(self.directory, "tracked.docx")
        self.assertEqual(texts[3][1], "본 계약은 갑이 을에게 홈페이지 개편 용역을 위탁하고 을이 이를 수행하는 데 필요한 사항을 정한다. 세부 범위는 별첨 과업지시서에 따른다.")
        self.assertEqual(texts[8], ("paragraph", "단, 갑의 사정으로 검수가 지연된 기간은 지급 기한에 산입하지 아니한다."))
        self.assertEqual(texts[9], ("table", [["구분", "금액"], ["착수금", "3,000,000"], ["중도금", "2,000,000"], ["잔금", "7,000,000"]]))
        self.assertNotIn("본 계약의 성립을 증명하기 위하여 계약서 2부를 작성하여 각 1부씩 보관한다.", [text for _, text in texts])
        self.assertEqual(read_details(self.directory, "tracked.docx")["revisionCount"], 0)


class SettleSelectionTest(ContractFixture):
    def test_rejecting_a_formatting_change_restores_the_old_properties(self):
        write_json(self.directory / "reject.json", [{"op": "reject_revisions", "type": "formatting"}])
        self.assertEqual(run_office(["doc", "apply", "contract.docx", "reject.json"], self.directory)["status"], "ok")
        with zipfile.ZipFile(self.directory / "contract.docx") as archive:
            document_xml = archive.read("word/document.xml").decode()
        self.assertNotIn("<w:b/>", document_xml)
        self.assertNotIn("rPrChange", document_xml)
        self.assertEqual(read_details(self.directory, "contract.docx", "--revisions")["revisions"][0]["type"], "insertion")

    def test_an_unknown_id_names_the_ids_that_exist(self):
        write_json(self.directory / "accept.json", [{"op": "accept_revisions", "ids": ["r7"]}])
        envelope = run_office(["doc", "apply", "contract.docx", "accept.json"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["TARGET_NOT_FOUND"])
        self.assertIn("r1-r2", envelope["issues"][0]["suggestion"])

    def test_a_selector_is_required(self):
        write_json(self.directory / "accept.json", [{"op": "accept_revisions"}])
        envelope = run_office(["doc", "apply", "contract.docx", "accept.json"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["MISSING_FIELD"])


if __name__ == "__main__":
    unittest.main()
