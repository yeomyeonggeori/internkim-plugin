from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILLS_PATH = Path(__file__).resolve().parents[1] / "skills"
sys.path.insert(0, str(SKILLS_PATH / "office" / "scripts"))

import skill_runtime  # noqa: E402


LOCKED_DIRECTORIES = (
    SKILLS_PATH / "office" / "scripts",
    SKILLS_PATH / "office" / "scripts" / "pdf" / "ocr",
    SKILLS_PATH / "dataroom" / "scripts",
)


class SkillDirectoryTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.directory / skill_runtime.REQUIREMENTS_FILE_NAME).write_text("pyyaml\n", encoding="utf-8")
        (self.directory / skill_runtime.LOCK_FILE_NAME).write_text('requires-python = ">=3.9"\n', encoding="utf-8")
        self.environment = skill_runtime.environment_path(self.directory)

    def install_environment(self, lock: bytes) -> None:
        (self.environment / "bin").mkdir(parents=True)
        (self.environment / "bin" / "python").touch()
        (self.environment / skill_runtime.LOCK_FILE_NAME).write_bytes(lock)


class EnsureRequirementsTest(SkillDirectoryTest):
    def test_the_environment_is_the_venv_beside_the_requirements(self):
        self.assertEqual(skill_runtime.environment_path(), Path(skill_runtime.__file__).resolve().parent / ".venv")

    def test_the_environment_itself_needs_nothing_more(self):
        with mock.patch.object(skill_runtime.sys, "prefix", str(self.environment)), \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertTrue(skill_runtime.ensure_requirements(self.directory))
        reexecute.assert_not_called()

    def test_another_python_moves_into_an_environment_installed_from_the_current_lock(self):
        self.install_environment((self.directory / skill_runtime.LOCK_FILE_NAME).read_bytes())
        with mock.patch.object(skill_runtime.sys, "prefix", "/usr"), \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertFalse(skill_runtime.ensure_requirements(self.directory))
        reexecute.assert_called_once_with(self.environment / "bin" / "python")

    def test_an_environment_from_another_lock_is_not_prepared(self):
        self.install_environment(b"an older lock\n")
        self.assertFalse(skill_runtime.is_prepared(self.directory))

    def test_an_unprepared_environment_is_reported_and_nothing_is_installed_or_written(self):
        before = sorted(self.directory.rglob("*"))
        with mock.patch.object(skill_runtime.sys, "prefix", "/usr"), \
                mock.patch.object(skill_runtime.subprocess, "run") as run, \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertFalse(skill_runtime.ensure_requirements(self.directory))
        run.assert_not_called()
        reexecute.assert_not_called()
        self.assertEqual(sorted(self.directory.rglob("*")), before)


class PrepareEnvironmentTest(SkillDirectoryTest):
    def fake_uv(self, command):
        if command[:2] == ["uv", "venv"]:
            (Path(command[-1]) / "bin").mkdir(parents=True)
            (Path(command[-1]) / "bin" / "python").touch()

    def test_setup_builds_the_venv_from_the_lock_once(self):
        with mock.patch.object(skill_runtime, "run_uv", side_effect=self.fake_uv) as uv:
            self.assertTrue(skill_runtime.prepare_environment(self.directory))
            self.assertFalse(skill_runtime.prepare_environment(self.directory))
        commands = [call.args[0][:3] for call in uv.call_args_list]
        self.assertEqual(commands, [["uv", "venv", "--quiet"], ["uv", "pip", "sync"]])
        self.assertEqual(uv.call_args_list[1].args[0][-1], str(self.directory / skill_runtime.LOCK_FILE_NAME))
        self.assertTrue(skill_runtime.is_prepared(self.directory))

    def test_an_environment_left_from_another_lock_is_rebuilt_whole(self):
        self.install_environment(b"an older lock\n")
        leftover = self.environment / "lib" / "removed-package"
        leftover.mkdir(parents=True)
        with mock.patch.object(skill_runtime, "run_uv", side_effect=self.fake_uv):
            self.assertTrue(skill_runtime.prepare_environment(self.directory))
        self.assertFalse(leftover.exists())

    def test_a_missing_lock_or_uv_is_named(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.directory)}):
            with self.assertRaisesRegex(skill_runtime.PreparationFailed, "uv is not on PATH"):
                skill_runtime.prepare_environment(self.directory)
        (self.directory / skill_runtime.LOCK_FILE_NAME).unlink()
        with self.assertRaisesRegex(skill_runtime.PreparationFailed, "pylock.toml is missing"):
            skill_runtime.prepare_environment(self.directory)

    def test_an_unwritable_package_cache_is_left_to_uv(self):
        unwritable = self.directory / "read-only"
        unwritable.mkdir()
        unwritable.chmod(0o500)
        self.addCleanup(unwritable.chmod, 0o700)
        self.assertNotIn("UV_CACHE_DIR", skill_runtime.uv_environment({"UV_CACHE_DIR": str(unwritable / "uv")}))
        self.assertEqual(skill_runtime.uv_environment({"UV_CACHE_DIR": str(self.directory / "uv")})["UV_CACHE_DIR"], str(self.directory / "uv"))


class LockTest(unittest.TestCase):
    def test_every_lock_pins_each_requirement_by_name(self):
        for directory in LOCKED_DIRECTORIES:
            with self.subTest(directory=directory.relative_to(SKILLS_PATH)):
                requirements = {requirement_name(line) for line in (directory / "requirements.txt").read_text(encoding="utf-8").splitlines() if line.strip()}
                locked = {line.split('"')[1].lower() for line in (directory / "pylock.toml").read_text(encoding="utf-8").splitlines() if line.startswith("name = ")}
                self.assertLessEqual(requirements, locked)

    @unittest.skipUnless(shutil.which("uv"), "needs uv")
    def test_every_lock_is_what_its_recorded_command_compiles_from_the_requirements(self):
        for directory in LOCKED_DIRECTORIES:
            with self.subTest(directory=directory.relative_to(SKILLS_PATH)):
                lock = (directory / "pylock.toml").read_text(encoding="utf-8")
                command = recorded_command(lock)
                with tempfile.TemporaryDirectory() as output:
                    compiled = Path(output) / "pylock.toml"
                    subprocess.run([*command[:-1], str(compiled)], cwd=directory, check=True, capture_output=True)
                    self.assertEqual(lock_body(compiled.read_text(encoding="utf-8")), lock_body(lock), f"{directory / 'pylock.toml'} is stale; rerun: {' '.join(command)}")


def requirement_name(line: str) -> str:
    return line.split(";")[0].split("==")[0].split(">=")[0].strip().lower().replace("_", "-")


def recorded_command(lock: str) -> list[str]:
    command = lock.splitlines()[1].lstrip("# ").split()
    if command[-2] != "-o":
        raise AssertionError(f"the lock header does not end with its output: {command}")
    return command


def lock_body(lock: str) -> str:
    return "\n".join(line for line in lock.splitlines() if not line.startswith("#"))


if __name__ == "__main__":
    unittest.main()
