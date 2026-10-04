import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from render_fixture import can_render
from skill_copy_fixture import PREPARED_LOCATIONS, copy_skill


DECK_SOURCE = Path(__file__).resolve().parent / "fixtures" / "deck-kit" / "quarterly-review"
REPORT = "# 분기 보고서\n\n3분기 매출은 **128억 원**입니다.\n\n| 지점 | 매출 |\n| --- | --- |\n| 서울 | 1,200 |\n"


def run(office_entry: Path, arguments: list[str], directory: Path, environment: dict[str, str]) -> tuple[subprocess.CompletedProcess, dict]:
    completed = subprocess.run([sys.executable, str(office_entry), *arguments], capture_output=True, text=True, cwd=directory, env=environment)
    return completed, json.loads(completed.stdout)


def tree_state(root: Path) -> dict[str, tuple[int, int]]:
    files = (path for path in root.rglob("*") if not path.is_dir() and "__pycache__" not in path.parts)
    return {str(path.relative_to(root)): (path.lstat().st_size, path.lstat().st_mtime_ns) for path in files}


def set_writable(root: Path, writable: bool) -> None:
    for path in [root, *root.rglob("*")]:
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IWUSR if writable else mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def requester_environment(home: Path) -> dict[str, str]:
    environment = {**os.environ, "HOME": str(home), "XDG_CACHE_HOME": str(home / "cache"), "UV_OFFLINE": "1", "npm_config_offline": "true"}
    environment.pop("UV_CACHE_DIR", None)
    return environment


class WithoutSetupTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.work = self.root / "work"
        self.work.mkdir()
        self.environment = requester_environment(self.root / "home")

    def test_a_command_before_setup_names_setup_and_writes_nothing(self):
        office_entry = copy_skill(self.root / "office")
        before = tree_state(self.root / "office")
        for arguments in (["create", "표.xlsx", "표.csv"], ["python", "-c", "print(1)"]):
            with self.subTest(arguments=arguments[:2]):
                completed, envelope = run(office_entry, arguments, self.work, self.environment)
                self.assertEqual(completed.returncode, 1)
                self.assertEqual([issue["code"] for issue in envelope["issues"]], ["DEPENDENCIES_UNAVAILABLE"])
                self.assertIn("office setup", envelope["issues"][0]["suggestion"])
        self.assertEqual(list(self.work.iterdir()), [])
        self.assertEqual(tree_state(self.root / "office"), before)
        self.assertFalse((self.root / "home").exists())

    def test_a_drawing_command_without_prepared_renderer_packages_names_setup(self):
        office_entry = copy_skill(self.root / "office", ("python environment",))
        (self.work / "보고서.md").write_text(REPORT, encoding="utf-8")
        completed, envelope = run(office_entry, ["create", "보고서.pdf", "보고서.md"], self.work, self.environment)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["RENDERER_UNAVAILABLE"])
        self.assertIn("office setup", envelope["issues"][0]["message"] + envelope["issues"][0]["suggestion"])
        self.assertEqual([path.name for path in self.work.iterdir()], ["보고서.md"])

    def test_setup_without_uv_names_the_piece_it_could_not_prepare(self):
        office_entry = copy_skill(self.root / "office")
        environment = {**self.environment, "PATH": str(Path(sys.executable).parent)}
        completed, envelope = run(office_entry, ["setup"], self.work, environment)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("SETUP_FAILED", "python environment")])
        self.assertIn("uv is not on PATH", envelope["issues"][0]["message"])
        self.assertEqual(envelope["details"]["steps"], [])


@unittest.skipUnless(can_render() and shutil.which("uv"), "needs uv, and bun or node 18 or newer")
class PreparedSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(cls.temporary_directory.name)
        cls.skill = root / "office"
        cls.office_entry = copy_skill(cls.skill, ("ocr engine",))
        cls.setup_completed, cls.setup_envelope = run(cls.office_entry, ["setup"], root, dict(os.environ))
        cls.requester = root / "requester"
        cls.work = cls.requester / "work"
        cls.work.mkdir(parents=True)

    @classmethod
    def tearDownClass(cls):
        set_writable(cls.skill, True)
        cls.temporary_directory.cleanup()

    def setUp(self):
        self.assertEqual(self.setup_completed.returncode, 0, self.setup_envelope)
        set_writable(self.skill, False)
        self.addCleanup(set_writable, self.skill, True)
        self.before = tree_state(self.skill)

    def test_setup_lists_each_piece_where_the_skill_reads_it(self):
        steps = self.setup_envelope["details"]["steps"]
        self.assertEqual([step["name"] for step in steps], ["python environment", "renderer packages", "ocr engine"])
        self.assertEqual([step["state"] for step in steps], ["prepared", "prepared", "found"])
        self.assertEqual([Path(step["path"]) for step in steps], [self.skill.resolve() / PREPARED_LOCATIONS[step["name"]] for step in steps])

    def test_a_second_setup_finds_everything_and_changes_nothing(self):
        completed, envelope = run(self.office_entry, ["setup"], self.work, requester_environment(self.requester))
        self.assertEqual(completed.returncode, 0, envelope)
        self.assertEqual({step["state"] for step in envelope["details"]["steps"]}, {"found"})
        self.assertEqual(tree_state(self.skill), self.before)

    def test_a_requester_builds_a_deck_a_sheet_and_a_document_from_the_read_only_skill_offline(self):
        shutil.copytree(DECK_SOURCE, self.work / "deck")
        (self.work / "보고서.md").write_text(REPORT, encoding="utf-8")
        (self.work / "실적.csv").write_text("지역,매출\n서울,1200\n", encoding="utf-8")
        (self.work / "실적.workbook.json").write_text('{"kind": "workbook", "tables": [{"name": "실적", "columns": [{"name": "지역"}, {"name": "매출", "type": "quantity"}], "csvPath": "실적.csv"}]}', encoding="utf-8")
        commands = (
            (self.work / "deck", ["create", "build/deck.pdf", "slides.html"]),
            (self.work, ["create", "실적.xlsx", "실적.workbook.json"]),
            (self.work, ["create", "보고서.pdf", "보고서.md"]),
            (self.work, ["create", "보고서.docx", "보고서.md"]),
        )
        for directory, arguments in commands:
            with self.subTest(arguments=arguments[:2]):
                completed, envelope = run(self.office_entry, arguments, directory, requester_environment(self.requester))
                self.assertNotEqual(envelope["status"], "error", envelope["issues"])
        self.assertEqual(tree_state(self.skill), self.before)
        self.assertFalse((self.requester / "cache").exists())


if __name__ == "__main__":
    unittest.main()
