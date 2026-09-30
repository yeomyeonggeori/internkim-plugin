import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"


def run_office_python_json(code: str, working_directory: Path):
    completed = subprocess.run(
        [sys.executable, str(OFFICE_ENTRY), "python", "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        check=True,
        cwd=working_directory,
    )
    return json.loads(completed.stdout)


class DeckFixture(unittest.TestCase):
    def setUp(self):
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.directory = Path(self._temporary_directory.name)
