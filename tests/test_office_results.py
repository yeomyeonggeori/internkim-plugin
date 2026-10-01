import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


OFFICE_PATH = Path(__file__).resolve().parents[1] / "skills" / "office"
SCRIPTS_PATH = OFFICE_PATH / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"

sys.path.insert(0, str(SCRIPTS_PATH))
sys.path.insert(0, str(SCRIPTS_PATH / "deck"))

from office_commands import COMMANDS, FORMATS  # noqa: E402
from office_result import COMMAND_ISSUE_KINDS, IssueKind  # noqa: E402
from office_schema import CellValue, Field, ListOf, Number, Record, Text, Variant  # noqa: E402


def load_definitions(office_format):
    definitions_path = SCRIPTS_PATH / office_format.definitions_script
    sys.path.insert(0, str(definitions_path.parent))
    module_name = f"{office_format.name}_test_definitions"
    specification = importlib.util.spec_from_file_location(module_name, definitions_path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


def defined_issue_kinds(module):
    kinds = [value for value in vars(module).values() if isinstance(value, IssueKind)]
    kinds.extend(check.kind for check in getattr(module, "SLIDE_RENDER_CHECKS", ()) + getattr(module, "DESIGN_CHECKS", ()))
    return kinds


def run_office(arguments, working_directory):
    completed = subprocess.run(
        [sys.executable, str(OFFICE_ENTRY), *arguments],
        capture_output=True,
        text=True,
        cwd=working_directory,
        env={"HOME": str(working_directory), "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin"},
    )
    return completed, json.loads(completed.stdout)


def all_known_codes():
    codes = {kind.code for kind in COMMAND_ISSUE_KINDS}
    for office_format in FORMATS:
        codes.update(kind.code for kind in defined_issue_kinds(load_definitions(office_format)))
    return codes


class ResultEnvelopeTest(unittest.TestCase):
    def test_every_command_answers_a_bad_call_with_the_envelope(self):
        known_codes = all_known_codes()
        with tempfile.TemporaryDirectory() as working_directory:
            for command in COMMANDS:
                with self.subTest(command=command.name):
                    completed, envelope = run_office([command.format_name, command.verb], working_directory)
                    self.assertEqual(set(envelope), {"status", "summary", "outputPath", "issues"})
                    self.assertEqual(envelope["status"], "error")
                    self.assertEqual(completed.returncode, 1)
                    self.assertTrue(envelope["issues"])
                    for issue in envelope["issues"]:
                        self.assertEqual(set(issue), {"code", "severity", "message", "location", "suggestion"})
                        self.assertIn(issue["code"], known_codes)

    def test_an_unknown_command_is_an_issue(self):
        with tempfile.TemporaryDirectory() as working_directory:
            _, envelope = run_office(["doc", "shred"], working_directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["UNKNOWN_COMMAND"])

    def test_issue_codes_are_unique(self):
        kinds = set(COMMAND_ISSUE_KINDS)
        for office_format in FORMATS:
            kinds.update(defined_issue_kinds(load_definitions(office_format)))
        codes = [kind.code for kind in kinds]
        duplicates = sorted({code for code in codes if codes.count(code) > 1})
        self.assertEqual(duplicates, [])


class GuideTest(unittest.TestCase):
    def guide(self, format_name, *verbs):
        return subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", format_name, *verbs], capture_output=True, text=True, check=True).stdout

    def guide_with_requested_detail(self, office_format):
        requested = getattr(load_definitions(office_format), "GUIDE_INPUTS_ON_REQUEST", ())
        return "\n".join([self.guide(office_format.name), *(self.guide(*command.split()) for command in requested)])

    def test_the_guide_lists_every_code_its_format_defines(self):
        for office_format in FORMATS:
            with self.subTest(format=office_format.name):
                guide_text = self.guide(office_format.name)
                missing = [kind.code for kind in defined_issue_kinds(load_definitions(office_format)) if kind.code not in guide_text]
                self.assertEqual(missing, [])

    def test_the_guide_lists_every_field_the_validators_accept(self):
        for office_format in FORMATS:
            with self.subTest(format=office_format.name):
                guide_text = self.guide_with_requested_detail(office_format)
                for _, shape in load_definitions(office_format).GUIDE_INPUTS:
                    for structure in shape.structures():
                        records = structure.records if isinstance(structure, Variant) else (structure,)
                        for record in records:
                            for field in record.fields:
                                self.assertRegex(guide_text, rf"\n\s+{re.escape(field.name)}\s")


class SchemaTest(unittest.TestCase):
    SHAPE = Record("thing", "a test record", (
        Field("name", Text(non_empty=True), "a name", required=True),
        Field("size", Number(1, 4, integer=True), "a size"),
        Field("rows", ListOf(ListOf(CellValue())), "rows"),
    ))

    def codes_and_locations(self, value):
        return [(issue.kind.code, issue.location) for issue in self.SHAPE.problems(value, "spec")]

    def test_a_valid_value_has_no_problems(self):
        self.assertEqual(self.codes_and_locations({"name": "a", "size": 2, "rows": [["x", 1, None, True]]}), [])

    def test_each_problem_names_its_code_and_location(self):
        self.assertEqual(
            self.codes_and_locations({"extra": 1, "size": 7, "rows": [["x", {}]]}),
            [
                ("UNKNOWN_FIELD", "spec.extra"),
                ("MISSING_FIELD", "spec.name"),
                ("INVALID_VALUE", "spec.size"),
                ("WRONG_TYPE", "spec.rows[0][1]"),
            ],
        )

    def test_a_boolean_is_not_a_number(self):
        self.assertEqual(self.codes_and_locations({"name": "a", "size": True}), [("WRONG_TYPE", "spec.size")])


class PaperworkSkeletonTest(unittest.TestCase):
    def test_every_spec_skeleton_passes_the_renderer_schema(self):
        definitions = load_definitions(next(office_format for office_format in FORMATS if office_format.name == "paperwork"))
        problems = []
        for spec_path in sorted((OFFICE_PATH / "references" / "paperwork").rglob("*.md")):
            for block in re.findall(r"```json\n(.*?)```", spec_path.read_text(encoding="utf-8"), re.S):
                document = json.loads(re.sub(r"\{\s*\.\.\.[^}]*\.\.\.\s*\}", '{"name": "sample"}', block))
                shape = skeleton_shape(document, definitions)
                if shape is not None:
                    problems.extend(f"{spec_path.name}: {issue.message}" for issue in shape.problems(document, "document"))
        self.assertEqual(problems, [])


def skeleton_shape(document, definitions):
    if "blocks" in document:
        return definitions.CONTRACT_DOCUMENT
    if "title" in document:
        return definitions.PAPERWORK_DOCUMENT
    return None


class DeckReviewResultTest(unittest.TestCase):
    def test_the_review_reports_every_warning_it_writes_as_an_issue(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            deck_path = Path(temporary_directory)
            (deck_path / "slides.html").write_text(
                "<section><h2>개요</h2><ul><li>하나</li><li>둘</li></ul></section>"
                "<section data-slide-role=\"closing\"><h2>승인을 요청드립니다</h2><p>본문</p></section>",
                encoding="utf-8",
            )
            review_path = deck_path / "review"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS_PATH / "deck" / "render_review.py"), str(deck_path / "slides.html"), "deck", str(review_path)],
                capture_output=True,
                text=True,
                env={"PYTHONPATH": str(SCRIPTS_PATH)},
            )
            envelope = json.loads(completed.stdout)
            report = json.loads((review_path / "slide-review.json").read_text(encoding="utf-8"))
        written_warnings = {warning for slide in report["slides"] for warning in slide["warnings"]}
        self.assertEqual({issue["message"] for issue in envelope["issues"]}, written_warnings)
        self.assertIn(("MISSING_SLIDE_ROLE", "slide 1"), {(issue["code"], issue["location"]) for issue in envelope["issues"]})
        self.assertIn(("WEAK_VISUAL_IDENTITY", "deck"), {(issue["code"], issue["location"]) for issue in envelope["issues"]})
        self.assertEqual(envelope["details"]["visualQualityScore"], report["visualQualityScore"])


if __name__ == "__main__":
    unittest.main()
