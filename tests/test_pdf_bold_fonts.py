import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

OFFICE_SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(OFFICE_SCRIPTS_PATH))

from fonts.registry import SANS_BODY, default_family, resolved_face  # noqa: E402
from fonts.font_files import bold_sibling  # noqa: E402

SOURCE_FONT_PATH = resolved_face(default_family(SANS_BODY).name).path


def save_renamed_font(source_path, target_path, postscript_name):
    from fontTools.ttLib import TTFont

    font = TTFont(str(source_path), fontNumber=0)
    for name_identifier in (1, 4, 6, 16, 17, 18, 21, 22, 25):
        font["name"].removeNames(nameID=name_identifier)
    for name_identifier in (1, 4, 6):
        font["name"].setName(postscript_name, name_identifier, 3, 1, 0x409)
        font["name"].setName(postscript_name, name_identifier, 1, 0, 0)
    font.save(str(target_path))


def run_office_script(script_path, *arguments):
    environment = {**os.environ, "PYTHONPATH": str(OFFICE_SCRIPTS_PATH)}
    completed = subprocess.run([sys.executable, str(OFFICE_SCRIPTS_PATH / script_path), *arguments], capture_output=True, text=True, env=environment)
    return json.loads(completed.stdout)


def embedded_font_names(pdf_path):
    from pypdf import PdfReader

    names = set()
    for page in PdfReader(str(pdf_path)).pages:
        fonts = page["/Resources"].get("/Font", {})
        names.update(str(face_font(fonts[key].get_object())["/BaseFont"]).split("+")[-1] for key in fonts)
    return names


def face_font(font):
    descendants = font.get("/DescendantFonts")
    return descendants[0].get_object() if descendants else font


def issue_codes(result):
    return [issue["code"] for issue in result["issues"]]


class BoldFontTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.directory, ignore_errors=True))
        self.regular_path = self.directory / "TestGothic.ttf"
        save_renamed_font(SOURCE_FONT_PATH, self.regular_path, "TestGothicRegular")

    def add_bold_sibling(self):
        save_renamed_font(SOURCE_FONT_PATH, self.directory / "TestGothicBold.ttf", "TestGothicBoldFace")

    def create_pdf(self):
        specification = {"title": "Report", "fontPath": str(self.regular_path), "sections": [{"title": "Summary", "paragraphs": ["Body text"]}]}
        specification_path = self.directory / "spec.json"
        specification_path.write_text(json.dumps(specification))
        output_path = self.directory / "out.pdf"
        result = run_office_script("pdf/create_pdf.py", str(output_path), str(specification_path))
        return result, output_path

    def test_pdf_create_embeds_a_second_font_file_for_headings(self):
        self.add_bold_sibling()
        result, output_path = self.create_pdf()
        self.assertEqual(issue_codes(result), [])
        self.assertEqual(embedded_font_names(output_path), {"TestGothicRegular", "TestGothicBoldFace"})

    def test_pdf_create_warns_when_no_bold_face_exists(self):
        result, output_path = self.create_pdf()
        self.assertEqual(issue_codes(result), ["BOLD_FONT_UNAVAILABLE"])
        self.assertEqual(result["status"], "warning")
        self.assertEqual(embedded_font_names(output_path), {"TestGothicRegular"})

    def test_a_markdown_pdf_embeds_bold_for_headings(self):
        self.add_bold_sibling()
        markdown_path = self.directory / "content.md"
        markdown_path.write_text("# Title\n\nBody\n")
        result = run_office_script("doc/export_document.py", str(markdown_path.with_suffix(".pdf")), str(markdown_path), "--font-path", str(self.regular_path))
        self.assertEqual(issue_codes(result), [])
        self.assertEqual(embedded_font_names(Path(result["outputPath"])), {"TestGothicRegular", "TestGothicBoldFace"})

    def test_a_form_embeds_bold_for_titles(self):
        self.add_bold_sibling()
        (self.directory / "company-profile.json").write_text(json.dumps({"name": "Sample Co"}))
        document = {"title": "Quote", "company": str(self.directory / "company-profile.json"), "sections": [{"title": "Terms", "paragraphs": ["Body"]}], "fontPath": str(self.regular_path)}
        document_path = self.directory / "document.json"
        document_path.write_text(json.dumps(document))
        result = run_office_script("paperwork/merge_form.py", "intl/quote", str(document_path), str(self.directory / "form.pdf"))
        self.assertEqual(issue_codes(result), [])
        self.assertEqual(embedded_font_names(self.directory / "form.pdf"), {"TestGothicRegular", "TestGothicBoldFace"})


class BoldSiblingTest(unittest.TestCase):
    def test_a_bold_file_beside_the_regular_file_is_found(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("NanumGothic.ttf", "NanumGothicBold.ttf", "NotoSansCJK-Regular.ttc", "NotoSansCJK-Bold.ttc"):
                (Path(directory) / name).write_bytes(b"")
            self.assertEqual(bold_sibling(Path(directory) / "NanumGothic.ttf"), Path(directory) / "NanumGothicBold.ttf")
            self.assertEqual(bold_sibling(Path(directory) / "NotoSansCJK-Regular.ttc"), Path(directory) / "NotoSansCJK-Bold.ttc")

    def test_a_regular_file_alone_has_no_bold_face(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "NanumGothic.ttf").write_bytes(b"")
            self.assertIsNone(bold_sibling(Path(directory) / "NanumGothic.ttf"))


if __name__ == "__main__":
    unittest.main()
