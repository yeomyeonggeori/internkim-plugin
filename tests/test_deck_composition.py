from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_fixture import can_render  # noqa: E402
from staged_deck_fixture import check_deck, issues_at, write_staged_deck  # noqa: E402

from deck.composition import MAXIMUM_PAGES_PER_COMPOSITION, PageComposition, repeated_composition_issues  # noqa: E402


def row(count: int) -> dict:
    return {"arrangement": "row", "rows": 1, "columns": count, "count": count, "selector": "div.card"}


def grid(rows: int, columns: int) -> dict:
    return {"arrangement": "grid", "rows": rows, "columns": columns, "count": rows * columns, "selector": "div.card"}


def repeated_pages(measured: list[tuple[str, dict | None]]) -> list[str]:
    pages = [PageComposition(number, page_type, shape) for number, (page_type, shape) in enumerate(measured, start=1)]
    return [issue.location for issue in repeated_composition_issues(pages)]


class RepeatedCompositionRuleTest(unittest.TestCase):
    def test_the_same_arrangement_on_more_pages_than_allowed_is_refused_from_the_first_extra_page(self):
        measured = [("cover", None), ("content", row(3)), ("content", None), ("content", row(3)), ("data", None), ("content", row(3)), ("closing", None)]
        self.assertEqual(MAXIMUM_PAGES_PER_COMPOSITION, 2)
        self.assertEqual(repeated_pages(measured), ["page 6"])

    def test_two_pages_in_a_row_with_one_arrangement_are_refused_at_the_second(self):
        measured = [("cover", None), ("data", row(3)), ("content", row(3)), ("closing", None)]
        self.assertEqual(repeated_pages(measured), ["page 3"])

    def test_a_different_count_or_grid_is_a_different_arrangement(self):
        measured = [("cover", None), ("content", row(3)), ("content", row(2)), ("data", grid(2, 2)), ("content", row(4)), ("content", row(3)), ("closing", None)]
        self.assertEqual(repeated_pages(measured), [])

    def test_cover_and_closing_pages_are_not_compared(self):
        measured = [("cover", row(2)), ("content", row(2)), ("closing", row(2))]
        self.assertEqual(repeated_pages(measured), [])

    def test_the_refusal_names_the_arrangement_and_the_pages_it_repeats(self):
        pages = [PageComposition(2, "content", row(3)), PageComposition(4, "content", row(3)), PageComposition(6, "content", row(3))]
        message = repeated_composition_issues(pages)[0].message
        self.assertIn("one row of 3 equal cards", message)
        self.assertIn("page 2 and page 4", message)


PAGE_STYLE = """
section { padding: 88px 96px; }
.cards { display: flex; gap: 32px; flex: 1; }
.cards > .card { flex: 1; justify-content: center; }
.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; flex: 1; }
.list li { flex: 1; display: flex; align-items: center; gap: 32px; border-bottom: 1px solid var(--line); font-size: 32px; }
table { border-collapse: collapse; width: 100%; font-size: 30px; flex: 1; }
td { border-bottom: 1px solid var(--line); }
"""


def three_cards(heading: str, words: tuple[str, str, str]) -> str:
    return f"<h2>{heading}</h2><div class=\"cards\">" + "".join(f'<div class="card"><h3>{word}</h3><p>{word} grew in every region this year.</p></div>' for word in words) + "</div>"


COVER = "<h1>Annual operations review</h1><p>Prepared for the board</p>"
CLOSING = "<h2>Approve the plan</h2><p>Budget review on 30 June</p>"
CARDS_A = three_cards("Three regions led growth", ("Seoul", "Busan", "Daegu"))
CARDS_B = three_cards("Three products carried the year", ("Parcels", "Freight", "Storage"))
CARDS_C = three_cards("Three risks for next year", ("Fuel", "Labour", "Weather"))
LIST = '<h2>Four steps next quarter</h2><ol class="list"><li>Open the Incheon depot</li><li>Move peak routes to nights</li><li>Review parcel costs</li><li>Publish the route map</li></ol>'
TABLE = "<h2>Costs by team</h2><table><tr><td>Operations</td><td>$480k</td></tr><tr><td>Sales</td><td>$320k</td></tr><tr><td>Support</td><td>$140k</td></tr></table>"


@unittest.skipUnless(can_render(), "the renderer is not available")
class RepeatedCompositionGateTest(unittest.TestCase):
    def test_the_deck_check_refuses_rendered_card_rows_repeated_page_after_page(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = check_deck(write_staged_deck(Path(directory), [COVER, CARDS_A, CARDS_B, LIST, CARDS_C, CLOSING], PAGE_STYLE))
        self.assertEqual(sorted(issue["location"] for issue in issues_at(envelope, "REPEATED_COMPOSITION")), ["page 3", "page 5"])
        self.assertEqual(envelope["status"], "error")

    def test_a_deck_that_varies_its_compositions_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            envelope = check_deck(write_staged_deck(Path(directory), [COVER, CARDS_A, LIST, CARDS_B, TABLE, CLOSING], PAGE_STYLE))
        self.assertEqual(issues_at(envelope, "REPEATED_COMPOSITION"), [])

    def test_the_page_check_compares_a_page_with_the_pages_before_it(self):
        with tempfile.TemporaryDirectory() as directory:
            deck = write_staged_deck(Path(directory), [COVER, CARDS_A, LIST, CARDS_B, CARDS_C, CLOSING], PAGE_STYLE)
            third_row = check_deck(deck, "pages/05.html")
            second_row = check_deck(deck, "pages/04.html")
        self.assertEqual([issue["location"] for issue in issues_at(third_row, "REPEATED_COMPOSITION")], ["page 5"])
        self.assertIn("page 2 and page 4", issues_at(third_row, "REPEATED_COMPOSITION")[0]["message"])
        self.assertEqual(issues_at(second_row, "REPEATED_COMPOSITION"), [])


if __name__ == "__main__":
    unittest.main()
