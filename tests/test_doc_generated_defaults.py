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


def list_paragraphs(document_path):
    document = package_part(document_path, "word/document.xml")
    return [
        (int(re.search(r'<w:ilvl w:val="(\d+)"', properties).group(1)), int(re.search(r'<w:numId w:val="(\d+)"', properties).group(1)))
        for properties in re.findall(r"<w:numPr>.*?</w:numPr>", document, re.S)
    ]


def number_format(document_path, number_id, level):
    numbering = package_part(document_path, "word/numbering.xml")
    abstract_id = re.search(rf'<w:num w:numId="{number_id}"[^>]*><w:abstractNumId w:val="(\d+)"', numbering).group(1)
    definition = re.search(rf'<w:abstractNum [^>]*w:abstractNumId="{abstract_id}".*?</w:abstractNum>', numbering, re.S).group(0)
    return re.search(rf'<w:lvl w:ilvl="{level}".*?<w:numFmt w:val="(\w+)"', definition, re.S).group(1)


class ListLevelTest(GeneratedDocumentTest):
    def test_exported_nested_lists_use_list_levels_and_each_numbered_list_restarts(self):
        path = self.exported("- 하나\n  - 둘\n    - 셋\n- 넷\n\n문단\n\n1. 가\n   1. 나\n2. 다\n\n문단\n\n1. 라\n")
        paragraphs = list_paragraphs(path)
        self.assertEqual([level for level, _ in paragraphs], [0, 1, 2, 0, 0, 1, 0, 0])
        bullet_list, first_numbered, second_numbered = paragraphs[0][1], paragraphs[4][1], paragraphs[7][1]
        self.assertEqual({number for _, number in paragraphs[:4]}, {bullet_list})
        self.assertEqual({number for _, number in paragraphs[4:7]}, {first_numbered})
        self.assertNotEqual(first_numbered, second_numbered)
        self.assertEqual([number_format(path, bullet_list, level) for level in range(3)], ["bullet"] * 3)
        self.assertEqual([number_format(path, first_numbered, level) for level in range(3)], ["decimal", "lowerLetter", "lowerRoman"])
        self.assertEqual(len(re.findall(r"<w:startOverride", package_part(path, "word/numbering.xml"))), 6)
        self.assertNotRegex(package_part(path, "word/document.xml"), r'w:pStyle w:val="List(Bullet|Number)')

    def test_created_lists_are_real_lists(self):
        path = self.created([
            {"type": "bullets", "items": ["하나", "둘"]},
            {"type": "numbered", "items": ["가", "나"]},
            {"type": "numbered", "items": ["다"]},
        ])
        paragraphs = list_paragraphs(path)
        self.assertEqual([level for level, _ in paragraphs], [0] * 5)
        self.assertEqual(len({number for _, number in paragraphs}), 3)
        self.assertEqual(number_format(path, paragraphs[0][1], 0), "bullet")
        self.assertEqual(number_format(path, paragraphs[2][1], 0), "decimal")


if __name__ == "__main__":
    unittest.main()
