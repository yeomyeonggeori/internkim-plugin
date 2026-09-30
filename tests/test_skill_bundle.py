import hashlib
import re
import runpy
from pathlib import Path
import subprocess
import sys
import unittest


SKILLS_PATH = Path(__file__).resolve().parents[1] / "skills"
OFFICE_SCRIPTS_PATH = SKILLS_PATH / "office" / "scripts"
RUNTIME_SKILL_NAMES = ("office", "dataroom")

sys.path.insert(0, str(OFFICE_SCRIPTS_PATH))


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def skill_files():
    return sorted(path for path in SKILLS_PATH.rglob("*") if path.is_file())


def office_command_table():
    return runpy.run_path(str(OFFICE_SCRIPTS_PATH / "office_commands.py"))["COMMANDS"]


class SharedSkillRuntimeTest(unittest.TestCase):
    def test_every_bundled_runtime_is_the_same_file(self):
        digests = {
            skill_name: file_digest(SKILLS_PATH / skill_name / "scripts" / "skill_runtime.py")
            for skill_name in RUNTIME_SKILL_NAMES
        }
        self.assertEqual(len(set(digests.values())), 1, f"skill_runtime.py copies diverged: {digests}")


class OfficeEntryTest(unittest.TestCase):
    def test_every_command_runs_a_bundled_script(self):
        missing_scripts = [command.script for command in office_command_table() if not (OFFICE_SCRIPTS_PATH / command.script).is_file()]
        self.assertEqual(missing_scripts, [])

    def test_help_lists_every_command(self):
        help_text = subprocess.run([sys.executable, str(OFFICE_SCRIPTS_PATH / "office"), "--help"], capture_output=True, text=True, check=True).stdout
        unlisted_commands = [command.name for command in office_command_table() if command.name not in help_text]
        self.assertEqual(unlisted_commands, [])

    def test_every_referenced_command_exists(self):
        command_names = {command.name for command in office_command_table()} | {"python"}
        referenced_names = set()
        for document_path in (SKILLS_PATH / "office").rglob("*.md"):
            text = document_path.read_text(encoding="utf-8")
            for words in re.findall(r"<skill>/scripts/office ([a-z]+)(?: ([a-z]+))?", text):
                referenced_names.add(words[0] if words[0] == "python" else " ".join(words))
        self.assertEqual(referenced_names - command_names, set())


class HostNeutralEnvironmentTest(unittest.TestCase):
    def test_no_skill_names_its_host(self):
        offending_paths = [
            str(path.relative_to(SKILLS_PATH))
            for path in skill_files()
            if b"BLUECLAW_" in path.read_bytes()
        ]
        self.assertEqual(offending_paths, [], "skills must read environment variables no host owns")


if __name__ == "__main__":
    unittest.main()
