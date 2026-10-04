import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from free_deck_fixture import write_free_deck

from doc_fixture import OFFICE_ENTRY, run_office, write_json
from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
HOST_CONTRACT = json.loads((SCRIPTS_PATH.parent / "assets" / "host-contract.json").read_text(encoding="utf-8"))


def source_beside(path):
    snapshot = Path(str(path) + HOST_CONTRACT["sourceSuffix"])
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
        Path(str(self.directory / "note.docx") + HOST_CONTRACT["sourceSuffix"]).unlink()
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
        result = run_office(["create", "build/deck.pptx", "slides.html"], self.directory)
        self.assertNotEqual(result["status"], "error", result)
        for name in ("deck.pptx", "deck.pdf"):
            self.assertEqual(source_beside(self.directory / "build" / name)["command"], "office create", name)

    def test_a_schema_merge_records_its_blanks_in_the_snapshot(self):
        values = {"meetingName": "Review", "startsAt": "2026-10-04 10:00", "endsAt": "2026-10-04 11:00", "place": None, "attendees": ["박예시"], "agenda": ["예산"], "decisions": ["유지"], "actions": []}
        write_json(self.directory / "values.json", values)
        result = run_office(["merge", "kr/meeting-minutes", "values.json", "minutes.pdf"], self.directory)
        self.assertEqual(source_beside(self.directory / "minutes.pdf")["blanks"], result["details"]["blanks"])
        self.assertIn("place", [blank["field"] for blank in result["details"]["blanks"]])


class HostContractTest(unittest.TestCase):
    def sample_context(self, directory):
        profile = Path(directory, "company-profile.json")
        write_json(profile, {"name": "샘플테크 주식회사", "sealImage": "seal.png"})
        return {
            "requester": {"name": "이샘플", "email": "sample@example.com"},
            "today": "2026-10-04",
            "company": {"ko": str(profile)},
            "registeredDocuments": [{"documentNumber": "SAMPLE-20261004-001"}],
            "attachments": [{"name": "budget.csv", "path": str(Path(directory, "budget.csv"))}],
            "reviewsDeckRenders": True,
            "preparesDecks": True,
            "deckDesign": None,
            "images": [],
        }

    def test_the_sample_context_holds_exactly_the_fields_the_contract_names(self):
        schema = HOST_CONTRACT["runtimeContext"]
        with tempfile.TemporaryDirectory() as directory:
            context = self.sample_context(directory)
        self.assertEqual(set(context), set(schema["properties"]))
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        for name in ("requester", "registeredDocuments", "attachments"):
            properties = schema["properties"][name].get("properties") or schema["properties"][name]["items"]["properties"]
            sample = context[name] if isinstance(context[name], dict) else context[name][0]
            self.assertEqual(set(sample), set(properties), name)

    def test_the_office_reader_takes_every_field_of_the_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            context_path = Path(directory, "context.json")
            write_json(context_path, self.sample_context(directory))
            reader = "from schemas.known_values import load_runtime_context; context = load_runtime_context(); import json; print(json.dumps({'requester': [context.requester_name, context.requester_email], 'today': str(context.today), 'company': context.company('ko').get('name'), 'seal': context.company('ko').get('stampPath'), 'number': context.document_number(), 'attachments': [attachment['name'] for attachment in context.attachments], 'reviewsDeckRenders': context.reviews_deck_renders}, ensure_ascii=False))"
            environment = dict(os.environ, OFFICE_RUNTIME_CONTEXT=str(context_path))
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", reader], capture_output=True, text=True, env=environment, check=True)
        read = json.loads(completed.stdout)
        self.assertEqual(read["requester"], ["이샘플", "sample@example.com"])
        self.assertEqual(read["today"], "2026-10-04")
        self.assertEqual(read["company"], "샘플테크 주식회사")
        self.assertEqual(read["seal"], str(Path(directory, "seal.png")))
        self.assertEqual(read["number"], "SAMPLE-20261004-001")
        self.assertEqual(read["attachments"], ["budget.csv"])
        self.assertIs(read["reviewsDeckRenders"], True)

    def test_a_context_from_a_host_that_names_no_render_review_reads_as_no_review(self):
        with tempfile.TemporaryDirectory() as directory:
            context_path = Path(directory, "context.json")
            older = {name: value for name, value in self.sample_context(directory).items() if name != "reviewsDeckRenders"}
            write_json(context_path, older)
            environment = dict(os.environ, OFFICE_RUNTIME_CONTEXT=str(context_path))
            reader = "from schemas.known_values import load_runtime_context; print(load_runtime_context().reviews_deck_renders)"
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", reader], capture_output=True, text=True, env=environment, check=True)
        self.assertEqual(completed.stdout.strip(), "False")

    def test_the_variable_the_reader_looks_for_is_the_contract_variable(self):
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", "from schemas.known_values import RUNTIME_CONTEXT_VARIABLE; print(RUNTIME_CONTEXT_VARIABLE)"], capture_output=True, text=True, check=True)
        self.assertEqual(completed.stdout.strip(), HOST_CONTRACT["runtimeContextVariable"])


if __name__ == "__main__":
    unittest.main()
