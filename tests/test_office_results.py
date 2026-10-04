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

from core.office_commands import VERBS, definitions_modules  # noqa: E402
from core.office_result import COMMAND_ISSUE_KINDS, IssueKind, command_result  # noqa: E402
from core.office_schema import CellValue, Field, ListOf, Number, Record, Text, Variant  # noqa: E402
from render_fixture import bare_environment, can_render  # noqa: E402


def every_definitions():
    return [importlib.import_module(name) for name in definitions_modules()]


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
        env=bare_environment(working_directory),
    )
    return completed, json.loads(completed.stdout)


def all_known_codes():
    codes = {kind.code for kind in COMMAND_ISSUE_KINDS}
    for definitions in every_definitions():
        codes.update(kind.code for kind in defined_issue_kinds(definitions))
    return codes


class ResultEnvelopeTest(unittest.TestCase):
    def test_every_command_answers_a_bad_call_with_the_envelope(self):
        known_codes = all_known_codes()
        with tempfile.TemporaryDirectory() as working_directory:
            for verb in VERBS:
                with self.subTest(verb=verb.name):
                    completed, envelope = run_office([verb.name], working_directory)
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
            _, envelope = run_office(["shred", "book.xlsx"], working_directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["UNKNOWN_COMMAND"])

    def test_a_retired_command_names_the_command_that_replaced_it(self):
        cases = {
            ("deck", "build", "--format", "pptx", "--name", "review"): "office create build/review.pptx slides.html",
            ("sheet", "validate", "book.xlsx"): "office check book.xlsx",
            ("paperwork", "fill", "nda", "values.json", "nda.docx"): "office merge kr/nda values.json nda.docx",
            ("doc", "export", "report.md", "--output", "report.pdf"): "office create report.pdf report.md",
            ("deck", "restore", "deck.html", "slides.html"): "office convert deck.html slides.html",
        }
        with tempfile.TemporaryDirectory() as working_directory:
            for arguments, replacement in cases.items():
                with self.subTest(arguments=arguments[:2]):
                    completed, envelope = run_office(list(arguments), working_directory)
                    self.assertEqual(completed.returncode, 1)
                    self.assertEqual([issue["code"] for issue in envelope["issues"]], ["UNKNOWN_COMMAND"])
                    self.assertEqual(envelope["issues"][0]["suggestion"], replacement)

    def test_a_mistyped_format_or_verb_names_the_command_it_meant(self):
        with tempfile.TemporaryDirectory() as working_directory:
            _, envelope = run_office(["crete", "deck.pdf", "slides.html"], working_directory)
        self.assertEqual(envelope["issues"][0]["code"], "UNKNOWN_COMMAND")
        self.assertIn("office create", envelope["issues"][0]["suggestion"])

    def test_a_mistyped_flag_names_the_flag_it_meant(self):
        with tempfile.TemporaryDirectory() as working_directory:
            completed, envelope = run_office(["create", "deck.pdf", "slides.html", "--slide-cont", "3"], working_directory)
        self.assertEqual(completed.returncode, 1)
        issue = envelope["issues"][0]
        self.assertEqual((issue["code"], issue["location"]), ("INVALID_ARGUMENTS", "--slide-cont"))
        self.assertIn("--slide-count", issue["suggestion"])

    def test_issue_codes_are_unique(self):
        kinds = set(COMMAND_ISSUE_KINDS)
        for definitions in every_definitions():
            kinds.update(defined_issue_kinds(definitions))
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
            (working_directory / "notes.html").write_text("<h1>제목</h1>", encoding="utf-8")
            (working_directory / "book.workbook.json").write_text('{"kind": "workbook", "tables": [{"name": "Data", "columns": [{"name": "a"}, {"name": "b"}], "rows": [["x", "y"]]}]}', encoding="utf-8")
            long_name = "n" * 300
            cases = {
                ("create", "folder.xlsx", "book.workbook.json"): ("PATH_UNUSABLE", "folder.xlsx"),
                ("create", "plain/book.xlsx", "book.workbook.json"): ("PATH_UNUSABLE", "plain"),
                ("create", "plain/notes.docx", "notes.md"): ("PATH_UNUSABLE", "plain"),
                ("convert", "notes.html", f"{long_name}.docx"): ("PATH_UNUSABLE", f"{long_name}.docx"),
            }
            for arguments, expected in cases.items():
                with self.subTest(arguments=arguments[:3]):
                    self.assertEqual(self.path_issues(list(arguments), working_directory), [expected])

    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_a_drawn_pdf_whose_name_the_disk_refuses_is_one_envelope_naming_it(self):
        with tempfile.TemporaryDirectory() as directory:
            long_name = f"{'n' * 300}.pdf"
            (Path(directory) / "spec.json").write_text('{"title": "제목"}', encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", long_name, "spec.json"], capture_output=True, text=True, cwd=directory)
            envelope = json.loads(completed.stdout)
            self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("PATH_UNUSABLE", long_name)])
            self.assertEqual([path.name for path in Path(directory).iterdir()], ["spec.json"])

    def test_an_output_whose_extension_names_another_format_is_refused_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            working_directory = Path(directory)
            (working_directory / "rows.csv").write_text("a,b\n", encoding="utf-8")
            (working_directory / "notes.md").write_text("# 제목\n", encoding="utf-8")
            cases = {
                ("create", "표.docx", "rows.csv"): "표.xlsx",
                ("create", "보고서.pptx", "notes.md"): "보고서.docx",
                ("image", "harbor cranes", "images/harbor.gif"): "images/harbor.jpg",
            }
            for arguments, meant in cases.items():
                with self.subTest(arguments=arguments[:3]):
                    completed, envelope = run_office(list(arguments), working_directory)
                    self.assertEqual([issue["code"] for issue in envelope["issues"]], ["WRONG_OUTPUT_FORMAT"])
                    self.assertIn(meant, envelope["issues"][0]["suggestion"])
            self.assertEqual(sorted(path.name for path in working_directory.iterdir()), ["notes.md", "rows.csv"])

    def test_apply_and_merge_write_the_kind_of_file_they_read(self):
        with tempfile.TemporaryDirectory() as directory:
            working_directory = Path(directory)
            (working_directory / "book.workbook.json").write_text('{"kind": "workbook", "tables": [{"name": "Data", "columns": [{"name": "a"}, {"name": "b"}], "rows": [["x", "y"]]}]}', encoding="utf-8")
            self.assertEqual(run_office(["create", "book.xlsx", "book.workbook.json"], working_directory)[1]["status"], "ok")
            (working_directory / "ops.json").write_text('[{"op": "set_cell", "cell": "D5", "value": 1}]', encoding="utf-8")
            (working_directory / "values.json").write_text("{}", encoding="utf-8")
            for arguments in (["apply", "book.xlsx", "ops.json", "--output", "book.csv"], ["merge", "book.xlsx", "values.json", "filled.pdf"]):
                with self.subTest(command=arguments[:2]):
                    _, envelope = run_office(arguments, working_directory)
                    self.assertEqual([issue["code"] for issue in envelope["issues"]], ["WRONG_OUTPUT_FORMAT"])
            self.assertEqual(sorted(path.name for path in working_directory.iterdir()), ["book.workbook.json", "book.xlsx", "book.xlsx.source.json", "ops.json", "values.json"])

    def test_an_empty_image_query_is_refused_before_any_search(self):
        with tempfile.TemporaryDirectory() as directory:
            _, envelope = run_office(["image", " ", "images/photo.jpg"], Path(directory))
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["INVALID_ARGUMENTS"])

    def test_an_apply_without_a_path_never_picks_a_file_by_itself(self):
        with tempfile.TemporaryDirectory() as directory:
            working_directory = Path(directory)
            (working_directory / "documents").mkdir()
            (working_directory / "book.workbook.json").write_text('{"kind": "workbook", "tables": [{"name": "Data", "columns": [{"name": "a"}, {"name": "b"}], "rows": [["x", "y"]]}]}', encoding="utf-8")
            (working_directory / "ops.json").write_text('[{"op": "append_rows", "rows": [[1, 2]]}]', encoding="utf-8")
            self.assertEqual(run_office(["create", "documents/book.xlsx", "book.workbook.json"], working_directory)[1]["status"], "ok")
            original = (working_directory / "documents" / "book.xlsx").read_bytes()
            for arguments in (["apply", "ops.json"], ["apply"], ["apply", "documents"]):
                with self.subTest(command=arguments):
                    _, envelope = run_office(arguments, working_directory)
                    self.assertEqual([issue["code"] for issue in envelope["issues"]], ["INVALID_ARGUMENTS"])
            self.assertEqual((working_directory / "documents" / "book.xlsx").read_bytes(), original)

    def test_a_read_only_disk_is_named_rather_than_raised(self):
        def write_on_read_only_disk():
            raise OSError(errno.EROFS, "Read-only file system", "/Volumes/archive/report.docx")

        result = command_result(write_on_read_only_disk)
        self.assertEqual([(issue.kind.code, issue.location) for issue in result.issues], [("PATH_UNUSABLE", "/Volumes/archive/report.docx")])
        self.assertIn("read-only", result.issues[0].message)


class GuideTest(unittest.TestCase):
    def guide(self, *topics):
        return subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", *topics], capture_output=True, text=True, check=True).stdout

    def guided_inputs(self):
        for definitions in every_definitions():
            for verb, kind, _, shape in getattr(definitions, "GUIDE_INPUTS", ()):
                yield verb, kind, shape

    def test_the_guide_lists_every_code_a_route_defines(self):
        for definitions in every_definitions():
            for verb, kind, kinds in getattr(definitions, "GUIDE_ISSUES", ()):
                with self.subTest(route=f"{verb} {kind}"):
                    text = self.guide(verb) if kind == "*" else self.guide(verb, kind)
                    self.assertEqual([issue.code for issue in kinds if issue.code not in text], [])

    def test_every_defined_code_is_listed_by_some_route(self):
        listed = {issue.code for definitions in every_definitions() for _, _, kinds in getattr(definitions, "GUIDE_ISSUES", ()) for issue in kinds}
        defined = {kind.code for definitions in every_definitions() for kind in defined_issue_kinds(definitions)}
        every_command = {kind.code for kind in COMMAND_ISSUE_KINDS}
        self.assertTrue(every_command <= set(re.findall(r"[A-Z_]{4,}", self.guide())))
        self.assertEqual(sorted(defined - listed - every_command), [])

    def test_the_guide_lists_every_field_the_validators_accept(self):
        for verb, kind, shape in self.guided_inputs():
            with self.subTest(route=f"{verb} {kind}"):
                texts = [self.guide(verb, kind)]
                for structure in shape.structures():
                    if isinstance(structure, Variant):
                        texts.extend(self.guide(verb, kind, record.name) for record in structure.records)
                guide_text = "\n".join(texts)
                for structure in shape.structures():
                    records = structure.records if isinstance(structure, Variant) else (structure,)
                    for record in records:
                        for field in record.fields:
                            self.assertRegex(guide_text, rf"\n\s+{re.escape(field.name)}\s")

    def test_one_operation_prints_only_its_fields(self):
        text = self.guide("apply", "xlsx", "add_chart")
        self.assertIn('op "add_chart"', text)
        self.assertIn("\n  range (", text)
        self.assertNotIn("set_cell", text)

    def test_an_unknown_topic_answers_with_the_envelope_and_the_close_name(self):
        cases = (
            (["xlsz"], "office guide xlsx"),
            (["aply"], "office guide apply"),
            (["apply", "xlx"], "office guide apply xlsx"),
            (["apply", "xlsx", "add_chrt"], "office guide apply xlsx add_chart"),
        )
        for arguments, suggestion in cases:
            with self.subTest(arguments=arguments):
                completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", *arguments], capture_output=True, text=True)
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(json.loads(completed.stdout)["issues"][0]["suggestion"], suggestion)

    def test_a_format_named_in_everyday_words_names_the_kind_it_means(self):
        cases = (
            (["sheet"], "xlsx", "office guide xlsx"),
            (["apply", "sheet"], "xlsx", "office guide apply xlsx"),
            (["apply", "spreadsheet"], "xlsx", "office guide apply xlsx"),
            (["check", "excel"], "xlsx", "office guide check xlsx"),
            (["document"], "docx", "office guide docx"),
            (["apply", "word"], "docx", "office guide apply docx"),
            (["deck"], "slides", "office guide slides"),
            (["create", "presentation"], "slides", "office guide create slides"),
            (["apply", "deck"], "pptx", "office guide apply pptx"),
            (["render", "slides"], "pptx", "office guide render pptx"),
            (["read", "powerpoint"], "pptx", "office guide read pptx"),
        )
        for arguments, kind, suggestion in cases:
            with self.subTest(arguments=arguments):
                completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", *arguments], capture_output=True, text=True)
                issue = json.loads(completed.stdout)["issues"][0]
                self.assertEqual(issue["suggestion"], suggestion)
                self.assertIn(f"did you mean {kind!r}?", issue["message"])

    def test_a_kind_written_where_a_file_belongs_names_the_kind_it_means(self):
        with tempfile.TemporaryDirectory() as working_directory:
            _, envelope = run_office(["read", "spreadsheet"], working_directory)
        issue = envelope["issues"][0]
        self.assertEqual(issue["code"], "WRONG_INPUT_FORMAT")
        self.assertIn("did you mean 'xlsx'?", issue["message"])
        self.assertIn("office read <file>.xlsx", issue["suggestion"])

    def test_the_index_of_a_kind_names_operations_without_their_fields(self):
        index = self.guide("xlsx")
        self.assertIn("add_chart", index)
        self.assertNotIn("secondaryAxis", index)

    def test_a_first_read_stays_short_and_an_operation_gives_its_fields(self):
        index, apply_guide = self.guide("xlsx"), self.guide("apply", "xlsx")
        self.assertLess(len(index), 6000)
        self.assertLess(len(apply_guide), 8000)
        self.assertIn('op "add_pivot_table": summarize', apply_guide)
        self.assertNotIn("secondaryAxis", apply_guide)
        self.assertIn("office guide apply xlsx <op> lists one op's fields", apply_guide)
        self.assertIn("secondaryAxis (true or false)", self.guide("apply", "xlsx", "add_chart"))
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

    def test_an_empty_list_or_text_says_it_is_empty_rather_than_absent(self):
        empty_list = ListOf(Text(), non_empty=True).problems([], "spec.blocks")[0]
        empty_text = Text(non_empty=True).problems(" ", "spec.title")[0]
        self.assertEqual((empty_list.kind.code, empty_text.kind.code), ("MISSING_FIELD", "MISSING_FIELD"))
        self.assertIn("the list is empty", empty_list.message)
        self.assertNotEqual(empty_list.suggestion, empty_list.kind.default_suggestion())
        self.assertNotEqual(empty_text.suggestion, empty_text.kind.default_suggestion())


class PaperworkSkeletonTest(unittest.TestCase):
    def test_every_spec_skeleton_passes_the_renderer_schema(self):
        definitions = importlib.import_module("paperwork.paperwork_definitions")
        problems = []
        for spec_path in sorted((OFFICE_PATH / "references" / "paperwork").rglob("*.md")):
            for block in re.findall(r"```json\n(.*?)```", spec_path.read_text(encoding="utf-8"), re.S):
                document = json.loads(re.sub(r"\{\s*\.\.\.[^}]*\.\.\.\s*\}", '{"name": "sample"}', block))
                shape = skeleton_shape(document, definitions)
                if shape is not None:
                    problems.extend(f"{spec_path.name}: {issue.message}" for issue in shape.problems(document, "document"))
        self.assertEqual(problems, [])


    def test_every_spec_takes_its_document_number_from_the_registry(self):
        definitions = importlib.import_module("paperwork.paperwork_definitions")
        numbers = {}
        for spec_path in sorted((OFFICE_PATH / "references" / "paperwork").rglob("*.md")):
            for block in re.findall(r"```json\n(.*?)```", spec_path.read_text(encoding="utf-8"), re.S):
                document = json.loads(re.sub(r"\{\s*\.\.\.[^}]*\.\.\.\s*\}", '{"name": "sample"}', block))
                if "documentNumber" in document:
                    numbers[f"{spec_path.parent.name}/{spec_path.name}"] = document["documentNumber"]
        self.assertGreater(len(numbers), 20)
        self.assertEqual({spec for spec, number in numbers.items() if number != definitions.REGISTERED_DOCUMENT_NUMBER}, set())


def skeleton_shape(document, definitions):
    if "blocks" in document:
        return definitions.CONTRACT_DOCUMENT
    if "title" in document:
        return definitions.PAPERWORK_DOCUMENT
    return None


class DeckReviewResultTest(unittest.TestCase):
    def test_the_review_reports_every_warning_it_writes_as_an_issue_without_legacy_codes(self):
        from deck.review.deck_review import review_deck

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
