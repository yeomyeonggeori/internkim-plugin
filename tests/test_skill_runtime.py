from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))

import skill_runtime  # noqa: E402


class SkillCacheTest(unittest.TestCase):
    def setUp(self):
        self.cache_directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.cache_directory)}))
        self.enterContext(mock.patch.object(skill_runtime, "PREPARED_CACHE_HOME", self.cache_directory / "absent" / ".prepared"))
        self.environment_path = skill_runtime.dependency_environment_path("office")

    def prepare_environment(self, environment_path: Path) -> None:
        (environment_path / "bin").mkdir(parents=True)
        (environment_path / "bin" / "python").touch()
        skill_runtime.requirements_marker(environment_path, skill_runtime.requirements_file()).touch()


class EnsureRequirementsTest(SkillCacheTest):
    def test_the_environment_itself_needs_nothing_more(self):
        with mock.patch.object(skill_runtime.sys, "prefix", str(self.environment_path)), \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertTrue(skill_runtime.ensure_requirements("office"))
        reexecute.assert_not_called()

    def test_an_environment_reached_through_a_symlinked_cache_is_still_the_one_running(self):
        linked_cache = Path(self.enterContext(tempfile.TemporaryDirectory())) / "cache"
        linked_cache.symlink_to(self.cache_directory)
        self.environment_path.mkdir(parents=True)
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(linked_cache)}), \
                mock.patch.object(skill_runtime.sys, "prefix", str(self.environment_path.resolve())), \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertTrue(skill_runtime.ensure_requirements("office"))
        reexecute.assert_not_called()

    def test_another_python_moves_into_a_prepared_environment(self):
        self.prepare_environment(self.environment_path)
        with mock.patch.object(skill_runtime.sys, "prefix", "/usr"), \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertFalse(skill_runtime.ensure_requirements("office"))
        reexecute.assert_called_once_with(self.environment_path / "bin" / "python")

    def test_an_unprepared_environment_is_reported_and_nothing_is_installed(self):
        with mock.patch.object(skill_runtime.sys, "prefix", "/usr"), \
                mock.patch.object(skill_runtime.subprocess, "run") as run, \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertFalse(skill_runtime.ensure_requirements("office"))
        run.assert_not_called()
        reexecute.assert_not_called()
        self.assertEqual(list(self.cache_directory.iterdir()), [])

    def test_an_environment_prepared_for_other_requirements_is_not_prepared(self):
        (self.environment_path / "bin").mkdir(parents=True)
        (self.environment_path / "bin" / "python").touch()
        (self.environment_path / ".requirements-0000000000000000.installed").touch()
        self.assertFalse(skill_runtime.is_prepared(self.environment_path, skill_runtime.requirements_file()))


class PrepareRequirementsTest(SkillCacheTest):
    def test_setup_creates_and_installs_once(self):
        def create(python_path, environment_path):
            (environment_path / "bin").mkdir(parents=True)
            python_path.touch()

        with mock.patch.object(skill_runtime, "create_dependency_environment", side_effect=create) as created, \
                mock.patch.object(skill_runtime, "install_requirements") as installed:
            self.assertTrue(skill_runtime.prepare_requirements("office"))
            self.assertFalse(skill_runtime.prepare_requirements("office"))
        created.assert_called_once()
        installed.assert_called_once()

    def test_a_missing_uv_is_named(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.cache_directory)}):
            with self.assertRaisesRegex(skill_runtime.PreparationFailed, "uv is not on PATH"):
                skill_runtime.prepare_requirements("office")

    def test_an_unwritable_package_cache_falls_back_to_the_skill_cache(self):
        unwritable = self.cache_directory / "read-only"
        unwritable.mkdir()
        unwritable.chmod(0o500)
        self.addCleanup(unwritable.chmod, 0o700)
        chosen = skill_runtime.usable_uv_cache_path({"UV_CACHE_DIR": str(unwritable / "uv"), "XDG_CACHE_HOME": str(self.cache_directory)})
        self.assertEqual(chosen, self.cache_directory / skill_runtime.SKILL_CACHE_DIRECTORY_NAME / "uv")


class PreparedCacheHomeTest(unittest.TestCase):
    def test_the_prepared_directory_beside_the_skills_is_read_and_the_requester_cache_is_written(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        prepared = root / "skills" / ".prepared"
        prepared.mkdir(parents=True)
        requester_cache = {"XDG_CACHE_HOME": str(root / "requester")}
        with mock.patch.object(skill_runtime, "PREPARED_CACHE_HOME", prepared):
            self.assertEqual(skill_runtime.skill_cache_path(requester_cache), prepared / skill_runtime.SKILL_CACHE_DIRECTORY_NAME)
            self.assertEqual(skill_runtime.writable_skill_cache_path(requester_cache), root / "requester" / skill_runtime.SKILL_CACHE_DIRECTORY_NAME)

    def test_without_a_prepared_directory_both_are_the_requester_cache(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        requester_cache = {"XDG_CACHE_HOME": str(root)}
        with mock.patch.object(skill_runtime, "PREPARED_CACHE_HOME", root / "skills" / ".prepared"):
            self.assertEqual(skill_runtime.skill_cache_path(requester_cache), skill_runtime.writable_skill_cache_path(requester_cache))

    def test_the_prepared_directory_is_named_beside_the_skill_directories(self):
        self.assertEqual(skill_runtime.PREPARED_CACHE_HOME, Path(skill_runtime.__file__).resolve().parents[2] / ".prepared")


if __name__ == "__main__":
    unittest.main()
