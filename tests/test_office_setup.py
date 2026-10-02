import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, SCRIPTS_PATH
from render_fixture import can_render
from skill_runtime import dependency_environment_path, safe_name, skill_cache_path, usable_uv_cache_path


SKILLS_PATH = SCRIPTS_PATH.parents[1]
DECK_SOURCE = Path(__file__).resolve().parent / "fixtures" / "deck-kit" / "quarterly-review"
REPORT = "# 분기 보고서\n\n3분기 매출은 **128억 원**입니다.\n\n| 지점 | 매출 |\n| --- | --- |\n| 서울 | 1,200 |\n"


def run(office_entry: Path, arguments: list[str], directory: Path, environment: dict[str, str]) -> tuple[subprocess.CompletedProcess, dict]:
    completed = subprocess.run([sys.executable, str(office_entry), *arguments], capture_output=True, text=True, cwd=directory, env=environment)
    return completed, json.loads(completed.stdout)


def tree_state(root: Path) -> dict[str, tuple[int, int]]:
    return {str(path.relative_to(root)): (path.lstat().st_size, path.lstat().st_mtime_ns) for path in root.rglob("*")}


def set_writable(root: Path, writable: bool) -> None:
    for path in [root, *root.rglob("*")]:
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IWUSR if writable else mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


class WithoutSetupTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.work = self.root / "work"
        self.cache = self.root / "cache"
        self.work.mkdir()
        self.cache.mkdir()
        self.environment = {**os.environ, "HOME": str(self.root), "XDG_CACHE_HOME": str(self.cache)}

    def test_a_command_before_setup_names_setup_and_writes_nothing(self):
        for arguments in (["sheet", "create", "표.xlsx", "--row", "a,b"], ["python", "-c", "print(1)"]):
            with self.subTest(arguments=arguments[:2]):
                completed, envelope = run(OFFICE_ENTRY, arguments, self.work, self.environment)
                self.assertEqual(completed.returncode, 1)
                self.assertEqual([issue["code"] for issue in envelope["issues"]], ["DEPENDENCIES_UNAVAILABLE"])
                self.assertIn("office setup", envelope["issues"][0]["suggestion"])
        self.assertEqual(list(self.work.iterdir()), [])
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_a_drawing_command_without_prepared_renderer_packages_names_setup(self):
        office_environment = skill_cache_path(self.environment) / "environments" / safe_name("office")
        office_environment.parent.mkdir(parents=True)
        office_environment.symlink_to(dependency_environment_path("office"))
        (self.work / "보고서.md").write_text(REPORT, encoding="utf-8")
        completed, envelope = run(OFFICE_ENTRY, ["doc", "export", "보고서.md", "--output", "보고서.pdf"], self.work, self.environment)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["RENDERER_UNAVAILABLE"])
        self.assertIn("office setup", envelope["issues"][0]["message"] + envelope["issues"][0]["suggestion"])
        self.assertEqual([path.name for path in self.work.iterdir()], ["보고서.md"])

    def test_setup_without_uv_names_the_piece_it_could_not_prepare(self):
        environment = {**self.environment, "PATH": str(Path(sys.executable).parent)}
        completed, envelope = run(OFFICE_ENTRY, ["setup"], self.work, environment)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("SETUP_FAILED", "python environment")])
        self.assertIn("uv is not on PATH", envelope["issues"][0]["message"])
        self.assertEqual(envelope["details"]["steps"], [])


@unittest.skipUnless(can_render() and shutil.which("uv"), "needs uv, and bun or node 18 or newer")
class PreparedTreeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(cls.temporary_directory.name)
        cls.skills = root / "skills"
        shutil.copytree(SKILLS_PATH / "office", cls.skills / "office", ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
        cls.prepared = cls.skills / ".prepared"
        cls.office_entry = cls.skills / "office" / "scripts" / "office"
        setup_environment = {**os.environ, "XDG_CACHE_HOME": str(cls.prepared), "UV_CACHE_DIR": str(usable_uv_cache_path(os.environ))}
        cls.setup_completed, cls.setup_envelope = run(cls.office_entry, ["setup"], root, setup_environment)
        cls.requester = root / "requester"
        cls.work = cls.requester / "work"
        cls.work.mkdir(parents=True)
        cls.requester_environment = {**os.environ, "HOME": str(cls.requester), "XDG_CACHE_HOME": str(cls.requester / "cache"), "UV_OFFLINE": "1"}
        cls.requester_environment.pop("UV_CACHE_DIR", None)

    @classmethod
    def tearDownClass(cls):
        if cls.prepared.exists():
            set_writable(cls.prepared, True)
        cls.temporary_directory.cleanup()

    def setUp(self):
        self.assertEqual(self.setup_completed.returncode, 0, self.setup_envelope)
        set_writable(self.prepared, False)
        self.addCleanup(set_writable, self.prepared, True)
        self.before = tree_state(self.prepared)

    def test_setup_lists_what_it_prepared_under_the_prepared_directory(self):
        steps = self.setup_envelope["details"]["steps"]
        self.assertEqual([step["name"] for step in steps], ["python environment", "renderer packages", "fonts"])
        self.assertTrue(all(Path(step["path"]).is_relative_to(self.prepared.resolve()) for step in steps))

    def test_a_second_setup_finds_everything_and_changes_nothing(self):
        completed, envelope = run(self.office_entry, ["setup"], self.work, {**self.requester_environment, "XDG_CACHE_HOME": str(self.prepared)})
        self.assertEqual(completed.returncode, 0, envelope)
        self.assertEqual({step["state"] for step in envelope["details"]["steps"]}, {"found"})
        self.assertEqual(tree_state(self.prepared), self.before)

    def test_a_requester_builds_a_deck_a_sheet_and_a_document_from_the_read_only_tree(self):
        shutil.copytree(DECK_SOURCE, self.work / "deck")
        (self.work / "보고서.md").write_text(REPORT, encoding="utf-8")
        commands = (
            (self.work / "deck", ["deck", "build", "--format", "pdf"]),
            (self.work, ["sheet", "create", "실적.xlsx", "--row", "지역,매출", "--row", "서울,1200"]),
            (self.work, ["doc", "export", "보고서.md", "--output", "보고서.pdf"]),
            (self.work, ["doc", "export", "보고서.md", "--output", "보고서.docx"]),
        )
        for directory, arguments in commands:
            with self.subTest(arguments=arguments[:2]):
                completed, envelope = run(self.office_entry, arguments, directory, self.requester_environment)
                self.assertNotEqual(envelope["status"], "error", envelope["issues"])
        self.assertEqual(tree_state(self.prepared), self.before)
        requester_cache = self.requester / "cache"
        self.assertFalse((requester_cache / "internkim-skills" / "environments").exists())
        self.assertEqual(list(requester_cache.rglob("node_modules")), [])


if __name__ == "__main__":
    unittest.main()
