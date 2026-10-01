import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, run_office, run_office_python
from report_fixture import CHART_IMAGE, REPORT_MARKDOWN, pdf_text


def export_pdf(markdown_name, working_directory):
    return run_office(["doc", "export", markdown_name, "--output", str(Path(markdown_name).with_suffix(".pdf"))], working_directory)


class DocumentPdfTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "보고서.md").write_text(REPORT_MARKDOWN, encoding="utf-8")
        run_office_python(CHART_IMAGE, self.directory)

    def tearDown(self):
        self.temporary_directory.cleanup()

    @unittest.skipUnless(shutil.which("bun"), "bun is not installed")
    def test_markdown_pdf_is_typeset_with_extractable_korean_text(self):
        envelope = export_pdf("보고서.md", self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        text = pdf_text("보고서.pdf", self.directory)
        self.assertIn("42억 3,000만 원", text)
        self.assertIn("1 / 1", text)
        validation = run_office(["pdf", "validate", "보고서.pdf", "--required-text", "대형 고객 3곳"], self.directory)
        self.assertEqual(validation["status"], "ok", validation["issues"])

    @unittest.skipUnless(shutil.which("bun"), "bun is not installed")
    def test_no_heading_is_left_alone_at_the_bottom_of_a_page(self):
        sentence = "본 절은 사업 추진 현황과 향후 계획을 설명하며, 각 항목의 근거 자료와 일정, 담당 조직을 함께 정리한다. "
        sections = [f"## {number}. 추진 항목 {number}\n\n{sentence * (2 + number * 7 % 9)}\n" for number in range(1, 31)]
        (self.directory / "긴보고서.md").write_text("# 하반기 사업 보고서\n\n" + "\n".join(sections), encoding="utf-8")
        self.assertEqual(export_pdf("긴보고서.md", self.directory)["status"], "ok")
        code = (
            "import json, pypdfium2\n"
            "document = pypdfium2.PdfDocument('긴보고서.pdf')\n"
            "print(json.dumps([[line.strip() for line in page.get_textpage().get_text_range().splitlines() if line.strip()] for page in document]))\n"
        )
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", code], capture_output=True, text=True, cwd=self.directory, check=True)
        pages = json.loads(completed.stdout)
        self.assertGreater(len(pages), 3)
        for number, lines in enumerate(pages[:-1], start=1):
            body = lines[:-1] if lines[-1].replace(" ", "") == f"{number}/{len(pages)}" else lines
            self.assertNotRegex(body[-1], r"^\d+\. 추진 항목 \d+$", f"page {number} ends with a heading")

    @unittest.skipUnless(shutil.which("bun"), "bun is not installed")
    def test_a_character_no_font_draws_is_named(self):
        (self.directory / "기호.md").write_text("# 기호\n\n완료 😀\n", encoding="utf-8")
        envelope = export_pdf("기호.md", self.directory)
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("GLYPH_NOT_COVERED", "😀")])


    def test_without_bun_the_plain_renderer_draws_the_pdf_and_says_so(self):
        environment = {"HOME": str(self.directory), "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin"}
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "doc", "export", "보고서.md", "--output", "보고서.pdf"], capture_output=True, text=True, cwd=self.directory, env=environment)
        envelope = json.loads(completed.stdout)
        self.assertEqual(envelope["issues"][0]["code"], "PDF_RENDERER_UNAVAILABLE")
        self.assertTrue((self.directory / "보고서.pdf").exists())

class ExportFormatTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "메모.md").write_text("# 메모\n\n이샘플이 작성했다.\n", encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_the_output_extension_picks_the_format(self):
        for name, signature in (("메모.pdf", b"%PDF-"), ("메모.docx", b"PK")):
            with self.subTest(output=name):
                envelope = run_office(["doc", "export", "메모.md", "--output", name], self.directory)
                self.assertNotEqual(envelope["status"], "error", envelope["issues"])
                self.assertTrue((self.directory / name).read_bytes().startswith(signature))

    def test_an_output_that_is_neither_docx_nor_pdf_is_refused_before_writing(self):
        envelope = run_office(["doc", "export", "메모.md", "--output", "메모.doc"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["WRONG_OUTPUT_FORMAT"])
        self.assertIn("메모.pdf", envelope["issues"][0]["suggestion"])
        self.assertFalse((self.directory / "메모.doc").exists())

    def test_there_is_no_format_flag_to_disagree_with_the_extension(self):
        envelope = run_office(["doc", "export", "메모.md", "--format", "pdf", "--output", "메모.docx"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["INVALID_ARGUMENTS"])
        self.assertFalse((self.directory / "메모.docx").exists())


if __name__ == "__main__":
    unittest.main()
