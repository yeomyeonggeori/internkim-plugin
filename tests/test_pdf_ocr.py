import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from openpyxl import load_workbook

from doc_fixture import run_office, run_office_python
from pdf_fixture import SCANNED_STATEMENT_PDF, copy_pdf_fixture
from skill_copy_fixture import copy_skill


AMOUNTS = ["금액", "1,440,000", "540,000", "1,192,500", "432,000", "420,000", "4,024,500"]


class ScannedStatementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temporary_directory.name)
        copy_pdf_fixture("statement.pdf", cls.directory)
        run_office_python(SCANNED_STATEMENT_PDF, cls.directory)

    @classmethod
    def tearDownClass(cls):
        cls.temporary_directory.cleanup()

    def test_without_ocr_the_scan_is_named_with_the_rerun_that_reads_it(self):
        envelope = run_office(["pdf", "read", "scanned-statement.pdf"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["PAGE_WITHOUT_TEXT"])
        self.assertIn("office pdf read scanned-statement.pdf --ocr", envelope["issues"][0]["suggestion"])
        converted = run_office(["convert", "scanned-statement.pdf", "scan.md"], self.directory)
        self.assertIn("office convert scanned-statement.pdf scan.md --ocr", converted["issues"][0]["suggestion"])
        slides = run_office(["convert", "scanned-statement.pdf", "scan.pptx"], self.directory)
        self.assertNotIn("--ocr", slides["issues"][0]["suggestion"])

    def test_read_with_ocr_gives_the_page_text_and_its_table(self):
        envelope = run_office(["pdf", "read", "scanned-statement.pdf", "--ocr"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["PAGE_READ_BY_OCR"])
        page = envelope["details"]["pages"][0]
        self.assertTrue(page["readByOcr"])
        self.assertFalse(page["hasText"])
        self.assertIn("거래 명세서", page["text"])
        self.assertIn("sample@example.com", page["text"])
        table, = page["tables"]
        self.assertEqual([row[-1] for row in table], AMOUNTS)
        self.assertEqual([row[0] for row in table][1:], ["2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "합계"])

    def test_convert_with_ocr_writes_the_scanned_table_as_typed_cells(self):
        envelope = run_office(["convert", "scanned-statement.pdf", "scan.xlsx", "--ocr"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["PAGE_READ_BY_OCR"])
        sheet = load_workbook(self.directory / "scan.xlsx").active
        self.assertEqual([cell.value for cell in sheet["E"]], ["금액", 1440000, 540000, 1192500, 432000, 420000, 4024500])

    def test_ocr_is_refused_for_a_route_that_cannot_use_it(self):
        envelope = run_office(["convert", "scanned-statement.pdf", "scan.pptx", "--ocr"], self.directory)
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("INVALID_VALUE", "--ocr")])

    def test_an_engine_that_is_not_prepared_is_named_with_its_setup_and_the_page_still_answers(self):
        with tempfile.TemporaryDirectory() as root:
            office_entry = copy_skill(Path(root) / "office", ("python environment", "fonts"))
            environment = {**os.environ, "PATH": str(Path(sys.executable).parent)}
            completed = subprocess.run([sys.executable, str(office_entry), "pdf", "read", "scanned-statement.pdf", "--ocr"], capture_output=True, text=True, cwd=self.directory, env=environment)
        self.assertNotIn("Traceback", completed.stderr)
        envelope = json.loads(completed.stdout)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["OCR_UNAVAILABLE", "PAGE_WITHOUT_TEXT"])
        self.assertIn("office setup --with-ocr", envelope["issues"][0]["message"])
        self.assertNotIn("--ocr", envelope["issues"][1]["suggestion"])


if __name__ == "__main__":
    unittest.main()
