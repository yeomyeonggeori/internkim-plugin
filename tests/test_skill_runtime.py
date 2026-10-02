from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))

import skill_runtime  # noqa: E402


class DependencyBootstrapTests(unittest.TestCase):
    def setUp(self):
        cache_directory = tempfile.TemporaryDirectory()
        self.addCleanup(cache_directory.cleanup)
        environment = mock.patch.dict(os.environ, {"XDG_CACHE_HOME": cache_directory.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.cache_directory = Path(cache_directory.name)
        self.environment_path = skill_runtime.dependency_environment_path("office")
        self.environment_python = self.environment_path / "bin" / "python"

    def test_the_dependency_environment_needs_no_further_setup(self):
        with mock.patch.object(skill_runtime.sys, "prefix", str(self.environment_path)), \
                mock.patch.object(skill_runtime, "create_dependency_environment") as create:
            self.assertTrue(skill_runtime.ensure_requirements("office"))
        create.assert_not_called()

    def test_an_environment_reached_through_a_symlinked_cache_is_still_the_one_running(self):
        linked_cache = Path(tempfile.mkdtemp()) / "cache"
        linked_cache.symlink_to(self.cache_directory)
        self.environment_path.mkdir(parents=True)
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(linked_cache)}), \
                mock.patch.object(skill_runtime.sys, "prefix", str(self.environment_path.resolve())), \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertTrue(skill_runtime.ensure_requirements("office"))
        reexecute.assert_not_called()

    def test_a_child_on_another_python_moves_into_the_environment_whatever_it_inherited(self):
        inherited = {"INTERNKIM_SKILL_BOOTSTRAP_READY_OFFICE": "1"}
        with mock.patch.dict(os.environ, inherited), \
                mock.patch.object(skill_runtime.sys, "prefix", "/usr"), \
                mock.patch.object(skill_runtime, "create_dependency_environment"), \
                mock.patch.object(skill_runtime, "install_requirements_if_needed"), \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertFalse(skill_runtime.ensure_requirements("office"))
        reexecute.assert_called_once_with(self.environment_python)

    def test_a_python_that_already_imports_every_name_still_moves_into_the_environment(self):
        every_name_importable = mock.Mock(returncode=0)
        with mock.patch.object(skill_runtime.sys, "prefix", "/usr"), \
                mock.patch.object(skill_runtime.subprocess, "run", return_value=every_name_importable), \
                mock.patch.object(skill_runtime, "create_dependency_environment"), \
                mock.patch.object(skill_runtime, "install_requirements_if_needed"), \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertFalse(skill_runtime.ensure_requirements("office"))
        reexecute.assert_called_once_with(self.environment_python)


if __name__ == "__main__":
    unittest.main()
