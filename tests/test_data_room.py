import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL_DIRECTORY = Path(__file__).resolve().parents[1] / "skills" / "dataroom"
SCRIPT_DIRECTORY = SKILL_DIRECTORY / "scripts"
DATA_ROOM = SCRIPT_DIRECTORY / "dataroom.py"
SETUP = f"python3 {SCRIPT_DIRECTORY / 'skill_runtime.py'} setup"


def run(*arguments) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(DATA_ROOM), *map(str, arguments)], capture_output=True, text=True)


def is_prepared() -> bool:
    return run("--help").returncode == 0


@unittest.skipUnless(is_prepared(), f"the data room's Python environment is not prepared; run {SETUP}")
class DataRoomTreeTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = self.directory / "room"
        self.assertEqual(run("init", self.root, "--slug", "sample").returncode, 0)

    def file(self, name: str, category: str) -> subprocess.CompletedProcess:
        original = self.directory / name
        original.write_bytes(b"Revenue 100, expenses 80.\n")
        return run("ingest", self.root, original, "--category", category, "--summary", "Revenue 100 and expenses 80.")

    def test_init_writes_the_standard_template(self):
        template = json.loads((SKILL_DIRECTORY / "assets" / "template.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((self.root / "company.json").read_text(encoding="utf-8"))["dataroom"], template)

    def test_filing_preserves_the_original_and_generates_a_text_preview(self):
        completed = self.file("sample.txt", "FS")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        original = (self.directory / "sample.txt").read_bytes()
        filed = next((self.root / "F-finance" / "FS-statements").glob("*.txt"))
        self.assertEqual(filed.read_bytes(), original)
        preview = filed.parent / ".derived" / hashlib.sha256(original).hexdigest() / "content.txt"
        self.assertEqual(preview.read_bytes(), original)
        checked = run("check", self.root)
        self.assertEqual((checked.returncode, checked.stdout.strip()), (0, "ok 1 documents"), checked.stdout)

    def test_filing_destinations_follow_whether_the_category_has_children(self):
        refused = self.file("parent.txt", "F")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("no filing category named F", refused.stderr)
        self.assertIn("filed X-inbox/", self.file("inbox.txt", "X").stdout)
        company_path = self.root / "company.json"
        company = json.loads(company_path.read_text(encoding="utf-8"))
        company["dataroom"]["categories"] = [category for category in company["dataroom"]["categories"] if category["parent"] != "F"]
        company_path.write_text(json.dumps(company), encoding="utf-8")
        self.assertIn("filed F-finance/", self.file("leaf.txt", "F").stdout)


if __name__ == "__main__":
    unittest.main()
