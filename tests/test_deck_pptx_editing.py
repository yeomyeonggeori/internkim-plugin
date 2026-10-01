import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from pptx import Presentation

from deck_fixture import OFFICE_ENTRY, SCRIPTS_PATH
from doc_fixture import write_json
from pptx_edit_fixture import build_korean_deck, sample_photo




def run_office(arguments, directory):
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=directory)
    return json.loads(completed.stdout)


def codes(envelope):
    return [issue["code"] for issue in envelope["issues"]]


class KoreanDeckFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._shared = tempfile.TemporaryDirectory()
        cls.deck_bytes_path = Path(cls._shared.name) / "deck.pptx"
        build_korean_deck(cls.deck_bytes_path)

    @classmethod
    def tearDownClass(cls):
        cls._shared.cleanup()

    def setUp(self):
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.directory = Path(self._temporary_directory.name)
        shutil.copy(self.deck_bytes_path, self.directory / "deck.pptx")
        (self.directory / "photo.png").write_bytes(sample_photo(400, 400))

    def apply(self, operations, *options):
        write_json(self.directory / "ops.json", operations)
        return run_office(["deck", "apply", "deck.pptx", "ops.json", *options], self.directory)

    def read(self, *options, name="deck.pptx"):
        return run_office(["deck", "read", name, *options], self.directory)["details"]

    def slide(self, number, *options):
        return self.read("--slides", str(number), *options)["slides"][0]

    def presentation(self, name="deck.pptx"):
        return Presentation(str(self.directory / name))


class ReadTest(KoreanDeckFixture):
    def test_each_shape_has_index_id_kind_box_and_effective_style(self):
        details = self.read()
        self.assertEqual(details["slideSize"]["w"], 12192000)
        title, card, label, body, picture = self.slide(2)["shapes"]
        self.assertEqual((title["kind"], title["placeholder"]), ("text", "title"))
        self.assertEqual((card["kind"], picture["kind"]), ("shape", "picture"))
        self.assertEqual(label["box"], {"x": 762000, "y": 1981200, "w": 3048000, "h": 457200})
        self.assertEqual(label["percent"]["x"], 6.2)
        self.assertEqual(label["style"]["size"], 24.0)
        self.assertTrue(label["style"]["bold"])
        self.assertEqual(label["style"]["color"], "#FFFFFF")
        self.assertEqual(body["text"], "신규 고객 42곳 확보\n재구매율 68%로 상승")

    def test_detail_names_where_each_inherited_value_comes_from(self):
        title = self.slide(2, "--detail")["shapes"][0]
        run = title["paragraphs"][0]["runs"][0]
        self.assertEqual(run["size"], {"value": 44.0, "from": "master"})
        self.assertEqual(run["font"]["from"], "theme")
        label_run = self.slide(2, "--detail")["shapes"][2]["paragraphs"][0]["runs"][0]
        self.assertEqual(label_run["size"], {"value": 24.0, "from": "run"})

    def test_groups_tables_charts_and_notes_are_described(self):
        table_slide = self.slide(4, "--detail")
        group = table_slide["shapes"][2]
        self.assertEqual([child["index"] for child in group["shapes"]], ["2.0", "2.1"])
        self.assertEqual(group["shapes"][1]["text"], "담당 박예시")
        self.assertEqual(table_slide["shapes"][1]["rows"][1], ["플랫폼", "50억", "58억"])
        self.assertEqual(table_slide["animated"], [str(group["id"])])
        chart = self.slide(3)["shapes"][1]["chart"]
        self.assertEqual(chart["categories"], ["1분기", "2분기", "3분기"])
        self.assertEqual(chart["series"][0], {"name": "매출", "values": [96.0, 110.0, 128.0]})
        self.assertEqual(self.slide(1)["notes"], "인사 후 3분기 요약으로 시작합니다.")


if __name__ == "__main__":
    unittest.main()
