import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from free_deck_fixture import write_free_deck

from doc_fixture import OFFICE_ENTRY, run_office, write_json
from render_fixture import can_render
from task_context_fixture import environment_with_context, register_record, write_context_at

from core.source_snapshot import SOURCE_SUFFIX


def source_beside(path):
    snapshot = Path(str(path) + SOURCE_SUFFIX)
    return json.loads(snapshot.read_text(encoding="utf-8")) if snapshot.is_file() else None


class ProvenanceTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def test_create_leaves_a_snapshot_beside_the_document_it_writes(self):
        Path(self.directory, "note.md").write_text("# 메모\n\n본문\n", encoding="utf-8")
        result = run_office(["create", "note.docx", "note.md"], self.directory)
        self.assertNotEqual(result["status"], "error", result)
        self.assertEqual(source_beside(self.directory / "note.docx"), {"command": "office create", "arguments": ["note.docx", "note.md"]})

    def test_convert_leaves_a_snapshot_beside_the_file_it_writes(self):
        Path(self.directory, "note.md").write_text("# 메모\n\n본문\n", encoding="utf-8")
        run_office(["create", "note.docx", "note.md"], self.directory)
        result = run_office(["convert", "note.docx", "note.pdf"], self.directory)
        self.assertNotEqual(result["status"], "error", result)
        self.assertEqual(source_beside(self.directory / "note.pdf")["command"], "office convert")

    def test_reading_checking_and_rendering_leave_no_snapshot(self):
        Path(self.directory, "note.md").write_text("# 메모\n\n본문\n", encoding="utf-8")
        run_office(["create", "note.docx", "note.md"], self.directory)
        Path(str(self.directory / "note.docx") + SOURCE_SUFFIX).unlink()
        for verb in ("read", "check"):
            run_office([verb, "note.docx"], self.directory)
        self.assertIsNone(source_beside(self.directory / "note.docx"))

    def test_apply_to_a_new_path_carries_the_snapshot_of_the_file_it_edits(self):
        Path(self.directory, "note.md").write_text("# 메모\n\n본문\n", encoding="utf-8")
        run_office(["create", "note.docx", "note.md"], self.directory)
        write_json(self.directory / "ops.json", [{"op": "replace_text", "find": "본문", "replace": "고친 본문"}])
        result = run_office(["apply", "note.docx", "ops.json", "--output", "edited.docx"], self.directory)
        self.assertNotEqual(result["status"], "error", result)
        self.assertEqual(source_beside(self.directory / "edited.docx"), source_beside(self.directory / "note.docx"))

    @unittest.skipUnless(can_render(), "needs the deck renderer")
    def test_a_deck_built_as_pptx_leaves_a_snapshot_beside_the_pdf_it_also_writes(self):
        write_free_deck(self.directory, ["<h2>배송이 빨라집니다</h2><p>주문 후 하루 안에 도착합니다.</p>"])
        result = run_office(["create", "build/deck.pptx", "."], self.directory)
        self.assertNotEqual(result["status"], "error", result)
        for name in ("deck.pptx", "deck.pdf"):
            self.assertEqual(source_beside(self.directory / "build" / name)["command"], "office create", name)

    def test_a_schema_merge_records_its_blanks_in_the_snapshot(self):
        values = {"meetingName": "Review", "startsAt": "2026-10-04 10:00", "endsAt": "2026-10-04 11:00", "place": None, "attendees": ["박예시"], "agenda": ["예산"], "decisions": ["유지"], "actions": []}
        write_json(self.directory / "values.json", values)
        result = run_office(["merge", "kr/meeting-minutes", "values.json", "minutes.pdf"], self.directory)
        self.assertEqual(source_beside(self.directory / "minutes.pdf")["blanks"], result["details"]["blanks"])
        self.assertIn("place", [blank["field"] for blank in result["details"]["blanks"]])


READER = ("from schemas.known_values import load_runtime_context; context = load_runtime_context(); import json; "
          "print(json.dumps({'requester': [context.requester_name, context.requester_email], 'today': str(context.today), 'company': context.company('ko').get('name'), "
          "'seal': context.company('ko').get('stampPath'), 'number': context.document_number(), 'attachments': [attachment['name'] for attachment in context.attachments]}, ensure_ascii=False))")


class TaskContextTest(unittest.TestCase):
    def sample_facts(self, directory):
        profile = Path(directory, "company-profile.json")
        write_json(profile, {"name": "샘플테크 주식회사", "sealImage": "seal.png"})
        return {
            "requester": {"name": "이샘플", "email": "sample@example.com"},
            "today": "2026-10-04",
            "company": {"ko": str(profile)},
            "registeredDocuments": [{"documentNumber": "SAMPLE-20261004-001"}],
            "attachments": [{"name": "budget.csv", "path": str(Path(directory, "budget.csv"))}],
        }

    def read_known_values(self, directory, facts):
        context_path = write_context_at(Path(directory, "task", "task-context.json"), facts)
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", READER], capture_output=True, text=True, env=environment_with_context(context_path), check=True)
        return json.loads(completed.stdout)

    def test_the_office_reads_the_known_values_from_the_task_context(self):
        with tempfile.TemporaryDirectory() as directory:
            read = self.read_known_values(directory, self.sample_facts(directory))
        self.assertEqual(read["requester"], ["이샘플", "sample@example.com"])
        self.assertEqual(read["today"], "2026-10-04")
        self.assertEqual(read["company"], "샘플테크 주식회사")
        self.assertEqual(read["seal"], str(Path(directory, "seal.png")))
        self.assertEqual(read["number"], "SAMPLE-20261004-001")
        self.assertEqual(read["attachments"], ["budget.csv"])

    def test_the_document_number_is_the_last_one_a_registration_answered(self):
        with tempfile.TemporaryDirectory() as directory:
            facts = self.sample_facts(directory) | {"registeredDocuments": [{"documentNumber": "QT-1"}, {"documentNumber": "QT-2"}], "records": [register_record(None)]}
            read = self.read_known_values(directory, facts)
        self.assertEqual(read["number"], "QT-2")


if __name__ == "__main__":
    unittest.main()
