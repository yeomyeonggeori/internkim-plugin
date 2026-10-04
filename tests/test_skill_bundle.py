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

from free_deck_fixture import write_free_deck

from bundle_fixture import bundled_files


REPOSITORY_PATH = Path(__file__).resolve().parents[1]
SKILLS_PATH = REPOSITORY_PATH / "skills"
OFFICE_SCRIPTS_PATH = SKILLS_PATH / "office" / "scripts"
RUNTIME_SKILL_NAMES = ("office", "dataroom")
MARKETPLACE_PATHS = (
    REPOSITORY_PATH / ".claude-plugin" / "marketplace.json",
    REPOSITORY_PATH / ".agents" / "plugins" / "marketplace.json",
)

sys.path.insert(0, str(OFFICE_SCRIPTS_PATH))

from core.office_commands import CONVERSIONS, ROUTES, VERBS  # noqa: E402


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def skill_files():
    return bundled_files(SKILLS_PATH)


def package_free_names():
    routes = {route.name for route in ROUTES if not route.needs_packages}
    conversions = {f"convert {conversion.source} to {conversion.target}" for conversion in CONVERSIONS if not conversion.needs_packages}
    return routes | conversions


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
    def test_every_route_runs_a_bundled_module(self):
        modules = {route.module for route in ROUTES} | {conversion.module for conversion in CONVERSIONS}
        self.assertEqual(sorted(module for module in modules if not module_path(module).is_file()), [])

    def test_help_lists_every_verb(self):
        help_text = subprocess.run([sys.executable, str(OFFICE_SCRIPTS_PATH / "office"), "--help"], capture_output=True, text=True, check=True).stdout
        self.assertEqual([verb.name for verb in VERBS if f"\n{verb.name} <" not in help_text], [])

    def test_every_verb_is_routed_or_documented_and_the_route_table_names_only_verbs(self):
        skill_text = (SKILLS_PATH / "office" / "SKILL.md").read_text(encoding="utf-8")
        route_table = skill_text.split("## Route the work")[1].split("\n## ")[0]
        listed = {command.removeprefix("office ").split()[0] for command in re.findall(r"`([a-z][^`]*)`", route_table) if not command.startswith("references/")}
        verb_names = {verb.name for verb in VERBS} | {"guide"}
        self.assertEqual(listed - verb_names, set())
        documents = "\n".join(path.read_text(encoding="utf-8") for path in bundled_files(SKILLS_PATH / "office", "*.md"))
        self.assertEqual([verb.name for verb in VERBS if f"office {verb.name}" not in documents and verb.name not in listed], [])


DECK_SECTIONS = ["<h1>매출이 6% 늘었습니다</h1><p>이샘플</p>"]
QUOTE = {
    "form": "kr/quote",
    "title": "견 적 서",
    "items": {
        "headers": ["품명", "수량", "단가", "공급가액"],
        "rows": [["의자", "10", "50,000", "500,000"]],
        "totals": [{"label": "공급가액 합계", "value": "500,000원"}, {"label": "부가세", "value": "50,000원"}, {"label": "총 합계", "value": "550,000원"}],
    },
}


def prepare_deck_restore(directory):
    write_free_deck(directory, DECK_SECTIONS)
    subprocess.run([sys.executable, str(OFFICE_SCRIPTS_PATH / "office"), "create", "build/deck.html", "slides.html"], capture_output=True, check=True, cwd=directory)
    return ["convert", "build/deck.html", "restored.html"]


def prepare_paperwork_check(directory):
    (directory / "quote.json").write_text(json.dumps(QUOTE, ensure_ascii=False), encoding="utf-8")
    return ["check", "quote.json"]


PACKAGE_FREE_CASES = {
    "convert html to html": prepare_deck_restore,
    "check form": prepare_paperwork_check,
}


def bare_interpreter(directory):
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(directory)], check=True)
    return directory / "bin" / "python"


class PackageFreeCommandTest(unittest.TestCase):
    def test_every_command_declared_package_free_has_a_case(self):
        self.assertEqual(set(PACKAGE_FREE_CASES), package_free_names())

    def test_each_package_free_command_runs_on_an_interpreter_without_the_skill_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            interpreter = bare_interpreter(Path(directory) / "bare")
            environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
            for name, prepare in PACKAGE_FREE_CASES.items():
                with self.subTest(command=name):
                    working_directory = Path(directory) / name.replace(" ", "-")
                    working_directory.mkdir()
                    arguments = prepare(working_directory)
                    completed = subprocess.run([str(interpreter), str(OFFICE_SCRIPTS_PATH / "office"), *arguments], capture_output=True, text=True, cwd=working_directory, env=environment)
                    self.assertNotIn("ModuleNotFoundError", completed.stderr)
                    self.assertEqual(json.loads(completed.stdout)["status"], "ok", completed.stdout)


OWNED_LITERALS = {
    "1048576": "core/excel_limits.py",
    "16384": "core/excel_limits.py",
    "12700": "core/units.py",
    "914400": "core/units.py",
}


class OwnedLiteralTest(unittest.TestCase):
    def test_excel_limits_and_emu_sizes_are_written_only_where_they_are_owned(self):
        scripts = bundled_files(OFFICE_SCRIPTS_PATH, "*.py")
        written_elsewhere = sorted(
            (literal, str(path.relative_to(OFFICE_SCRIPTS_PATH)))
            for path in scripts
            for literal, owner in OWNED_LITERALS.items()
            if str(path.relative_to(OFFICE_SCRIPTS_PATH)) != owner and re.search(rf"(?<![0-9.]){literal}(?![0-9])", path.read_text(encoding="utf-8"))
        )
        self.assertEqual(written_elsewhere, [])


class OldPythonTest(unittest.TestCase):
    def test_modern_annotations_are_never_evaluated_at_definition_time(self):
        offending_paths = [
            str(path.relative_to(SKILLS_PATH))
            for path in bundled_files(OFFICE_SCRIPTS_PATH, "*.py")
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
