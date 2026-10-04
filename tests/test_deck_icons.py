from pathlib import Path
import tempfile
import unittest

from design_gate_fixture import run_office
from free_deck_fixture import write_free_deck
from render_fixture import can_render


STYLE = ".row { display: flex; gap: 16px; align-items: center; font-size: 40px; } .stack { display: flex; flex-direction: column; gap: 24px; }"
ROW = '<div class="row"><i data-icon="lightbulb"></i><span>연구개발에 씁니다</span></div>'
INLINE = '<p><i data-icon="megaphone"></i> 영업에 씁니다</p>'


class IconCheckTest(unittest.TestCase):
    def test_an_icon_the_kit_does_not_ship_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_free_deck(Path(directory), ['<h2>자금 사용처</h2><i data-icon="robot-arm"></i>'], STYLE)
            envelope = run_office(["check", "slides.html"], path)
        issue = next(issue for issue in envelope["issues"] if issue["code"] == "ICON_UNKNOWN")
        self.assertEqual((issue["severity"], issue["location"]), ("error", "slide 1"))


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class IconBuildTest(unittest.TestCase):
    def test_icons_in_a_row_and_on_their_own_line_are_drawn_as_pictures_in_the_pptx(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_free_deck(Path(directory), [f'<h2>자금 사용처</h2><div class="stack">{ROW}{INLINE}</div>'], STYLE)
            envelope = run_office(["create", "build/icons.pptx", "slides.html"], path)
        self.assertIn(envelope["status"], ("ok", "warning"), envelope["summary"])
        self.assertEqual(envelope["details"]["pptx"]["icons"], 2)


if __name__ == "__main__":
    unittest.main()
