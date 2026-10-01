import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from xlsb_fixture import write_xlsb


OFFICE_ENTRY = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "office"
READERS = {
    "docx": ("doc read", "doc check", "doc validate", "doc render"),
    "xlsx": ("sheet read", "sheet check", "sheet validate", "sheet render"),
    "pptx": ("deck read", "deck check"),
    "pdf": ("pdf read", "pdf render", "pdf validate"),
}


def run_office(arguments, working_directory):
    completed = subprocess.run([str(OFFICE_ENTRY), *arguments], cwd=working_directory, capture_output=True, text=True, timeout=300)
    return json.loads(completed.stdout), completed.stderr


def write_inputs(directory):
    script = """
import sys
from pathlib import Path
import docx, openpyxl, pptx
from pypdf import PdfWriter
directory = Path(sys.argv[1])
docx.Document().save(directory / "plain.docx")
openpyxl.Workbook().save(directory / "plain.xlsx")
pptx.Presentation().save(directory / "plain.pptx")
writer = PdfWriter(); writer.add_blank_page(200, 200); writer.write(directory / "plain.pdf")
writer = PdfWriter(); writer.add_blank_page(200, 200); writer.encrypt("sample-password"); writer.write(directory / "locked.pdf")
from fpdf import FPDF
document = FPDF(); document.add_page(); document.set_font("Helvetica", size=12)
for line in range(40): document.cell(text=f"Sample line {line} for the owner locked report", new_x="LMARGIN", new_y="NEXT")
document.output(str(directory / "report.pdf"))
whole = (directory / "report.pdf").read_bytes()
(directory / "truncated.pdf").write_bytes(whole[:len(whole) // 2])
writer = PdfWriter(clone_from=str(directory / "report.pdf")); writer.encrypt(user_password="", owner_password="owner", permissions_flag=0, algorithm="RC4-128"); writer.write(directory / "owner-locked.pdf")
(directory / "notes.txt").write_text("이샘플의 메모", encoding="utf-8")
for name in ("plain.docx", "plain.xlsx", "plain.pptx"):
    whole = (directory / name).read_bytes()
    (directory / ("cut-" + name)).write_bytes(whole[:len(whole) // 2])
import zipfile
with zipfile.ZipFile(directory / "plain.docx") as source, zipfile.ZipFile(directory / "broken-part.docx", "w") as target:
    for item in source.infolist():
        data = source.read(item.filename)
        target.writestr(item, data[:len(data) // 2] if item.filename == "word/document.xml" else data)
(directory / "보고서.md").write_bytes("# 분기 보고서\\n\\n이샘플 작성\\n".encode("cp949"))
(directory / "실적.csv").write_bytes("지역,매출\\n서울,120\\n".encode("cp949"))
(directory / "utf16.md").write_bytes("# 제목\\n".encode("utf-16"))
(directory / "pdf-named.md").write_bytes((directory / "report.pdf").read_bytes())
(directory / "legacy.xls").write_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + bytes(504))
"""
    subprocess.run([str(OFFICE_ENTRY), "python", "-c", script, str(directory)], check=True, capture_output=True, timeout=300)


class InputBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temporary_directory.name)
        write_inputs(cls.directory)
        write_xlsb(cls.directory / "binary.xlsb", [("판매", [["지역", "매출"], ["서울", 120]], [])])

    @classmethod
    def tearDownClass(cls):
        cls.temporary_directory.cleanup()

    def assert_refused(self, command, input_name, code):
        envelope, stderr = run_office([*command.split(), input_name], self.directory)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(envelope["status"], "error", f"{command} {input_name}")
        self.assertEqual(envelope["issues"][0]["code"], code, f"{command} {input_name}")
        return envelope["issues"][0]

    def test_every_reader_names_the_command_for_a_file_of_another_kind(self):
        for kind, commands in READERS.items():
            other_kind = "xlsx" if kind != "xlsx" else "docx"
            for command in commands:
                with self.subTest(command=command):
                    issue = self.assert_refused(command, f"plain.{other_kind}", "WRONG_INPUT_FORMAT")
                    self.assertIn("office doc read" if other_kind == "docx" else "office sheet read", issue["suggestion"])

    def test_every_reader_answers_a_missing_file(self):
        for commands in READERS.values():
            for command in commands:
                with self.subTest(command=command):
                    self.assert_refused(command, "missing.docx", "INPUT_NOT_FOUND")

    def test_text_and_legacy_files_are_refused_with_what_they_are(self):
        self.assertEqual(self.assert_refused("doc read", "notes.txt", "WRONG_INPUT_FORMAT")["message"], "notes.txt is not a Word document: its content is not in any Office or PDF format")
        self.assertIn("office convert", self.assert_refused("sheet read", "legacy.xls", "WRONG_INPUT_FORMAT")["suggestion"])

    def test_an_empty_file_is_named_empty_by_every_reader_and_convert(self):
        for kind, commands in READERS.items():
            (self.directory / f"empty.{kind}").write_bytes(b"")
            for command in commands:
                with self.subTest(command=command):
                    self.assertEqual(self.assert_refused(command, f"empty.{kind}", "FILE_DAMAGED")["message"], f"empty.{kind} is empty (0 bytes)")
        envelope, _ = run_office(["convert", "empty.pdf", "empty.docx"], self.directory)
        self.assertEqual(envelope["summary"], "empty.pdf is empty (0 bytes)")

    def test_a_binary_workbook_is_sent_to_convert(self):
        issue = self.assert_refused("sheet read", "binary.xlsb", "WRONG_INPUT_FORMAT")
        self.assertIn("binary Excel workbook", issue["message"])
        self.assertIn("office convert binary.xlsb <name>.xlsx", issue["suggestion"])

    def test_a_password_protected_pdf_is_named_by_every_pdf_reader_and_convert(self):
        for command in READERS["pdf"]:
            with self.subTest(command=command):
                self.assert_refused(command, "locked.pdf", "PDF_PASSWORD_REQUIRED")
        envelope, stderr = run_office(["convert", "locked.pdf", "locked.docx"], self.directory)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(envelope["issues"][0]["code"], "PDF_PASSWORD_REQUIRED")

    def test_the_password_opens_the_pdf_for_every_reader_and_convert(self):
        for command in READERS["pdf"]:
            with self.subTest(command=command):
                envelope, stderr = run_office([*command.split(), "locked.pdf", "--password", "sample-password"], self.directory)
                self.assertNotIn("Traceback", stderr)
                self.assertNotIn("PDF_PASSWORD_REQUIRED", [issue["code"] for issue in envelope["issues"]], command)
        envelope, _ = run_office(["convert", "locked.pdf", "opened.md", "--password", "sample-password"], self.directory)
        self.assertNotIn("PDF_PASSWORD_REQUIRED", [issue["code"] for issue in envelope["issues"]])
        self.assertTrue((self.directory / "opened.md").exists())

    def test_a_truncated_pdf_is_refused_as_damaged_by_every_reader_and_convert(self):
        for command in (*READERS["pdf"], "pdf edit"):
            with self.subTest(command=command):
                self.assertIn("ask the user", self.assert_refused(command, "truncated.pdf", "FILE_DAMAGED")["suggestion"])
        for target in ("truncated.md", "truncated.docx", "truncated.xlsx", "truncated.pptx"):
            with self.subTest(target=target):
                envelope, stderr = run_office(["convert", "truncated.pdf", target], self.directory)
                self.assertNotIn("Traceback", stderr)
                self.assertEqual([issue["code"] for issue in envelope["issues"]], ["FILE_DAMAGED"])

    def test_an_owner_locked_pdf_converts_without_a_password(self):
        for target in ("owner-locked.md", "owner-locked.docx", "owner-locked.pptx"):
            with self.subTest(target=target):
                envelope, stderr = run_office(["convert", "owner-locked.pdf", target], self.directory)
                self.assertNotIn("Traceback", stderr)
                self.assertNotEqual(envelope["status"], "error", envelope["issues"])
        self.assertIn("Sample line 39 for the owner locked report", (self.directory / "owner-locked.md").read_text(encoding="utf-8"))

    def test_a_cut_short_or_broken_office_file_is_refused_as_damaged(self):
        for kind, commands in READERS.items():
            if kind == "pdf":
                continue
            for command in commands:
                with self.subTest(command=command):
                    self.assert_refused(command, f"cut-plain.{kind}", "FILE_DAMAGED")
        self.assertIn("unclosed token", self.assert_refused("doc read", "broken-part.docx", "FILE_DAMAGED")["message"])
        envelope, stderr = run_office(["convert", "broken-part.docx", "broken.md"], self.directory)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["FILE_DAMAGED"])

    def test_text_inputs_are_read_as_utf8_or_cp949_and_anything_else_is_named(self):
        envelope, _ = run_office(["doc", "export", "보고서.md", "--output", "보고서.docx"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        envelope, _ = run_office(["convert", "실적.csv", "실적.xlsx"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        rows, _ = run_office(["sheet", "read", "실적.xlsx"], self.directory)
        self.assertIn("서울", json.dumps(rows, ensure_ascii=False))
        for command in (["doc", "export", "utf16.md", "--output", "x.docx"], ["convert", "utf16.md", "x.html"]):
            with self.subTest(command=command):
                envelope, stderr = run_office(command, self.directory)
                self.assertNotIn("Traceback", stderr)
                self.assertEqual([issue["code"] for issue in envelope["issues"]], ["WRONG_INPUT_FORMAT"])
        issue = self.assert_refused("doc export", "pdf-named.md", "WRONG_INPUT_FORMAT")
        self.assertIn("office pdf read", issue["suggestion"])

    def test_a_wrong_password_is_refused_as_wrong(self):
        envelope, _ = run_office(["pdf", "read", "locked.pdf", "--password", "guess"], self.directory)
        self.assertEqual(envelope["issues"][0]["code"], "PDF_PASSWORD_REQUIRED")
        self.assertIn("does not open it", envelope["issues"][0]["message"])

    def test_an_edited_locked_pdf_stays_locked_with_the_same_password(self):
        edited = self.directory / "edited-locked.pdf"
        edited.write_bytes((self.directory / "locked.pdf").read_bytes())
        envelope, _ = run_office(["pdf", "edit", edited.name, "--heading", "추가 조항", "--password", "sample-password"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        self.assert_refused("pdf read", edited.name, "PDF_PASSWORD_REQUIRED")
        envelope, _ = run_office(["pdf", "read", edited.name, "--password", "sample-password"], self.directory)
        self.assertEqual(envelope["details"]["pageCount"], 2)

    def test_apply_checks_its_input_before_reading_the_operations(self):
        (self.directory / "ops.json").write_text("[]", encoding="utf-8")
        for command, other in (("doc apply", "plain.xlsx"), ("sheet apply", "plain.pptx"), ("deck apply", "plain.docx")):
            with self.subTest(command=command):
                envelope, stderr = run_office([*command.split(), other, "ops.json"], self.directory)
                self.assertNotIn("Traceback", stderr)
                self.assertEqual(envelope["issues"][0]["code"], "WRONG_INPUT_FORMAT")


if __name__ == "__main__":
    unittest.main()
