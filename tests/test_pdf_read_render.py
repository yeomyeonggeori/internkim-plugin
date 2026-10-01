from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, SCRIPTS_PATH, run_office, run_office_python
from pdf_fixture import STATEMENT_ROWS, statement_pdf_code
from render_fixture import png_size


FIXTURE_PDF = """
from fpdf import FPDF
pdf = FPDF(format="A4", unit="pt")
pdf.set_font("Helvetica", size=14)
pdf.add_page()
pdf.cell(text="Quarterly summary page one")
pdf.add_page(format="Letter")
pdf.cell(text="Second page, Letter size")
pdf.add_page()
pdf.output("fixture.pdf")
"""


class PdfFixture(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        run_office_python(FIXTURE_PDF, self.directory)

    def tearDown(self):
        self.temporary_directory.cleanup()


class ReadTest(PdfFixture):
    def test_pages_carry_text_size_and_whether_they_have_text(self):
        envelope = run_office(["pdf", "read", "fixture.pdf"], self.directory)
        details = envelope["details"]
        self.assertEqual(details["pageCount"], 3)
        self.assertFalse(details["truncated"])
        self.assertEqual([page["hasText"] for page in details["pages"]], [True, True, False])
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("PAGE_WITHOUT_TEXT", "pages 3")])
        self.assertIn("pdf render fixture.pdf --pages 3 --scale 2", envelope["issues"][0]["suggestion"])
        self.assertIn("Quarterly summary page one", details["pages"][0]["text"])
        self.assertEqual((details["pages"][0]["widthPoints"], details["pages"][0]["heightPoints"]), (595.28, 841.89))
        self.assertEqual((details["pages"][1]["widthPoints"], details["pages"][1]["heightPoints"]), (612.0, 792.0))

    def test_a_limit_truncates_and_start_continues(self):
        first = run_office(["pdf", "read", "fixture.pdf", "--limit", "1"], self.directory)["details"]
        self.assertTrue(first["truncated"])
        self.assertEqual([page["page"] for page in first["pages"]], [1])
        rest = run_office(["pdf", "read", "fixture.pdf", "--start", "2"], self.directory)["details"]
        self.assertEqual([page["page"] for page in rest["pages"]], [2, 3])
        self.assertFalse(rest["truncated"])


class ReadTablesTest(unittest.TestCase):
    def test_read_gives_the_rows_of_a_table_laid_out_without_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            run_office_python(statement_pdf_code(SCRIPTS_PATH.parent / "assets" / "fonts" / "paperlogy"), Path(directory))
            page = run_office(["pdf", "read", "statement.pdf"], Path(directory))["details"]["pages"][0]
        self.assertEqual(page["tables"], [STATEMENT_ROWS])

    def test_a_page_without_a_table_carries_no_tables_field(self):
        with tempfile.TemporaryDirectory() as directory:
            run_office_python(FIXTURE_PDF, Path(directory))
            pages = run_office(["pdf", "read", "fixture.pdf"], Path(directory))["details"]["pages"]
        self.assertEqual([page.get("tables") for page in pages], [None, None, None])


class RenderTest(PdfFixture):
    def test_every_page_becomes_a_png_of_the_scaled_size_and_a_contact_sheet_is_written(self):
        envelope = run_office(["pdf", "render", "fixture.pdf", "--scale", "1"], self.directory)
        self.assertEqual(envelope["status"], "ok")
        pages = envelope["details"]["pages"]
        self.assertEqual([page["page"] for page in pages], [1, 2, 3])
        self.assertEqual([png_size(self.directory / page["path"]) for page in pages], [(596, 842), (612, 792), (596, 842)])
        self.assertEqual([(page["widthPixels"], page["heightPixels"]) for page in pages], [(596, 842), (612, 792), (596, 842)])
        contact_sheet = self.directory / envelope["details"]["contactSheet"]
        self.assertTrue(contact_sheet.is_file())
        self.assertEqual(contact_sheet.parent, self.directory / envelope["outputPath"])
        self.assertGreater(png_size(contact_sheet)[0], 320)

    def test_scale_changes_the_pixel_size(self):
        envelope = run_office(["pdf", "render", "fixture.pdf", "--pages", "2", "--scale", "2"], self.directory)
        self.assertEqual([png_size(self.directory / page["path"]) for page in envelope["details"]["pages"]], [(1224, 1584)])

    def test_pages_select_a_subset(self):
        envelope = run_office(["pdf", "render", "fixture.pdf", "--pages", "1,3", "--scale", "0.5"], self.directory)
        self.assertEqual([page["page"] for page in envelope["details"]["pages"]], [1, 3])

    def test_a_page_the_pdf_lacks_is_refused(self):
        envelope = run_office(["pdf", "render", "fixture.pdf", "--pages", "2-9"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["PAGE_NOT_IN_DOCUMENT"])

    def test_a_scale_outside_the_range_is_refused(self):
        envelope = run_office(["pdf", "render", "fixture.pdf", "--scale", "40"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["INVALID_VALUE"])


class GuideTest(unittest.TestCase):
    def test_the_guide_lists_the_commands_and_the_render_issue(self):
        guide = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", "pdf"], capture_output=True, text=True, check=True).stdout
        for expected in ("office pdf read", "office pdf render", "PAGE_NOT_IN_DOCUMENT"):
            self.assertIn(expected, guide)


if __name__ == "__main__":
    unittest.main()
