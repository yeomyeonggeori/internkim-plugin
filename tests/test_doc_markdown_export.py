from pathlib import Path
import tempfile
import unittest
import zipfile

from doc_fixture import run_office, run_office_python
from report_fixture import pdf_text


PROPOSAL = """# 도입 제안서

**수신처:** 주식회사 샘플상사 (담당: 최견본 팀장)
**제안사:** 주식회사 예시랩
**작성일:** 2026년 10월 1일

---

본문 첫 문단입니다.

본문 둘째 문단입니다.
"""


class MarkdownExportTest(unittest.TestCase):
    def test_links_images_and_nested_lists_survive_export(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            run_office_python("from PIL import Image\nImage.new('RGB', (40, 20)).save('chart.png')", directory)
            (directory / "source.md").write_text(
                "[소개](https://example.com/about) 참고\n\n![차트](chart.png)\n\n![없음](missing.png)\n\n- 하나\n  - 둘\n    - 셋\n- 넷\n",
                encoding="utf-8",
            )
            envelope = run_office(["doc", "export", "source.md", "--output", "source.docx"], directory)
            blocks = run_office(["doc", "read", "source.docx"], directory)["details"]["blocks"]
            with zipfile.ZipFile(directory / "source.docx") as archive:
                relationships = archive.read("word/_rels/document.xml.rels").decode()
                document_xml = archive.read("word/document.xml").decode()
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("IMAGE_UNAVAILABLE", "missing.png")])
        self.assertIn("https://example.com/about", relationships)
        self.assertIn("<w:hyperlink", document_xml)
        self.assertTrue(blocks[1].get("picture"))
        self.assertEqual([block["text"] for block in blocks if block["kind"] == "listItem"], ["하나", "둘", "셋", "넷"])



class LineAndRuleTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "제안서.md").write_text(PROPOSAL, encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def export(self, output_name):
        envelope = run_office(["doc", "export", "제안서.md", "--output", output_name], self.directory)
        self.assertNotEqual(envelope["status"], "error", envelope["issues"])

    def document_xml(self, name):
        with zipfile.ZipFile(self.directory / name) as archive:
            return archive.read("word/document.xml").decode()

    def test_lines_written_one_under_another_stay_one_paragraph_with_line_breaks(self):
        self.export("제안서.docx")
        texts = [block.get("text") for block in run_office(["doc", "read", "제안서.docx"], self.directory)["details"]["blocks"]]
        self.assertIn("수신처: 주식회사 샘플상사 (담당: 최견본 팀장)\n제안사: 주식회사 예시랩\n작성일: 2026년 10월 1일", texts)
        self.assertIn("본문 첫 문단입니다.", texts)
        self.assertIn("본문 둘째 문단입니다.", texts)
        self.assertEqual(self.document_xml("제안서.docx").count("<w:br/>"), 2)

    def test_a_thematic_break_is_a_bordered_empty_paragraph_and_comes_back_as_three_dashes(self):
        self.export("제안서.docx")
        document_xml = self.document_xml("제안서.docx")
        self.assertNotIn("---", document_xml)
        self.assertIn('<w:pBdr><w:bottom w:val="single"', document_xml)
        run_office(["convert", "제안서.docx", "왕복.md"], self.directory)
        markdown = (self.directory / "왕복.md").read_text(encoding="utf-8")
        self.assertIn("\n---\n", markdown)
        self.assertIn("**수신처:** 주식회사 샘플상사 (담당: 최견본 팀장)\n**제안사:** 주식회사 예시랩", markdown)

    def test_the_pdf_breaks_the_same_lines_and_draws_the_rule_instead_of_dashes(self):
        self.export("제안서.pdf")
        lines = pdf_text("제안서.pdf", self.directory).splitlines()
        self.assertTrue(any(line.startswith("수신처") and "제안사" not in line for line in lines), lines)
        self.assertNotIn("---", lines)

    def test_html_carries_the_break_and_the_rule(self):
        run_office(["convert", "제안서.md", "제안서.html"], self.directory)
        page = (self.directory / "제안서.html").read_text(encoding="utf-8")
        self.assertIn("최견본 팀장)<br><strong>제안사:</strong>", page)
        self.assertIn("<hr>", page)


if __name__ == "__main__":
    unittest.main()
