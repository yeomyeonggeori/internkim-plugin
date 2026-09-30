from pathlib import Path
import tempfile
import unittest
import zipfile

from doc_fixture import run_office, run_office_python


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


if __name__ == "__main__":
    unittest.main()
