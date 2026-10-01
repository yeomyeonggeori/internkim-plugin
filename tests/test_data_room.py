import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIRECTORY = Path(__file__).resolve().parents[1] / "skills/dataroom/scripts"
sys.path.insert(0, str(SCRIPT_DIRECTORY))
SPECIFICATION = importlib.util.spec_from_file_location("dataroom", SCRIPT_DIRECTORY / "dataroom.py")
DATA_ROOM = importlib.util.module_from_spec(SPECIFICATION)
SPECIFICATION.loader.exec_module(DATA_ROOM)


class DataRoomTreeTest(unittest.TestCase):
    def test_filing_preserves_the_original_and_generates_a_text_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            root = directory / "room"
            original = directory / "sample.txt"
            original.write_bytes(b"Revenue 100, expenses 80.\n")
            arguments = DATA_ROOM.build_parser().parse_args(["init", str(root), "--slug", "sample"])
            arguments.handler(arguments)
            arguments = DATA_ROOM.build_parser().parse_args([
                "ingest", str(root), str(original), "--category", "FS", "--summary", "Revenue 100 and expenses 80."
            ])
            arguments.handler(arguments)
            filed = next((root / "F-finance/FS-statements").glob("*.txt"))
            self.assertEqual(filed.read_bytes(), original.read_bytes())
            metadata = DATA_ROOM.load_frontmatter(DATA_ROOM.sidecar_path(filed))
            self.assertEqual(metadata["categoryCode"], "FS")
            preview = filed.parent / ".derived" / metadata["sha256"] / "content.txt"
            self.assertEqual(preview.read_bytes(), original.read_bytes())
            self.assertEqual(DATA_ROOM.run_check(argparse.Namespace(directory=str(root))), 0)
            template = json.loads((root / "company.json").read_text())["dataroom"]
            self.assertEqual(template, DATA_ROOM.TEMPLATE)

    def test_filing_destinations_follow_whether_the_category_has_children(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments = DATA_ROOM.build_parser().parse_args(["init", str(root), "--slug", "sample"])
            arguments.handler(arguments)
            with self.assertRaises(DATA_ROOM.Failure):
                DATA_ROOM.resolve_category(root, "F")
            self.assertEqual(DATA_ROOM.resolve_category(root, "X"), "X-inbox")
            company = DATA_ROOM.load_company(root)
            company["dataroom"]["categories"] = [category for category in company["dataroom"]["categories"]
                                                  if category["parent"] != "F"]
            DATA_ROOM.write_json(root / "company.json", company)
            self.assertEqual(DATA_ROOM.resolve_category(root, "F"), "F-finance")


if __name__ == "__main__":
    unittest.main()
