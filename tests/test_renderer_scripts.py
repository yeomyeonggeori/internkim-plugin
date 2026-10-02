from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from render.renderer import scripts_digest, stage_scripts  # noqa: E402


SCRIPTS = {"render_html.mjs": b"export const version = 1;\n"}


class RendererScriptStagingTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.packages = self.root / "prepared" / "render" / "packages"
        (self.packages / "node_modules").mkdir(parents=True)

    def test_two_checkouts_with_different_scripts_never_share_a_directory(self):
        self.assertNotEqual(scripts_digest(SCRIPTS), scripts_digest({"render_html.mjs": b"export const version = 2;\n"}))
        self.assertEqual(scripts_digest(SCRIPTS), scripts_digest(dict(SCRIPTS)))

    def test_scripts_staged_beside_the_packages_find_them_through_their_parent(self):
        directory = stage_scripts(self.packages / "scripts" / scripts_digest(SCRIPTS), SCRIPTS, self.packages / "node_modules")
        self.assertEqual((directory / "render_html.mjs").read_bytes(), SCRIPTS["render_html.mjs"])
        self.assertFalse((directory / "node_modules").exists())

    def test_scripts_staged_in_the_requester_cache_link_the_prepared_packages(self):
        requester = self.root / "requester" / "render" / "packages" / "scripts" / scripts_digest(SCRIPTS)
        directory = stage_scripts(requester, SCRIPTS, self.packages / "node_modules")
        self.assertEqual((directory / "node_modules").resolve(), (self.packages / "node_modules").resolve())
        self.assertEqual(stage_scripts(requester, SCRIPTS, self.packages / "node_modules"), directory)


if __name__ == "__main__":
    unittest.main()
