from pathlib import Path
import re
import tempfile
import unittest
import zipfile

from doc_fixture import run_office, write_json


def package_part(document_path, part_name):
    with zipfile.ZipFile(document_path) as archive:
        return archive.read(part_name).decode("utf-8")


def style_xml(styles, style_id):
    return re.search(rf'<w:style [^>]*w:styleId="{style_id}".*?</w:style>', styles, re.S).group(0)


class GeneratedDocumentTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)

    def created(self, blocks=None, **specification):
        write_json(self.directory / "spec.json", {"title": "제목", "blocks": blocks or [{"type": "paragraph", "text": "본문"}], **specification})
        envelope = run_office(["doc", "create", "created.docx", "--spec", "spec.json"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope)
        return self.directory / "created.docx"

    def exported(self, markdown):
        (self.directory / "source.md").write_text(markdown, encoding="utf-8")
        envelope = run_office(["doc", "export", "source.md", "--output", "exported.docx"], self.directory)
        self.assertNotEqual(envelope["status"], "error", envelope)
        return self.directory / "exported.docx"


class KoreanLanguageTest(GeneratedDocumentTest):
    def assert_korean_defaults(self, document_path):
        styles = package_part(document_path, "word/styles.xml")
        settings = package_part(document_path, "word/settings.xml")
        self.assertRegex(styles, r'<w:docDefaults>.*<w:lang [^>]*w:eastAsia="ko-KR"')
        self.assertRegex(settings, r'<w:themeFontLang [^>]*w:eastAsia="ko-KR"')
        for style_id in ("Title", "Heading1", "Heading2", "Heading3"):
            fonts = re.search(r"<w:rFonts [^>]*/>", style_xml(styles, style_id)).group(0)
            self.assertIn('w:eastAsia="맑은 고딕"', fonts, style_id)
            self.assertNotIn("Theme=", fonts, style_id)

    def test_created_document_is_korean_by_default(self):
        self.assert_korean_defaults(self.created([{"type": "heading", "text": "개요", "level": 1}]))

    def test_exported_document_is_korean_by_default(self):
        self.assert_korean_defaults(self.exported("# 개요\n\n본문\n"))


if __name__ == "__main__":
    unittest.main()
