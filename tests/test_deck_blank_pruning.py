from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))

from deck.deck_claims import blanked_deck, deck_units  # noqa: E402

DECK = """<!doctype html><html><head><title>Plan</title></head><body>
<section><h1>Cover title</h1><p>Cover line that stays.</p></section>
<section><h2>Three bets</h2>
<div class="row">
<div class="card"><h3>Bet one</h3><p>Inventory sync ships in Q1.</p></div>
<div class="card"><h3>Bet two</h3><p>Payroll pilot runs in Q2.</p></div>
<div class="card"><h3>Bet three</h3><p>Bank feeds reach GA in Q3.</p></div>
</div></section>
<section><h2>Risks</h2><div class="row"><div class="card"><h3>API access</h3><p>Vendors may limit it.</p></div><div class="card"><h3>Regions</h3><p>Rules differ.</p></div></div></section>
<section><h2>Table slide</h2><table><tr><td>A</td><td>1</td></tr><tr><td>B</td><td>2</td></tr></table></section>
</body></html>
"""


def path_of(text: str) -> str:
    return next(unit.path for unit in deck_units(DECK) if unit.text == text)


class BlankPruningTest(unittest.TestCase):
    def test_a_card_left_with_only_its_title_is_dropped_and_the_others_stay(self):
        result = blanked_deck(DECK, [path_of("Payroll pilot runs in Q2.")])
        self.assertNotIn("Bet two", result)
        self.assertNotIn("Payroll", result)
        for kept in ("Bet one", "Inventory sync ships in Q1.", "Bet three", "Bank feeds reach GA in Q3."):
            self.assertIn(kept, result)
        self.assertEqual(result.count('class="card"'), 4)

    def test_a_slide_left_with_no_body_is_dropped(self):
        result = blanked_deck(DECK, [path_of("Vendors may limit it."), path_of("Rules differ.")])
        self.assertNotIn("Risks", result)
        self.assertEqual(result.count("<section"), 3)

    def test_a_cover_with_only_its_title_is_kept(self):
        result = blanked_deck(DECK, [path_of("Cover line that stays.")])
        self.assertIn("Cover title", result)
        self.assertEqual(result.count("<section"), 4)

    def test_a_table_row_whose_cells_are_all_blank_is_dropped(self):
        result = blanked_deck(DECK, [path_of("B"), path_of("2")])
        self.assertNotIn("<td>B", result)
        self.assertIn("<td>A", result)
        self.assertEqual(result.count("<tr>"), 1)

    def test_nothing_is_dropped_when_nothing_is_blanked(self):
        self.assertEqual(blanked_deck(DECK, []), DECK)

    def test_a_replacement_keeps_its_container(self):
        result = blanked_deck(DECK, [], {path_of("Payroll pilot runs in Q2."): "Payroll pilot runs in the second quarter."})
        self.assertIn("Bet two", result)
        self.assertIn("second quarter", result)

    def test_a_blank_that_leaves_the_slide_other_content_does_not_drop_the_slide(self):
        result = blanked_deck(DECK, [path_of("Inventory sync ships in Q1."), path_of("Payroll pilot runs in Q2.")])
        self.assertIn("Three bets", result)
        self.assertIn("Bet three", result)
        self.assertNotIn("Bet one", result)


if __name__ == "__main__":
    unittest.main()
