from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_fixture import can_render  # noqa: E402
from staged_deck_fixture import PICTURE_SOURCE, check_deck, codes_at, issues_at, write_staged_deck  # noqa: E402

FILL_STYLE = """
.columns { flex: 1; display: flex; }
.columns > div { flex: 1; padding: 0 48px; }
.columns > div:first-child { border-right: 2px solid var(--line); padding-left: 0; }
.hairline-row { flex: 1; display: flex; gap: 48px; }
.hairline { width: 2px; background: var(--line); }
.split { flex: 1; display: flex; gap: 64px; }
.split > div { flex: 1; }
.number-card { display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 28px; background: var(--surface); border-radius: var(--radius); }
.number-card b { font-size: 160px; line-height: 1; color: var(--accent); }
.timeline { flex: 1; display: flex; gap: 32px; }
.step { flex: 1; display: flex; flex-direction: column; padding: 40px; background: var(--surface); border-radius: var(--radius); }
.step h3 { font-size: 44px; }
.step i { margin-top: auto; height: 24px; border-radius: 12px; background: var(--accent); }
.fitted { display: flex; gap: 32px; }
.fitted > div { flex: 1; display: flex; flex-direction: column; gap: 16px; padding: 40px; background: var(--surface); border-radius: var(--radius); }
.fitted b { font-size: 120px; line-height: 1; color: var(--accent); }
.apart { flex: 1; display: flex; flex-direction: column; justify-content: space-between; padding: 40px; background: var(--surface); border-radius: var(--radius); }
""" + f'.photo {{ flex: 1; display: flex; align-items: flex-end; padding: 32px; border-radius: var(--radius); background: #14213D url("{PICTURE_SOURCE}") center / cover; color: #FFFFFF; }}'

HEADING = "<h2>The pilot cut losses at every farm</h2>"
LEAD = "<p>Disease was found two weeks earlier on all 64 farms.</p>"

SHORT_BESIDE_DIVIDER = f'{HEADING}<div class="columns"><div><h3>Sensors</h3><p>Every greenhouse reports each minute.</p></div><div><h3>Forecast</h3><p>Harvest dates are predicted a month ahead.</p></div></div>'
SHORT_BESIDE_HAIRLINE = f'{HEADING}<div class="hairline-row"><div>{LEAD}</div><div class="hairline"></div><div><p>Losses fell by a third in the first season.</p></div></div>'
ONE_NUMBER_IN_A_TALL_CARD = f'<div class="split"><div>{HEADING}{LEAD}</div><div class="number-card"><b>63%</b><p>of farms found disease late</p></div></div>'
STEPS_HELD_UP_BY_BARS = f'{HEADING}<div class="timeline"><div class="step"><p>Months 1 to 3</p><h3>Collect data</h3><i></i></div><div class="step"><p>Months 4 to 8</p><h3>Train the model</h3><i></i></div><div class="step"><p>Months 9 to 12</p><h3>Field trial</h3><i></i></div></div>'

CARDS_FILLED_BY_WHAT_THEY_HOLD = f'{HEADING}<div class="fitted"><div><p>Farms in the pilot</p><b>64</b><p>Up from 12 in the first year, across three provinces.</p></div><div><p>Yield gain</p><b>17%</b><p>Average across the 64 farms over two seasons.</p></div></div>'
TWO_LINES_PUSHED_APART = f'{HEADING}<div class="apart"><p>Losses fell by a third in the first season.</p><p>Measured on all 64 farms.</p></div>'
PHOTO_WITH_A_CAPTION = f'{HEADING}<div class="photo"><p>The Nonsan pilot greenhouse in its second season</p></div>'


@unittest.skipUnless(can_render(), "the renderer is not available")
class PageFillIgnoresRulesTest(unittest.TestCase):
    def test_a_column_border_does_not_fill_the_band_below_short_columns(self):
        envelope = self.checked([SHORT_BESIDE_DIVIDER])
        self.assertIn("PAGE_NOT_FILLED", codes_at(envelope, "page 2"), envelope["summary"])

    def test_a_full_height_hairline_does_not_fill_the_band_below_short_text(self):
        envelope = self.checked([SHORT_BESIDE_HAIRLINE])
        self.assertIn("PAGE_NOT_FILLED", codes_at(envelope, "page 2"), envelope["summary"])

    def checked(self, sections: list) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            return check_deck(write_staged_deck(Path(directory), ["<h1>Strawberry pilot review</h1>", *sections, "<h2>Thank you</h2>"], FILL_STYLE))


@unittest.skipUnless(can_render(), "the renderer is not available")
class CardFillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        sections = ["<h1>Strawberry pilot review</h1>", ONE_NUMBER_IN_A_TALL_CARD, STEPS_HELD_UP_BY_BARS, CARDS_FILLED_BY_WHAT_THEY_HOLD, PHOTO_WITH_A_CAPTION, TWO_LINES_PUSHED_APART, "<h2>Thank you</h2>"]
        cls.envelope = check_deck(write_staged_deck(Path(cls.directory.name), sections, FILL_STYLE))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_a_card_stretched_around_one_number_is_refused(self):
        self.assertIn("page 2", self.refused_pages(), self.envelope["summary"])

    def test_bars_at_the_foot_of_cards_do_not_count_as_their_content(self):
        self.assertIn("page 3", self.refused_pages(), self.envelope["summary"])

    def test_two_lines_pushed_to_the_ends_of_a_stretched_card_are_refused(self):
        self.assertIn("page 6", self.refused_pages(), self.envelope["summary"])

    def test_the_refusal_names_the_card_and_how_much_of_it_is_empty(self):
        message = next(issue["message"] for issue in issues_at(self.envelope, "CARD_NOT_FILLED") if issue["location"] == "page 2")
        self.assertIn("div.number-card", message)
        self.assertRegex(message, r"nothing is drawn across \d+px \(\d+%\) of its \d+px inner height")

    def test_cards_filled_by_what_they_hold_and_a_captioned_photo_pass(self):
        self.assertNotIn("page 4", self.refused_pages(), self.envelope["summary"])
        self.assertNotIn("page 5", self.refused_pages(), self.envelope["summary"])

    def refused_pages(self) -> list[str]:
        return [issue["location"] for issue in issues_at(self.envelope, "CARD_NOT_FILLED")]


if __name__ == "__main__":
    unittest.main()
