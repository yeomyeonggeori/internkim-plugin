from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from staged_deck_fixture import issue_codes, issues_at  # noqa: E402
from design_gate_slides import BALLAST  # noqa: E402
from staged_deck_fixture import check_deck, write_staged_deck  # noqa: E402
from render_fixture import can_render  # noqa: E402

STYLE = """
.a { position: absolute; left: 96px; top: 300px; width: 700px; font-size: 32px; margin: 0; }
.b { position: absolute; left: 160px; top: 312px; width: 700px; font-size: 32px; margin: 0; }
.photo { position: absolute; right: 0; top: 0; width: 700px; height: 900px; }
.icon { position: absolute; left: 100px; top: 306px; width: 90px; height: 90px; }
.side { position: absolute; left: 900px; top: 300px; width: 600px; font-size: 32px; margin: 0; }
"""
HEADING = "<h2>Revenue grew 18 percent in the third quarter</h2>"
TEXT = "The logistics business closed the quarter above its plan in every region."
SLIDES = [
    f'{HEADING}<p class="a">{TEXT}</p><p class="b">{TEXT}</p>',
    f'{HEADING}<svg class="icon" aria-hidden="true" width="90" height="90"></svg><p class="a">{TEXT}</p>',
    f'{HEADING}<p class="a">{TEXT}</p><p class="side">{TEXT}</p>{BALLAST}',
]


@unittest.skipUnless(can_render(), "the renderer is not available")
class ContentOverlapTest(unittest.TestCase):
    def test_text_over_text_and_text_over_an_icon_are_refused_and_text_beside_text_is_not(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = check_deck(write_staged_deck(Path(directory), SLIDES, STYLE))
        located = {issue["location"] for issue in issues_at(envelope, "CONTENT_OVERLAP")}
        self.assertEqual(located, {"page 1", "page 2"}, sorted(issue_codes(envelope)))


if __name__ == "__main__":
    unittest.main()
