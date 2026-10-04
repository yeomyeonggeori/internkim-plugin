from pathlib import Path
import re
import subprocess
import sys
import unittest

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from powerpoint.definitions import OUT_OF_FRAME  # noqa: E402
from powerpoint.layout_audit import layout_issue  # noqa: E402


class AdviceTest(unittest.TestCase):
    def test_a_pptx_layout_issue_points_at_its_fix_or_says_what_to_do_without_one(self):
        moved = layout_issue(OUT_OF_FRAME, "slide 1 shape 2 lies partly outside the slide", "slide 1 shape 2", {"op": "set_transform", "slide": 1, "shape": 2, "x": 0})
        unplaced = layout_issue(OUT_OF_FRAME, "slide 1 shape 2 lies partly outside the slide", "slide 1 shape 2", None)
        self.assertIn("set_transform in fix", moved.suggestion)
        self.assertEqual(moved.fix, ({"op": "set_transform", "slide": 1, "shape": 2, "x": 0},))
        self.assertEqual((unplaced.suggestion, unplaced.fix), (OUT_OF_FRAME.kind.suggestion, ()))

    def test_the_guide_names_actions_that_add_no_words(self):
        guide = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", "create", "slides"], capture_output=True, text=True, check=True).stdout
        fix_of = {code: fix for code, fix in re.findall(r"^\s+([A-Z_]+) \(\w+\): .*?Fix: (.*)$", guide, re.MULTILINE)}
        self.assertIn("add no words of your own", fix_of["VERTICAL_DEAD_ZONE"])
        self.assertIn("add no words of your own", fix_of["EMPTY_REGION"])
        self.assertIn("remove the style attribute", fix_of["STYLE_NOT_DRAWN"])
        self.assertNotIn("kit", " ".join(fix_of.values()).lower())


if __name__ == "__main__":
    unittest.main()
