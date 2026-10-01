import subprocess
import sys
import unittest
import zipfile

from doc_fixture import DocumentFixture, block_texts, run_office, write_json
from doc_fixture import OFFICE_ENTRY, SCRIPTS_PATH


class ReadTest(DocumentFixture):
    def test_blocks_are_indexed_in_body_order(self):
        self.assertEqual(block_texts(self.directory, "fixture.docx"), [
            ("heading", "개요"),
            ("paragraph", "첫 문단 {{ customer_name }} 입니다."),
            ("paragraph", "둘째 문단"),
            ("table", [["항목", "값"], ["매출", "100"]]),
            ("heading", "결론"),
        ])


class ApplyTest(DocumentFixture):
    def test_a_batch_applies_every_operation_against_the_indexes_read_before_it(self):
        write_json(self.directory / "ops.json", [
            {"op": "delete_block", "block": 2},
            {"op": "insert_paragraph", "after": 1, "text": "삽입 하나"},
            {"op": "insert_paragraph", "after": 1, "text": "삽입 둘"},
            {"op": "set_cell", "block": 3, "row": 1, "column": 1, "text": "200"},
            {"op": "insert_table_row", "block": 3, "after": 1, "cells": ["비용", "50"]},
            {"op": "replace_text", "find": "{{ customer_name }}", "replace": "박예시"},
        ])
        envelope = run_office(["doc", "apply", "fixture.docx", "ops.json"], self.directory)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(block_texts(self.directory, "fixture.docx"), [
            ("heading", "개요"),
            ("paragraph", "첫 문단 박예시 입니다."),
            ("paragraph", "삽입 하나"),
            ("paragraph", "삽입 둘"),
            ("table", [["항목", "값"], ["매출", "200"], ["비용", "50"]]),
            ("heading", "결론"),
        ])

    def test_one_bad_operation_leaves_the_file_untouched(self):
        original = (self.directory / "fixture.docx").read_bytes()
        write_json(self.directory / "ops.json", [
            {"op": "set_text", "block": 1, "text": "바뀜"},
            {"op": "set_cell", "block": 3, "row": 9, "column": 0, "text": "없음"},
        ])
        envelope = run_office(["doc", "apply", "fixture.docx", "ops.json"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["TARGET_NOT_FOUND"])
        self.assertEqual(envelope["issues"][0]["location"], "ops[1].row")
        self.assertEqual((self.directory / "fixture.docx").read_bytes(), original)

    def test_a_dry_run_reports_changes_and_writes_nothing(self):
        original = (self.directory / "fixture.docx").read_bytes()
        write_json(self.directory / "ops.json", [{"op": "insert_heading", "before": 0, "text": "머리", "level": 1}])
        envelope = run_office(["doc", "apply", "fixture.docx", "ops.json", "--dry-run"], self.directory)
        self.assertTrue(envelope["details"]["dryRun"])
        self.assertEqual(len(envelope["details"]["changes"]), 1)
        self.assertEqual((self.directory / "fixture.docx").read_bytes(), original)

    def test_a_misspelled_operation_or_field_suggests_the_close_name(self):
        write_json(self.directory / "ops.json", [{"op": "replace_txt", "find": "a", "replace": "b"}, {"op": "set_text", "block": 1, "texts": "바뀜"}])
        envelope = run_office(["doc", "apply", "fixture.docx", "ops.json"], self.directory)
        self.assertEqual([issue["suggestion"] for issue in envelope["issues"] if issue["code"] in ("INVALID_VALUE", "UNKNOWN_FIELD")], ['use "op": "replace_text"', "rename the field to 'text'"])

    def test_a_block_out_of_range_names_the_valid_range(self):
        write_json(self.directory / "ops.json", [{"op": "set_text", "block": 40, "text": "바뀜"}])
        envelope = run_office(["doc", "apply", "fixture.docx", "ops.json"], self.directory)
        self.assertEqual(envelope["issues"][0]["suggestion"], "use a block index from 0 to 4; doc read lists them")

    def test_deleting_a_block_another_operation_uses_is_refused(self):
        write_json(self.directory / "ops.json", [{"op": "set_text", "block": 2, "text": "바뀜"}, {"op": "delete_block", "block": 2}])
        envelope = run_office(["doc", "apply", "fixture.docx", "ops.json"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["OPERATION_NOT_APPLICABLE"])

    def test_parts_no_operation_touches_keep_their_bytes(self):
        write_json(self.directory / "ops.json", [{"op": "set_text", "block": 2, "text": "바뀜"}])
        run_office(["doc", "apply", "fixture.docx", "ops.json", "--output", "edited.docx"], self.directory)
        with zipfile.ZipFile(self.directory / "fixture.docx") as source, zipfile.ZipFile(self.directory / "edited.docx") as edited:
            changed = [name for name in source.namelist() if source.read(name) != edited.read(name)]
        self.assertEqual(changed, ["word/document.xml"])


class OperationPlannerTest(unittest.TestCase):
    def test_every_declared_operation_has_a_planner(self):
        completed = subprocess.run(
            [sys.executable, str(OFFICE_ENTRY), "python", "-c", "import sys; sys.path.insert(0, sys.argv[1]); from docx_operations import DOCX_OPERATIONS as o; print(sorted(o.planners) == sorted(r.name for r in o.shape.records))", str(SCRIPTS_PATH / "doc")],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(completed.stdout.strip(), "True")


if __name__ == "__main__":
    unittest.main()
