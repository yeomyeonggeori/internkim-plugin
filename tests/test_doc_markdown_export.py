import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from doc_fixture import run_office, run_office_python
from report_fixture import pdf_text

from doc.blocks.writers import markdown_text  # noqa: E402
from doc.blocks.markdown import CodeBlock, parse_markdown  # noqa: E402


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
            envelope = run_office(["create", "source.docx", "source.md"], directory)
            blocks = run_office(["read", "source.docx"], directory)["details"]["blocks"]
            with zipfile.ZipFile(directory / "source.docx") as archive:
                relationships = archive.read("word/_rels/document.xml.rels").decode()
                document_xml = archive.read("word/document.xml").decode()
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("IMAGE_UNAVAILABLE", "missing.png")])
        self.assertIn("https://example.com/about", relationships)
        self.assertIn("<w:hyperlink", document_xml)
        self.assertTrue(blocks[1].get("picture"))
        self.assertEqual([block["text"] for block in blocks if block["kind"] == "listItem"], ["하나", "둘", "셋", "넷"])


FORMULAS = """# 수식

피타고라스 정리는 $a^2+b^2=c^2$ 이다. 가격은 $100에서 $200 사이.

$$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$$

잘못된 수식 $\\foo{x}$ 끝.
"""


class LineAndRuleTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "제안서.md").write_text(PROPOSAL, encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def export(self, output_name):
        envelope = run_office(["create", output_name, "제안서.md"], self.directory)
        self.assertNotEqual(envelope["status"], "error", envelope["issues"])

    def document_xml(self, name):
        with zipfile.ZipFile(self.directory / name) as archive:
            return archive.read("word/document.xml").decode()

    def test_lines_written_one_under_another_stay_one_paragraph_with_line_breaks(self):
        self.export("제안서.docx")
        texts = [block.get("text") for block in run_office(["read", "제안서.docx"], self.directory)["details"]["blocks"]]
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
        run_office(["create", "제안서.html", "제안서.md"], self.directory)
        page = (self.directory / "제안서.html").read_text(encoding="utf-8")
        self.assertIn("최견본 팀장)<br><strong>제안사:</strong>", page)
        self.assertIn("<hr>", page)



    def test_a_line_break_in_a_table_cell_is_a_line_break_in_every_output(self):
        table = "| 기관 | 서명 |\n| --- | --- |\n| 기관명: 견본재단<br>대표자: 최견본 | 날짜: 2026-03-02<br/>장소: 서울 |\n| Example Labs<BR />CTO Alex Sample | **확인**<br>(인) |\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "table.md").write_text(table, encoding="utf-8")
            self.assertEqual(run_office(["create", "table.docx", "table.md"], directory)["status"], "ok")
            cells = next(block for block in run_office(["read", "table.docx"], directory)["details"]["blocks"] if block["kind"] == "table")["cells"]
            self.assertEqual(cells[1:], [["기관명: 견본재단\n대표자: 최견본", "날짜: 2026-03-02\n장소: 서울"], ["Example Labs\nCTO Alex Sample", "확인\n(인)"]])
            (directory / "applied.md").write_text("시작\n", encoding="utf-8")
            run_office(["create", "applied.docx", "applied.md"], directory)
            (directory / "operations.json").write_text(json.dumps([{"op": "insert_markdown", "at": "end", "markdown": table}]), encoding="utf-8")
            self.assertEqual(run_office(["apply", "applied.docx", "operations.json"], directory)["status"], "ok")
            applied = next(block for block in run_office(["read", "applied.docx"], directory)["details"]["blocks"] if block["kind"] == "table")["cells"]
            self.assertEqual(applied, cells)
            self.assertEqual(run_office(["create", "table.pdf", "table.md"], directory)["status"], "ok")
            text = pdf_text(directory / "table.pdf", directory)
            self.assertNotIn("<br", text.lower())
            self.assertIn("대표자: 최견본", text)


class MathTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "수식.md").write_text(FORMULAS, encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def export(self, output_name):
        return run_office(["create", output_name, "수식.md"], self.directory)

    def test_math_becomes_word_equations_and_unreadable_latex_is_named(self):
        envelope = self.export("수식.docx")
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("MATH_NOT_CONVERTED", "\\foo{x}")])
        with zipfile.ZipFile(self.directory / "수식.docx") as archive:
            document_xml = archive.read("word/document.xml").decode()
        self.assertEqual(document_xml.count("<m:oMathPara>"), 1)
        self.assertEqual(document_xml.count("<m:oMath>"), 2)
        self.assertNotIn("$a^2", document_xml)
        self.assertNotIn("\\frac", document_xml)
        self.assertIn("$100에서 $200 사이", document_xml)
        self.assertIn("$\\foo{x}$", document_xml)

    def test_a_formula_word_cannot_hold_is_named_for_docx_and_still_typeset_in_the_pdf(self):
        (self.directory / "평균.md").write_text("분기 평균은 $\\bar{x} = 3$ 이다.\n", encoding="utf-8")
        word = run_office(["create", "평균.docx", "평균.md"], self.directory)
        self.assertEqual([issue["code"] for issue in word["issues"]], ["MATH_NOT_CONVERTED"])
        self.assertIn("no Word equation form", word["issues"][0]["message"])
        pdf = run_office(["create", "평균.pdf", "평균.md"], self.directory)
        self.assertEqual(pdf["issues"], [])

    def test_broken_latex_is_named_with_its_reason_and_never_raised(self):
        (self.directory / "깨진.md").write_text("제곱은 $x^$ 이고 근은 $\\sqrt$ 이다.\n", encoding="utf-8")
        envelope = run_office(["create", "깨진.docx", "깨진.md"], self.directory)
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("MATH_NOT_CONVERTED", "x^"), ("MATH_NOT_CONVERTED", "\\sqrt")])
        for issue in envelope["issues"]:
            self.assertNotIn("()", issue["message"])

    def test_the_pdf_typesets_the_formulas_instead_of_printing_latex(self):
        self.assertEqual([issue["code"] for issue in self.export("수식.pdf")["issues"]], ["MATH_NOT_CONVERTED"])
        text = pdf_text("수식.pdf", self.directory)
        self.assertNotIn("\\frac", text)
        self.assertNotIn("$a^2", text)
        self.assertIn("4ac", text)
        self.assertIn("$100에서 $200 사이", text)


CODE_NOTE = """# 배포 절차

아래 명령을 실행합니다.

```bash
cd /srv/app
make build   # 빌드
    ./deploy --env production
```

끝.
"""


class CodeBlockTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "절차.md").write_text(CODE_NOTE, encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def export(self, output_name):
        envelope = run_office(["create", output_name, "절차.md"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])

    def test_a_code_fence_is_read_as_written_and_written_back_as_a_fence(self):
        blocks = parse_markdown(CODE_NOTE)
        self.assertIn(CodeBlock("cd /srv/app\nmake build   # 빌드\n    ./deploy --env production", "bash"), blocks)
        self.assertEqual(parse_markdown(markdown_text(blocks)), blocks)

    def test_a_code_fence_becomes_one_shaded_paragraph_in_the_code_font(self):
        self.export("절차.docx")
        with zipfile.ZipFile(self.directory / "절차.docx") as archive:
            document = archive.read("word/document.xml").decode()
        self.assertNotIn("```", document)
        code = document[document.index("cd /srv/app") - 600:document.index("production") + 20]
        self.assertIn('w:fill="F2F4F7"', code)
        self.assertIn('w:eastAsia="D2Coding"', code)
        self.assertEqual(code.count("<w:br/>"), 2)
        self.assertIn("    ./deploy", document)

    def test_the_pdf_and_html_keep_the_code_as_written(self):
        self.export("절차.pdf")
        text = pdf_text("절차.pdf", self.directory)
        self.assertNotIn("```", text)
        self.assertIn("make build", text)
        run_office(["create", "절차.html", "절차.md"], self.directory)
        self.assertIn("<pre><code>cd /srv/app\nmake build   # 빌드\n    ./deploy --env production</code></pre>", (self.directory / "절차.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
