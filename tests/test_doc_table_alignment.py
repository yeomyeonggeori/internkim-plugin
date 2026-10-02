from pathlib import Path
import re
import sys
import tempfile
import unittest
import zipfile

from doc_fixture import run_office


from doc.block_writers import html_table  # noqa: E402

MARKDOWN = "# 견적\n\n| 품목 | 수량 | 금액 |\n| :--- | :---: | ---: |\n| 유지보수 | 1 | 1,200,000 |\n| 교육 | 2 | 300,000 |\n"


class TableAlignmentTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "quote.md").write_text(MARKDOWN, encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_column_alignment_reaches_the_document_and_comes_back(self):
        self.assertEqual(run_office(["create", "quote.docx", "quote.md"], self.directory)["status"], "ok")
        document_xml = zipfile.ZipFile(self.directory / "quote.docx").read("word/document.xml").decode()
        self.assertEqual(re.findall(r'w:jc w:val="(\w+)"', document_xml)[:3], ["left", "center", "right"])
        self.assertEqual(run_office(["convert", "quote.docx", "back.md"], self.directory)["status"], "ok")
        self.assertIn("| :--- | :---: | ---: |", (self.directory / "back.md").read_text(encoding="utf-8"))

    def test_html_cells_carry_the_alignment(self):
        self.assertIn('<td style="text-align:right">', html_table([["금액"], ["1"]], ("right",)))


if __name__ == "__main__":
    unittest.main()
