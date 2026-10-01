import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, SCRIPTS_PATH, run_office, run_office_python


REPORT = """
from docx import Document
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Pt

document = Document()
footer = document.sections[0].footer.paragraphs[0]
run = footer.add_run()
for kind, text in (("begin", None), ("instr", " PAGE "), ("separate", None), ("text", "1"), ("end", None)):
    node = OxmlElement("w:instrText" if kind == "instr" else "w:t" if kind == "text" else "w:fldChar")
    if text is None:
        node.set(qn("w:fldCharType"), kind)
    else:
        node.text = text
    run._r.append(node)
footer.add_run(" 쪽")
document.sections[0].header.paragraphs[0].text = "예시상사 내부 보고"
document.add_heading("분기 보고서", 0)
for item in ("매출 요약", "지역별 실적", "다음 분기 계획"):
    document.add_paragraph(item, style="List Number")
table = document.add_table(rows=3, cols=3)
table.style = "Table Grid"
table.cell(0, 0).merge(table.cell(0, 2)).text = "병합 머리글"
table.cell(1, 0).merge(table.cell(2, 0)).text = "세로"
paragraph = document.add_paragraph("수정 전 문장")
paragraph._p.append(parse_xml(f'<w:ins {nsdecls("w")} w:id="1" w:author="이샘플" w:date="2026-09-01T09:00:00Z"><w:r><w:t xml:space="preserve"> 추가된 문장</w:t></w:r></w:ins>'))
for number in range(40):
    document.add_paragraph(f"{number + 1}번째 문단입니다. 본 문단은 페이지 나눔을 확인하기 위해 충분히 길게 작성한 한국어 문장으로, 줄바꿈이 여러 번 일어나도록 이어집니다.")
breaker = document.add_paragraph("나눔 앞 문장")
breaker.runs[0].add_break(WD_BREAK.PAGE)
breaker.add_run("나눔 뒤 문장")
document.save("보고서.docx")
"""


def page_sections(html):
    return re.findall(r'<section data-page="(\d+)" style="([^"]*)">(.*?)</section>', html, re.S)


class DocumentPreviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temporary_directory.name)
        run_office_python(REPORT, cls.directory)
        cls.envelope = run_office(["doc", "render", "보고서.docx"], cls.directory)
        cls.html = (cls.directory / "보고서-preview" / "preview.html").read_text(encoding="utf-8")
        cls.pages = page_sections(cls.html)

    @classmethod
    def tearDownClass(cls):
        cls.temporary_directory.cleanup()

    def test_each_page_is_one_letter_section_with_inline_styles_only(self):
        self.assertGreaterEqual(len(self.pages), 3)
        self.assertEqual([int(number) for number, _, _ in self.pages], list(range(1, len(self.pages) + 1)))
        self.assertTrue(all("width:816px;height:1056px" in style for _, style, _ in self.pages))
        for forbidden in ("<style", "<script", "::before", "::after", "counter(", ":has("):
            self.assertNotIn(forbidden, self.html)
        self.assertEqual(self.envelope["details"]["pageCount"], len(self.pages))

    def test_fonts_name_the_files_the_layout_measured_with(self):
        fonts = self.envelope["details"]["previewFonts"]
        self.assertTrue(fonts)
        self.assertTrue(all(Path(font["path"]).is_file() and font["weight"] in (400, 700) for font in fonts))
        families = {font["family"] for font in fonts}
        for declaration in set(re.findall(r"font-family:(.*?);", self.html)):
            self.assertTrue(all(name in families for name in re.findall(r"&quot;([^&]*)&quot;", declaration) if name != "Korean Fallback") or "Korean Fallback" in families, declaration)

    def test_headers_footers_numbering_merges_and_tracked_insertions_show(self):
        first, last = self.pages[0][2], self.pages[-1][2]
        self.assertIn("예시상사 내부 보고", first)
        self.assertRegex(first, r">1</span><span[^>]*> 쪽<")
        self.assertRegex(last, rf">{len(self.pages)}</span><span[^>]*> 쪽<")
        self.assertIn(">1.</span>", first)
        self.assertIn("grid-column:1 / span 3", first)
        self.assertIn("grid-row:2 / span 2", first)
        self.assertRegex(first, r"text-decoration:underline;color:#1d4ed8\">[^<]*추가된 문장")

    def test_a_page_break_starts_the_text_after_it_on_a_new_page(self):
        before = next(index for index, (_, _, body) in enumerate(self.pages) if "나눔 앞 문장" in body)
        after = next(index for index, (_, _, body) in enumerate(self.pages) if "나눔 뒤 문장" in body)
        self.assertEqual(after, before + 1)

    def test_every_page_holds_no_more_than_its_body_area(self):
        code = (
            "import json, sys\n"
            f"sys.path[0:0] = [{str(SCRIPTS_PATH / 'doc')!r}, {str(SCRIPTS_PATH / 'deck')!r}, {str(SCRIPTS_PATH)!r}]\n"
            "from pathlib import Path\n"
            "from docx_layout import Layout\n"
            "from docx_pagination import Paginator\n"
            "from docx_preview import DocxModelBuilder\n"
            "from preview_fonts import FontRegistry\n"
            "pages = Paginator(Layout(FontRegistry())).paginate(DocxModelBuilder(Path('보고서.docx')).sections())\n"
            "print(json.dumps([(sum(item.height for item in page.placed), page.body_bottom - page.body_top) for page in pages]))\n"
        )
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", code], capture_output=True, text=True, cwd=self.directory, check=True)
        for used, available in json.loads(completed.stdout):
            self.assertLessEqual(used, available + 0.5)


if __name__ == "__main__":
    unittest.main()
