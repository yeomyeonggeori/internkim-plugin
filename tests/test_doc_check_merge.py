import unittest
import zipfile

from doc_fixture import DocumentFixture, block_texts, run_office, run_office_python, write_json


class CheckTest(DocumentFixture):
    def test_each_finding_suggests_the_operation_that_fixes_it(self):
        run_office_python("""
            from docx import Document
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            document = Document("fixture.docx")
            fonts = document.styles.element.find(qn("w:docDefaults")).find(qn("w:rPrDefault")).find(qn("w:rPr")).find(qn("w:rFonts"))
            fonts.attrib.pop(qn("w:eastAsiaTheme"))
            contents = document.paragraphs[0].insert_paragraph_before()
            run = contents.add_run()
            for kind, text in (("begin", None), ("instr", " TOC \\\\o "), ("separate", None), ("text", "개요"), ("end", None)):
                node = OxmlElement("w:instrText" if kind == "instr" else "w:t" if kind == "text" else "w:fldChar")
                if text is None:
                    node.set(qn("w:fldCharType"), kind)
                else:
                    node.text = text
                run._r.append(node)
            link = OxmlElement("w:hyperlink")
            link.set(qn("w:anchor"), "missing_bookmark")
            document.paragraphs[-1]._p.append(link)
            document.save("fixture.docx")
        """, self.directory)
        envelope = run_office(["doc", "check", "fixture.docx"], self.directory)
        findings = {issue["code"]: issue["suggestion"] for issue in envelope["issues"]}
        self.assertEqual(set(findings), {"PLACEHOLDER_LEFT", "BROKEN_INTERNAL_REFERENCE", "STALE_TABLE_OF_CONTENTS", "EAST_ASIA_FONT_MISSING"})
        fixes = [findings["PLACEHOLDER_LEFT"] | {"replace": "박예시"}, findings["STALE_TABLE_OF_CONTENTS"], findings["EAST_ASIA_FONT_MISSING"]]
        write_json(self.directory / "fixes.json", fixes)
        self.assertEqual(run_office(["doc", "apply", "fixture.docx", "fixes.json"], self.directory)["status"], "ok")
        remaining = {issue["code"] for issue in run_office(["doc", "check", "fixture.docx"], self.directory)["issues"]}
        self.assertEqual(remaining, {"BROKEN_INTERNAL_REFERENCE"})
        with zipfile.ZipFile(self.directory / "fixture.docx") as archive:
            self.assertIn(b'w:updateFields w:val="true"', archive.read("word/settings.xml"))


class MergeTest(DocumentFixture):
    def test_a_missing_value_writes_nothing(self):
        write_json(self.directory / "values.json", {"customer": "박예시"})
        envelope = run_office(["doc", "merge", "fixture.docx", "values.json", "merged.docx"], self.directory)
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("UNRESOLVED_PLACEHOLDER", "values.customer_name")])
        self.assertFalse((self.directory / "merged.docx").exists())

    def test_values_fill_placeholders_and_unused_names_warn(self):
        write_json(self.directory / "values.json", {"customer_name": "박예시", "custmer": "오타"})
        envelope = run_office(["doc", "merge", "fixture.docx", "values.json", "merged.docx"], self.directory)
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("UNUSED_VALUE", "values.custmer")])
        self.assertIn(("paragraph", "첫 문단 박예시 입니다."), block_texts(self.directory, "merged.docx"))


if __name__ == "__main__":
    unittest.main()
