import tempfile
from pathlib import Path
import unittest

from doc_fixture import block_texts, run_office, run_office_python, write_json


WRAPPED_RUNS_DOCUMENT = """
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

document = Document()
body = document.element.body
namespace = nsdecls("w")
paragraphs = [
    '<w:r><w:t xml:space="preserve">갑은 </w:t></w:r><w:ins w:id="1" w:author="이샘플"><w:r><w:t>삽입된</w:t></w:r></w:ins><w:del w:id="2" w:author="이샘플"><w:r><w:delText>삭제된</w:delText></w:r></w:del><w:r><w:t xml:space="preserve"> 문구</w:t></w:r>',
    '<w:moveTo w:id="3" w:author="박예시"><w:r><w:t>옮겨온</w:t></w:r></w:moveTo><w:moveFrom w:id="4" w:author="박예시"><w:r><w:t>옮겨간</w:t></w:r></w:moveFrom>',
    '<w:smartTag w:uri="urn:example" w:element="date"><w:r><w:t>2026년 9월</w:t></w:r></w:smartTag>',
    '<w:fldSimple w:instr=" DATE "><w:r><w:t>2026-09-01</w:t></w:r></w:fldSimple>',
    '<w:sdt><w:sdtPr/><w:sdtContent><w:r><w:t>인라인 컨트롤</w:t></w:r></w:sdtContent></w:sdt>',
    '<w:customXml w:element="party"><w:r><w:t>최견본</w:t></w:r></w:customXml>',
    '<w:hyperlink w:anchor="top"><w:r><w:t>링크</w:t></w:r></w:hyperlink><w:r><w:t>탭</w:t><w:tab/><w:t>뒤</w:t><w:br w:type="page"/></w:r>',
]
for runs in paragraphs:
    body.insert(len(body) - 1, parse_xml(f"<w:p {namespace}>{runs}</w:p>"))
table = document.add_table(rows=1, cols=1)
table.rows[0].cells[0]._tc.append(parse_xml(f'<w:p {namespace}><w:ins w:id="5" w:author="이샘플"><w:r><w:t>셀 삽입</w:t></w:r></w:ins></w:p>'))
document.save("wrapped.docx")
"""


class WrappedRunTextTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        run_office_python(WRAPPED_RUNS_DOCUMENT, self.directory)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_read_shows_text_inside_every_run_wrapper_and_hides_removed_text(self):
        self.assertEqual(block_texts(self.directory, "wrapped.docx"), [
            ("paragraph", "갑은 삽입된 문구"),
            ("paragraph", "옮겨온"),
            ("paragraph", "2026년 9월"),
            ("paragraph", "2026-09-01"),
            ("paragraph", "인라인 컨트롤"),
            ("paragraph", "최견본"),
            ("paragraph", "링크탭\t뒤"),
            ("table", [["\n셀 삽입"]]),
        ])

    def test_validate_finds_required_text_inside_insertions(self):
        envelope = run_office(["check", "wrapped.docx", "--required-text", "삽입된", "--required-text", "셀 삽입", "--forbidden-text", "삭제된"], self.directory)
        codes = [issue["code"] for issue in envelope["issues"]]
        self.assertNotIn("REQUIRED_TEXT_MISSING", codes)
        self.assertNotIn("FORBIDDEN_TEXT_PRESENT", codes)

    def test_replace_text_reaches_inserted_and_wrapped_runs(self):
        write_json(self.directory / "ops.json", [
            {"op": "replace_text", "find": "삽입된", "replace": "고친"},
            {"op": "replace_text", "find": "최견본", "replace": "박예시"},
        ])
        envelope = run_office(["apply", "wrapped.docx", "ops.json"], self.directory)
        self.assertEqual(envelope["status"], "ok")
        texts = block_texts(self.directory, "wrapped.docx")
        self.assertEqual(texts[0], ("paragraph", "갑은 고친 문구"))
        self.assertEqual(texts[5], ("paragraph", "박예시"))


if __name__ == "__main__":
    unittest.main()
