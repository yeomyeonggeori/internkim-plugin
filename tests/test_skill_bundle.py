import ast
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPOSITORY_PATH = Path(__file__).resolve().parents[1]
SKILLS_PATH = REPOSITORY_PATH / "skills"
OFFICE_SCRIPTS_PATH = SKILLS_PATH / "office" / "scripts"
RUNTIME_SKILL_NAMES = ("office", "dataroom")
MARKETPLACE_PATHS = (
    REPOSITORY_PATH / ".claude-plugin" / "marketplace.json",
    REPOSITORY_PATH / ".agents" / "plugins" / "marketplace.json",
)

sys.path.insert(0, str(OFFICE_SCRIPTS_PATH))

from core.office_commands import COMMANDS, FORMATS  # noqa: E402


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def skill_files():
    return sorted(path for path in SKILLS_PATH.rglob("*") if path.is_file())


def office_command_table():
    return COMMANDS


def office_format_names():
    return {office_format.name for office_format in FORMATS}


def module_path(module: str) -> Path:
    return OFFICE_SCRIPTS_PATH.joinpath(*module.split(".")).with_suffix(".py")


class SharedSkillRuntimeTest(unittest.TestCase):
    def test_every_bundled_runtime_is_the_same_file(self):
        digests = {
            skill_name: file_digest(SKILLS_PATH / skill_name / "scripts" / "skill_runtime.py")
            for skill_name in RUNTIME_SKILL_NAMES
        }
        self.assertEqual(len(set(digests.values())), 1, f"skill_runtime.py copies diverged: {digests}")


class OfficeEntryTest(unittest.TestCase):
    def test_every_command_runs_a_bundled_module(self):
        missing_modules = [command.module for command in office_command_table() if not module_path(command.module).is_file()]
        self.assertEqual(missing_modules, [])

    def test_help_lists_every_command(self):
        help_text = subprocess.run([sys.executable, str(OFFICE_SCRIPTS_PATH / "office"), "--help"], capture_output=True, text=True, check=True).stdout
        unlisted_commands = [command.name for command in office_command_table() if command.name not in help_text]
        self.assertEqual(unlisted_commands, [])

    def test_every_referenced_command_exists(self):
        command_names = {command.name for command in office_command_table()} | {"python", "guide"}
        command_names |= {f"guide {format_name}" for format_name in office_format_names()}
        referenced_names = set()
        for document_path in (SKILLS_PATH / "office").rglob("*.md"):
            text = document_path.read_text(encoding="utf-8")
            for words in re.findall(r"<skill>/scripts/office ([a-z]+)(?: ([a-z]+))?", text):
                referenced_names.add(words[0] if words[0] == "python" or not words[1] else " ".join(words))
        self.assertEqual(referenced_names - command_names, set())

    def test_route_table_lists_every_command(self):
        skill_text = (SKILLS_PATH / "office" / "SKILL.md").read_text(encoding="utf-8")
        route_table = skill_text.split("## Route the work")[1].split("\n## ")[0]
        listed_names = set(re.findall(r"`([a-z]+(?: [a-z]+)?)`", route_table))
        command_names = {command.name for command in office_command_table()}
        self.assertEqual(command_names ^ listed_names, set())


DECK_SOURCE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>예시</title></head><body data-theme="corporate">
<section data-layout="cover"><h1>매출이 6% 늘었습니다</h1><p class="meta">이샘플</p></section>
</body></html>"""
QUOTE = {
    "title": "견 적 서",
    "items": {
        "headers": ["품명", "수량", "단가", "공급가액"],
        "rows": [["의자", "10", "50,000", "500,000"]],
        "totals": [{"label": "공급가액 합계", "value": "500,000원"}, {"label": "부가세", "value": "50,000원"}, {"label": "총 합계", "value": "550,000원"}],
    },
}


def prepare_deck_restore(directory):
    (directory / "slides.html").write_text(DECK_SOURCE, encoding="utf-8")
    subprocess.run([sys.executable, str(OFFICE_SCRIPTS_PATH / "office"), "deck", "build", "--format", "html", "--name", "deck"], capture_output=True, check=True, cwd=directory)
    return ["deck", "restore", "build/deck.html", "restored.html"]


def prepare_paperwork_check(directory):
    (directory / "quote.json").write_text(json.dumps(QUOTE, ensure_ascii=False), encoding="utf-8")
    return ["paperwork", "check", "quote.json"]


PACKAGE_FREE_CASES = {
    "deck restore": prepare_deck_restore,
    "paperwork check": prepare_paperwork_check,
}


def bare_interpreter(directory):
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(directory)], check=True)
    return directory / "bin" / "python"


class PackageFreeCommandTest(unittest.TestCase):
    def test_every_command_declared_package_free_has_a_case(self):
        self.assertEqual(set(PACKAGE_FREE_CASES), {command.name for command in office_command_table() if not command.needs_packages})

    def test_each_package_free_command_runs_on_an_interpreter_without_the_skill_packages_or_a_font_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            interpreter = bare_interpreter(Path(directory) / "bare")
            environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"} | {"XDG_CACHE_HOME": str(Path(directory) / "empty-cache")}
            for name, prepare in PACKAGE_FREE_CASES.items():
                with self.subTest(command=name):
                    working_directory = Path(directory) / name.replace(" ", "-")
                    working_directory.mkdir()
                    arguments = prepare(working_directory)
                    completed = subprocess.run([str(interpreter), str(OFFICE_SCRIPTS_PATH / "office"), *arguments], capture_output=True, text=True, cwd=working_directory, env=environment)
                    self.assertNotIn("ModuleNotFoundError", completed.stderr)
                    self.assertEqual(json.loads(completed.stdout)["status"], "ok", completed.stdout)


class OldPythonTest(unittest.TestCase):
    def test_modern_annotations_are_never_evaluated_at_definition_time(self):
        offending_paths = [
            str(path.relative_to(SKILLS_PATH))
            for path in (SKILLS_PATH / "office" / "scripts").rglob("*.py")
            if uses_modern_annotations(path) and not postpones_annotations(path)
        ]
        self.assertEqual(offending_paths, [], "Python 3.9, the macOS Command Line Tools interpreter, cannot evaluate list[str] or X | None")


def annotation_nodes(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.annotation:
            yield node.annotation
        if isinstance(node, ast.FunctionDef) and node.returns:
            yield node.returns
        if isinstance(node, ast.AnnAssign):
            yield node.annotation


def uses_modern_annotations(path):
    for annotation in annotation_nodes(ast.parse(path.read_text(encoding="utf-8"))):
        for node in ast.walk(annotation):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                return True
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in {"list", "dict", "set", "tuple"}:
                return True
    return False


def postpones_annotations(path):
    return "from __future__ import annotations" in path.read_text(encoding="utf-8")


class HostNeutralEnvironmentTest(unittest.TestCase):
    def test_no_skill_names_its_host(self):
        offending_paths = [
            str(path.relative_to(SKILLS_PATH))
            for path in skill_files()
            if b"BLUECLAW_" in path.read_bytes()
        ]
        self.assertEqual(offending_paths, [], "skills must read environment variables no host owns")


def read_json(path):
    return json.loads(path.read_text())


class MarketplaceCatalogTest(unittest.TestCase):
    def test_every_catalog_lists_only_this_plugin(self):
        plugin_name = read_json(REPOSITORY_PATH / "plugin.json")["name"]
        for path in MARKETPLACE_PATHS:
            listed_names = [entry["name"] for entry in read_json(path)["plugins"]]
            self.assertEqual(listed_names, [plugin_name], f"{path.relative_to(REPOSITORY_PATH)} lists {listed_names}")

    def test_a_copied_description_matches_the_manifest(self):
        manifest_description = read_json(REPOSITORY_PATH / "plugin.json")["description"]
        for path in MARKETPLACE_PATHS:
            for entry in read_json(path)["plugins"]:
                if "description" in entry:
                    self.assertEqual(entry["description"], manifest_description, f"{path.relative_to(REPOSITORY_PATH)} description drifted")


if __name__ == "__main__":
    unittest.main()
