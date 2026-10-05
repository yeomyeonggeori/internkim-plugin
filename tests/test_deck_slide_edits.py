from collections import Counter
from pathlib import Path
import re
import sys
import unittest

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from deck.deck_source import normalized_text, parse_source, visible_text  # noqa: E402
from deck.slide_edits import slide_edits  # noqa: E402


CARDS = '<section id="s3" class="slide"><h2>Three bets for 2027</h2><div class="row"><div class="card"><h3>Sync</h3><p>Inventory sync ships in Q1.</p></div><div class="card"><h3>Payroll</h3><p>Pilot with 50 cafes in Q2.</p></div></div><aside class="notes">Notes stay.</aside></section>'
LIST = '<section><h2>What we decide today</h2><ul><li><i data-icon="check"></i> Approve the roadmap</li><li>Name the partners</li><li>Confirm the budget</li></ul><aside class="notes">n</aside></section>'
TABLE = '<section><h2>Pricing today</h2><table><tr><th>Tier</th><th>Price</th></tr><tr><td>Basic</td><td>$19</td></tr></table><p>Reviewed in Q4.</p><aside class="notes">n</aside></section>'
CHART = '<section><h2>Growth</h2><figure data-chart="bar" data-labels="Q1, Q2" data-values="1, 2" data-unit=""></figure><p>Referrals drove it.</p><aside class="notes">n</aside></section>'
PHOTO = '<section><h2>The depot</h2><img src="depot.jpg"><p>Opens in October.</p><aside class="notes">n</aside></section>'
SINGLE = '<section><h2>One line</h2><p>Only this.</p><aside class="notes">n</aside></section>'
KEYED = '<section><h2>Bet 2: payroll</h2><div class="kv"><span class="k">The bet</span><span class="v">Payroll</span></div><div class="kv"><span class="k">Risk</span><span class="v">Regions differ</span></div><aside class="notes">n</aside></section>'
ICON_ROWS = '<section><h2>Three developments</h2><div class="col"><div class="item" style="display:flex;gap:20px;font-size:var(--size-title);"><i data-icon="search"></i><span><b>Disease model</b><br>Leaf photo diagnosis</span></div><div class="item" style="display:flex;gap:20px;"><i data-icon="settings"></i><span><b>Control link</b><br>Greenhouse</span></div></div><aside class="notes">n</aside></section>'


def words(markup: str) -> Counter:
    root = parse_source(markup)
    return Counter(normalized_text(visible_text(root)).split())


def kinds(markup: str) -> tuple[int, int, int]:
    return markup.count("<table"), markup.count("<img"), markup.count("data-chart=")


def ids(section: str) -> set[str]:
    return {edit.id for edit in slide_edits(section)}


class SlideEditsTest(unittest.TestCase):
    def test_every_edit_is_one_section_that_keeps_the_words_the_parts_and_the_notes(self):
        for source in (CARDS, LIST, TABLE, CHART, PHOTO, SINGLE):
            for edit in slide_edits(source):
                with self.subTest(source=source[:40], edit=edit.id):
                    self.assertEqual(len(re.findall(r"<section\b", edit.section)), 1)
                    self.assertEqual(len(re.findall(r"</section>", edit.section)), 1)
                    self.assertEqual(words(edit.section), words(source))
                    self.assertEqual(kinds(edit.section), kinds(source))
                    self.assertIn('<aside class="notes">', edit.section)
                    self.assertNotEqual(edit.section.strip(), source.strip())

    def test_an_edit_keeps_the_sections_id_and_classes(self):
        for edit in slide_edits(CARDS):
            self.assertIn('id="s3"', edit.section)
            self.assertIn("slide", edit.section.split(">", 1)[0])

    def test_a_composition_is_offered_only_when_the_content_has_its_parts(self):
        self.assertIn("recompose:table", ids(TABLE))
        self.assertNotIn("recompose:chart", ids(TABLE))
        self.assertIn("recompose:chart", ids(CHART))
        self.assertIn("recompose:photo-text", ids(PHOTO))
        self.assertNotIn("recompose:table", ids(LIST))
        self.assertTrue({"recompose:sequence", "recompose:panel", "recompose:columns"} <= ids(LIST))
        self.assertNotIn("recompose:sequence", ids(SINGLE))

    def test_cards_become_separate_items_so_a_sequence_is_offered(self):
        self.assertIn("recompose:sequence", ids(CARDS))
        self.assertIn("recompose:columns", ids(CARDS))

    def test_a_list_keeps_its_icons_and_every_item(self):
        sequence = next(edit for edit in slide_edits(LIST) if edit.id == "recompose:sequence")
        self.assertIn('data-icon="check"', sequence.section)
        self.assertEqual(sequence.section.count("Approve the roadmap") + sequence.section.count("Name the partners") + sequence.section.count("Confirm the budget"), 3)

    def test_each_edit_names_its_operation_and_says_what_it_does(self):
        for edit in slide_edits(CARDS):
            self.assertEqual(edit.operation, "recompose")
            self.assertTrue(edit.description.strip())

    def test_large_text_is_offered_only_for_a_short_slide(self):
        self.assertIn("recompose:text-large", ids(SINGLE))
        long_text = "<section><h2>Long</h2>" + "".join(f"<p>{'word ' * 30}{index}</p>" for index in range(8)) + '<aside class="notes">n</aside></section>'
        self.assertNotIn("recompose:text-large", ids(long_text))

    def test_a_title_wrapped_by_an_earlier_edit_is_still_the_title(self):
        wrapped = TABLE.replace("<h2>Pricing today</h2>", '<div style="flex:none;"><h2>Pricing today</h2></div>')
        edit = next(edit for edit in slide_edits(wrapped) if edit.id == "recompose:table")
        self.assertLess(edit.section.index("<h2>"), edit.section.index("<table"))

    def test_a_key_and_value_row_keeps_its_class_so_the_two_do_not_run_together(self):
        for edit in slide_edits(KEYED):
            self.assertIn('class="kv"', edit.section, edit.id)

    def test_an_icon_row_keeps_its_row_layout_and_loses_only_its_font_size(self):
        for edit in (edit for edit in slide_edits(ICON_ROWS) if edit.id != "recompose:text-large"):
            with self.subTest(edit=edit.id):
                self.assertIn("display:flex", edit.section)
                self.assertNotIn("font-size:var(--size-title)", edit.section.split("</h2>", 1)[1])

    def test_numbered_steps_stay_a_row_so_the_number_and_its_name_do_not_run_together(self):
        steps = '<section><h2>Three</h2><div class="step"><span class="no">01</span><span class="name">Disease model</span></div><div class="step"><span class="no">02</span><span class="name">Control link</span></div><aside class="notes">n</aside></section>'
        for edit in slide_edits(steps):
            self.assertIn("display:flex", edit.section, edit.id)


if __name__ == "__main__":
    unittest.main()
