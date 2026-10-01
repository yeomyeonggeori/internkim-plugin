from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from render.renderer import script_directory  # noqa: E402


class RendererScriptDirectoryTest(unittest.TestCase):
    def test_two_checkouts_with_different_scripts_never_share_a_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = Path(directory)
            first = script_directory(environment, {"render_html.mjs": b"export const version = 1;\n"})
            second = script_directory(environment, {"render_html.mjs": b"export const version = 2;\n"})
            again = script_directory(environment, {"render_html.mjs": b"export const version = 1;\n"})
            self.assertNotEqual(first, second)
            self.assertEqual(first, again)
            self.assertEqual((first / "render_html.mjs").read_bytes(), b"export const version = 1;\n")
            self.assertEqual(first.parent.parent, environment)


if __name__ == "__main__":
    unittest.main()
