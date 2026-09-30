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
        self.environment_python = skill_runtime.dependency_environment_path("office") / "bin" / "python"

    def test_the_dependency_environment_needs_no_further_setup(self):
        with mock.patch.object(skill_runtime.sys, "executable", str(self.environment_python)), \
                mock.patch.object(skill_runtime, "python_satisfies_requirements") as satisfies:
            self.assertTrue(skill_runtime.ensure_requirements("office"))
        satisfies.assert_not_called()

    def test_a_child_on_another_python_moves_into_the_environment_whatever_it_inherited(self):
        inherited = {"INTERNKIM_SKILL_BOOTSTRAP_READY_OFFICE": "1"}
        with mock.patch.dict(os.environ, inherited), \
                mock.patch.object(skill_runtime.sys, "executable", "/usr/bin/python3"), \
                mock.patch.object(skill_runtime, "python_satisfies_requirements", return_value=False), \
                mock.patch.object(skill_runtime, "create_dependency_environment"), \
                mock.patch.object(skill_runtime, "install_requirements_if_needed"), \
                mock.patch.object(skill_runtime, "reexecute_python") as reexecute:
            self.assertFalse(skill_runtime.ensure_requirements("office"))
        reexecute.assert_called_once_with(self.environment_python)


if __name__ == "__main__":
    unittest.main()
