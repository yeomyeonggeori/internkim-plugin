import errno
import importlib
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

from core.office_commands import COMMANDS, FORMATS  # noqa: E402
from office_guide import guide_text  # noqa: E402
from core.office_result import COMMAND_ISSUE_KINDS, IssueKind, command_result  # noqa: E402
from core.office_schema import CellValue, Field, ListOf, Number, Record, Text, Variant  # noqa: E402


def load_definitions(office_format):
    return importlib.import_module(office_format.definitions_module)


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
                        self.assertEqual(set(issue), {"code", "severity", "message", "location", "suggestion", "fix"})
                        self.assertIsInstance(issue["suggestion"], str)
                        self.assertEqual(issue["fix"], [])
                        self.assertIn(issue["code"], known_codes)

    def test_an_issue_carries_its_suggestion_as_text_and_its_operations_in_fix(self):
        kind = IssueKind("SAMPLE", "warning", "a sample", "do the sample thing")
        self.assertEqual(kind.issue("found", "block 2", fix=[{"op": "delete_block", "block": 2}]).to_json(), {
            "code": "SAMPLE", "severity": "warning", "message": "found", "location": "block 2",
            "suggestion": "do the sample thing", "fix": [{"op": "delete_block", "block": 2}],
        })
        self.assertEqual(kind.issue("found").to_json()["fix"], [])
        with self.assertRaises(TypeError):
            kind.issue("found", suggestion={"op": "delete_block"})
        with self.assertRaises(TypeError):
            kind.issue("found", fix=[{"block": 2}])

    def test_a_kind_whose_suggestion_applies_fix_refuses_an_issue_without_fix(self):
        kind = IssueKind("SAMPLE", "warning", "a sample", "apply the operation in fix", suggestion_applies_fix=True)
        self.assertEqual(kind.issue("found", fix=[{"op": "recalculate"}]).suggestion, "apply the operation in fix")
        self.assertEqual(kind.issue("found", suggestion="leave it as it is").fix, ())
        with self.assertRaises(TypeError):
            kind.issue("found")

    def test_an_unknown_command_is_an_issue(self):
        with tempfile.TemporaryDirectory() as working_directory:
            _, envelope = run_office(["doc", "shred"], working_directory)
            _, retired = run_office(["deck", "validate", "slides.html"], working_directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["UNKNOWN_COMMAND"])
        self.assertIn("deck check", retired["issues"][0]["suggestion"])

    def test_a_mistyped_format_or_verb_names_the_command_it_meant(self):
        with tempfile.TemporaryDirectory() as working_directory:
            _, format_typo = run_office(["dek", "build"], working_directory)
            _, verb_typo = run_office(["deck", "biuld"], working_directory)
        for envelope in (format_typo, verb_typo):
            self.assertEqual(envelope["status"], "error")
            self.assertEqual(envelope["issues"][0]["code"], "UNKNOWN_COMMAND")
            self.assertIn("office deck build", envelope["issues"][0]["suggestion"])

    def test_a_mistyped_flag_names_the_flag_it_meant(self):
        with tempfile.TemporaryDirectory() as working_directory:
            completed, envelope = run_office(["deck", "build", "--slide-cont", "3"], working_directory)
        self.assertEqual(completed.returncode, 1)
        issue = envelope["issues"][0]
        self.assertEqual((issue["code"], issue["location"]), ("INVALID_ARGUMENTS", "--slide-cont"))
        self.assertIn("--slide-count", issue["suggestion"])

    def test_issue_codes_are_unique(self):
        kinds = set(COMMAND_ISSUE_KINDS)
        for office_format in FORMATS:
            kinds.update(defined_issue_kinds(load_definitions(office_format)))
        codes = [kind.code for kind in kinds]
        duplicates = sorted({code for code in codes if codes.count(code) > 1})
        self.assertEqual(duplicates, [])


class OutputPathTest(unittest.TestCase):
    def path_issues(self, arguments, working_directory):
        completed, envelope = run_office(arguments, working_directory)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        return [(issue["code"], issue["location"]) for issue in envelope["issues"]]

    def test_an_output_path_the_disk_refuses_is_one_envelope_naming_the_path(self):
        with tempfile.TemporaryDirectory() as directory:
            working_directory = Path(directory)
            (working_directory / "folder.xlsx").mkdir()
            (working_directory / "plain").write_text("not a folder", encoding="utf-8")
            (working_directory / "notes.md").write_text("# 제목\n\n본문\n", encoding="utf-8")
            long_name = "n" * 300
            cases = {
                ("sheet", "create", "folder.xlsx", "--row", "a,b"): ("PATH_UNUSABLE", "folder.xlsx"),
                ("sheet", "create", "plain/book.xlsx", "--row", "a,b"): ("PATH_UNUSABLE", "plain"),
                ("pdf", "create", f"{long_name}.pdf", "--title", "제목"): ("PATH_UNUSABLE", f"{long_name}.pdf"),
                ("doc", "export", "notes.md", "--output", "plain/notes.docx"): ("PATH_UNUSABLE", "plain"),
                ("convert", "notes.md", f"{long_name}.docx"): ("PATH_UNUSABLE", f"{long_name}.docx"),
            }
            for arguments, expected in cases.items():
                with self.subTest(arguments=arguments[:3]):
                    self.assertEqual(self.path_issues(list(arguments), working_directory), [expected])

    def test_an_output_whose_extension_names_another_format_is_refused_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            working_directory = Path(directory)
            cases = {
                ("sheet", "create", "표.csv", "--row", "a,b"): "표.xlsx",
                ("pdf", "create", "보고서.docx", "--title", "제목"): "보고서.pdf",
                ("doc", "create", "보고서.pdf", "--title", "제목", "--paragraph", "본문"): "보고서.docx",
                ("deck", "image", "harbor cranes", "images/harbor.gif"): "images/harbor.jpg",
            }
            for arguments, meant in cases.items():
                with self.subTest(arguments=arguments[:3]):
                    completed, envelope = run_office(list(arguments), working_directory)
                    self.assertEqual([issue["code"] for issue in envelope["issues"]], ["WRONG_OUTPUT_FORMAT"])
                    self.assertIn(meant, envelope["issues"][0]["suggestion"])
            self.assertEqual(sorted(path.name for path in working_directory.iterdir()), [])

    def test_apply_and_merge_write_the_kind_of_file_they_read(self):
        with tempfile.TemporaryDirectory() as directory:
            working_directory = Path(directory)
            self.assertEqual(run_office(["sheet", "create", "book.xlsx", "--row", "a,b"], working_directory)[1]["status"], "ok")
            (working_directory / "ops.json").write_text('[{"op": "set_cell", "cell": "A2", "value": 1}]', encoding="utf-8")
            (working_directory / "values.json").write_text("{}", encoding="utf-8")
            for arguments in (["sheet", "apply", "book.xlsx", "ops.json", "--output", "book.csv"], ["sheet", "merge", "book.xlsx", "values.json", "filled.pdf"]):
                with self.subTest(command=arguments[:2]):
                    _, envelope = run_office(arguments, working_directory)
                    self.assertEqual([issue["code"] for issue in envelope["issues"]], ["WRONG_OUTPUT_FORMAT"])
            self.assertEqual(sorted(path.name for path in working_directory.iterdir()), ["book.xlsx", "ops.json", "values.json"])

    def test_a_read_only_disk_is_named_rather_than_raised(self):
        def write_on_read_only_disk():
            raise OSError(errno.EROFS, "Read-only file system", "/Volumes/archive/report.docx")

        result = command_result(write_on_read_only_disk)
        self.assertEqual([(issue.kind.code, issue.location) for issue in result.issues], [("PATH_UNUSABLE", "/Volumes/archive/report.docx")])
        self.assertIn("read-only", result.issues[0].message)


class GuideTest(unittest.TestCase):
    def guide(self, format_name, *verbs):
        return subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", format_name, *verbs], capture_output=True, text=True, check=True).stdout

    def guide_with_every_verb(self, office_format):
        verbs = [command.verb for command in COMMANDS if command.format_name == office_format.name and command.verb]
        operation_guides = [
            guide_text(office_format, label.split()[1], record.name)
            for label, shape in load_definitions(office_format).GUIDE_INPUTS
            for structure in shape.structures() if isinstance(structure, Variant)
            for record in structure.records
        ]
        return "\n".join([self.guide(office_format.name), *(self.guide(office_format.name, verb) for verb in verbs), *operation_guides])

    def test_the_guide_lists_every_code_its_format_defines(self):
        for office_format in FORMATS:
            with self.subTest(format=office_format.name):
                guide_text = self.guide(office_format.name)
                missing = [kind.code for kind in defined_issue_kinds(load_definitions(office_format)) if kind.code not in guide_text]
                self.assertEqual(missing, [])

    def test_the_guide_lists_every_field_the_validators_accept(self):
        for office_format in FORMATS:
            with self.subTest(format=office_format.name):
                guide_text = self.guide_with_every_verb(office_format)
                for _, shape in load_definitions(office_format).GUIDE_INPUTS:
                    for structure in shape.structures():
                        records = structure.records if isinstance(structure, Variant) else (structure,)
                        for record in records:
                            for field in record.fields:
                                self.assertRegex(guide_text, rf"\n\s+{re.escape(field.name)}\s")


    def test_one_operation_prints_only_its_fields(self):
        text = self.guide("sheet", "apply", "add_chart")
        self.assertIn('op "add_chart"', text)
        self.assertIn("\n  range (", text)
        self.assertNotIn("set_cell", text)

    def test_an_unknown_topic_answers_with_the_envelope_and_the_close_name(self):
        for arguments, suggestion in ((["sheat"], "office guide sheet"), (["sheet", "aply"], "office guide sheet apply"), (["sheet", "apply", "add_chrt"], "office guide sheet apply add_chart")):
            with self.subTest(arguments=arguments):
                completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", *arguments], capture_output=True, text=True)
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(json.loads(completed.stdout)["issues"][0]["suggestion"], suggestion)

    def test_the_index_names_operations_without_their_fields(self):
        index = self.guide("sheet")
        self.assertIn("add_chart", index)
        self.assertNotIn("secondaryAxis", index)

    def test_a_first_read_stays_short_and_an_operation_gives_its_fields(self):
        index, apply_guide = self.guide("sheet"), self.guide("sheet", "apply")
        self.assertLess(len(index), 6000)
        self.assertLess(len(apply_guide), 8000)
        self.assertIn('op "add_pivot_table": summarize', apply_guide)
        self.assertNotIn("secondaryAxis", apply_guide)
        self.assertIn("office guide sheet apply <op> lists one op's fields", apply_guide)
        self.assertIn("secondaryAxis (true or false)", self.guide("sheet", "apply", "add_chart"))
        self.assertIn("CIRCULAR_REFERENCE (error)", apply_guide)


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
    def test_the_review_reports_every_warning_it_writes_as_an_issue_without_legacy_codes(self):
        from deck.render_review import review_deck

        with tempfile.TemporaryDirectory() as temporary_directory:
            deck_path = Path(temporary_directory)
            (deck_path / "slides.html").write_text(
                "<section><h2>개요</h2><ul><li>하나</li><li>둘</li></ul></section>"
                "<section><h2>승인을 요청드립니다</h2><p>본문</p></section>",
                encoding="utf-8",
            )
            review_path = deck_path / "review"
            result = review_deck(deck_path / "slides.html", "deck", review_path)
            report = json.loads((review_path / "slide-review.json").read_text(encoding="utf-8"))
        codes = {issue.kind.code for issue in result.issues}
        self.assertEqual({issue.message for issue in result.issues}, {warning for slide in report["slides"] for warning in slide["warnings"]})
        self.assertIn("MISSING_SPEAKER_NOTES", codes)
        self.assertEqual(codes & {"MISSING_SLIDE_ROLE", "WEAK_VISUAL_IDENTITY", "RAW_TABLE", "BARE_LIST", "MISSING_REQUIRED_TEXT"}, set())
        self.assertFalse(any(re.match(r"^[a-z]+[A-Z]\w*: ", issue.message) for issue in result.issues))
        self.assertNotIn("visualQualityScore", report)


if __name__ == "__main__":
    unittest.main()
