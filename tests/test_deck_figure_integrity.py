from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_fixture import can_render  # noqa: E402
from staged_deck_fixture import check_deck, codes_at, issues_at, write_staged_deck  # noqa: E402

FIGURE_STYLE = """
.block-chart figure[data-chart] { display: block; height: 560px; }
.squeezed-chart figure[data-chart] { height: 560px; }
.squeezed-chart figcaption { height: 530px; }
.number { width: 340px; margin: 0; font-size: 190px; font-weight: 800; line-height: 1; }
.number small { font-size: 60px; margin-left: 14px; }
.amount { width: 330px; margin: 0; font-size: 150px; font-weight: 800; line-height: 1; }
.amount small { font-size: 48px; margin-left: 10px; }
.roomy { width: 900px; }
"""

CHART = '<figure data-chart="bar" data-labels="Brakes, Steering, Housings" data-values="38, 27, 19" data-unit="억"><figcaption>Sales by product line</figcaption></figure>'
BLOCK_CHART = ' class="block-chart"', f"<h2>Brakes lead sales by product line</h2>{CHART}"
SQUEEZED_CHART = ' class="squeezed-chart"', f"<h2>Brakes lead sales by product line</h2>{CHART}"
SYMBOL_TORN_FROM_ITS_NUMBER = "<h2>Margin fell this quarter</h2><p class=\"number\">8.4<small>%</small></p><p>Down from 9.7% a year ago.</p>"
SYMBOL_WITH_ROOM = "<h2>Margin fell this quarter</h2><p class=\"number roomy\">8.4<small>%</small></p><p>Down from 9.7% a year ago.</p>"
UNIT_LEFT_ON_A_LINE_OF_ITS_OWN = "<h2>정부 지원금은 4.5억 원입니다</h2><p class=\"amount\">4.5<small>억 원</small></p><p>총 사업비의 75%</p>"
UNIT_WITH_ROOM = "<h2>정부 지원금은 4.5억 원입니다</h2><p class=\"amount roomy\">4.5<small>억 원</small></p><p>총 사업비의 75%</p>"


def checked(sections: list) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        return check_deck(write_staged_deck(Path(directory), ["<h1>Quarterly sales review</h1>", *sections, "<h2>Thank you</h2>"], FIGURE_STYLE))


@unittest.skipUnless(can_render(), "the renderer is not available")
class ChartPlotTest(unittest.TestCase):
    def test_a_page_that_sets_its_chart_figure_to_block_still_draws_the_chart(self):
        envelope = checked([BLOCK_CHART])
        self.assertNotIn("CHART_COLLAPSED", codes_at(envelope, "page 2"), envelope["summary"])

    def test_a_chart_squeezed_to_its_labels_inside_a_tall_figure_is_refused(self):
        envelope = checked([SQUEEZED_CHART])
        self.assertIn("CHART_COLLAPSED", codes_at(envelope, "page 2"), envelope["summary"])


@unittest.skipUnless(can_render(), "the renderer is not available")
class NumberAndUnitTest(unittest.TestCase):
    def test_a_symbol_set_in_its_own_element_and_wrapped_away_from_its_number_is_a_broken_word(self):
        envelope = checked([SYMBOL_TORN_FROM_ITS_NUMBER])
        self.assertIn("BROKEN_WORD", codes_at(envelope, "page 2"), envelope["summary"])
        message = next(issue["message"] for issue in issues_at(envelope, "BROKEN_WORD"))
        self.assertIn('"8.4%"', message)

    def test_a_unit_left_alone_on_the_last_line_is_refused(self):
        envelope = checked([UNIT_LEFT_ON_A_LINE_OF_ITS_OWN])
        self.assertIn("TEXT_RUNT", codes_at(envelope, "page 2"), envelope["summary"])
        message = next(issue["message"] for issue in issues_at(envelope, "TEXT_RUNT"))
        self.assertIn('"원"', message)

    def test_numbers_with_room_for_their_units_pass(self):
        envelope = checked([SYMBOL_WITH_ROOM, UNIT_WITH_ROOM])
        for page in ("page 2", "page 3"):
            self.assertFalse({"BROKEN_WORD", "TEXT_RUNT"} & codes_at(envelope, page), envelope["summary"])


if __name__ == "__main__":
    unittest.main()
