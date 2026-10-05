import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from staged_deck_fixture import RUNTIME_CONTEXT_VARIABLE, style_sheet_markdown

from deck.check_deck import check_outline  # noqa: E402
from deck.layout_choice import assigned_layouts, decided_choices, is_decision_pending, layout_request, request_digest  # noqa: E402
from deck.outline import Outline, OutlinePage, layout_issues, outline_issues, read_outline  # noqa: E402


def page(title: str, page_type: str, brief: tuple[str, ...] = ("a fact from the request",), photos: tuple[str, ...] = (), layout: str = "") -> OutlinePage:
    return OutlinePage(title, page_type, brief, photos, layout)


def outline(*pages: OutlinePage, core_hook: str = "Margins fell 40% while volume grew") -> Outline:
    return Outline(core_hook, pages)


def codes(issues) -> list[tuple[str, str | None]]:
    return [(issue.kind.code, issue.location) for issue in issues]


def body_deck(*layouts: str) -> Outline:
    pages = [page("Cover", "cover", layout="cover_typography_hero")]
    pages += [page(f"Body {index}", "content", layout=layout) for index, layout in enumerate(layouts, start=1)]
    return outline(*pages, page("Close", "closing", layout="closing_cta"))


class OutlineContentTest(unittest.TestCase):
    def test_a_complete_outline_passes(self):
        self.assertEqual(outline_issues(outline(page("Cover", "cover"), page("Point", "content"), page("Close", "closing")), set(), 3), [])

    def test_an_unknown_type_or_a_missing_brief_or_core_hook_is_refused(self):
        issues = outline_issues(outline(page("Cover", "cover"), page("Point", "slide", brief=()), core_hook=""), set(), None)
        self.assertEqual(sorted(codes(issues)), sorted([("OUTLINE_INCOMPLETE", "outline"), ("OUTLINE_INCOMPLETE", "outline page 2"), ("OUTLINE_INCOMPLETE", "outline page 2")]))

    def test_placeholder_copy_is_refused(self):
        issues = outline_issues(outline(page("Cover", "cover"), page("Growth", "content", brief=("revenue grew XX% TBD",))), set(), None)
        self.assertIn(("PLACEHOLDER_LEFT", "outline page 2"), codes(issues))

    def test_a_photo_the_guide_does_not_list_is_refused(self):
        issues = outline_issues(outline(page("Cover", "cover", photos=("/photos/a.jpg",)), page("Point", "content", photos=("/photos/b.jpg",))), {"/photos/a.jpg"}, None)
        self.assertEqual(codes(issues), [("PHOTO_NOT_LISTED", "outline page 2")])

    def test_the_requested_page_count_is_enforced(self):
        self.assertIn(("SLIDE_COUNT_MISMATCH", "outline"), codes(outline_issues(outline(page("Cover", "cover"), page("Close", "closing")), set(), 5)))

    def test_a_deck_that_opens_without_a_cover_is_a_warning(self):
        issues = outline_issues(outline(page("Point", "content"), page("Point", "content"), page("Close", "content")), set(), None)
        self.assertEqual({issue.kind.severity for issue in issues}, {"warning"})


class OutlineLayoutTest(unittest.TestCase):
    def test_a_layout_of_another_type_or_a_photo_layout_without_a_photo_is_refused(self):
        deck = outline(page("Cover", "cover", layout="kpi_cards_row"), page("Point", "content", layout="left_text_right_image"), page("Close", "closing", layout="closing_cta"))
        self.assertEqual(codes(layout_issues(deck)), [("LAYOUT_INVALID", "outline page 1"), ("LAYOUT_INVALID", "outline page 2")])

    def test_a_photo_layout_is_valid_for_a_page_with_a_photo(self):
        deck = outline(page("Cover", "cover", photos=("a.jpg",), layout="cover_split_image"), page("Close", "closing", layout="closing_cta"))
        self.assertEqual(layout_issues(deck), [])

    def test_a_body_layout_repeated_back_to_back_is_refused(self):
        self.assertEqual(codes(layout_issues(body_deck("hero_big_number", "hero_big_number"))), [("LAYOUT_REPEATED", "outline page 3")])

    def test_four_body_pages_need_three_layouts(self):
        self.assertEqual(codes(layout_issues(body_deck("hero_big_number", "three_column_cards", "hero_big_number", "three_column_cards"))), [("LAYOUT_VARIETY", "outline")])
        self.assertEqual(layout_issues(body_deck("hero_big_number", "three_column_cards", "timeline_horizontal", "three_column_cards")), [])


def answer(*rankings: dict) -> dict:
    return {f"page_{index:02d}": {"option": max(ranking, key=ranking.get), "probabilities": ranking} for index, ranking in enumerate(rankings, start=1)}


class LayoutChoiceTest(unittest.TestCase):
    def test_each_page_is_one_question_whose_options_are_the_layouts_it_can_take(self):
        deck = outline(page("Cover", "cover"), page("Point", "content", photos=("a.jpg",)), page("Data", "data"), page("Close", "closing"))
        request = layout_request(deck)
        self.assertEqual(sorted(request["questions"]), ["page_01", "page_02", "page_03", "page_04"])
        self.assertNotIn("cover_split_image", request["questions"]["page_01"]["options"])
        self.assertIn("left_text_right_image", request["questions"]["page_02"]["options"])
        self.assertEqual(set(request["questions"]["page_03"]["options"]), {"kpi_cards_row", "chart_with_insight", "two_by_two_grid"})
        self.assertIn("Page 2 of 4, a content page. Title: Point.", request["questions"]["page_02"]["instructions"])
        self.assertIn("Do not count points", request["instructions"])
        self.assertIn("one key number for hero_big_number", request["instructions"])

    def test_an_answer_counts_only_for_the_outline_it_was_asked_about(self):
        deck = outline(page("Cover", "cover"), page("Close", "closing"))
        changed = outline(page("Cover", "cover"), page("Close again", "closing"))
        decision = {"digest": request_digest(deck), "choices": answer({"cover_dark_minimal": 0.9}, {"closing_cta": 0.9})}
        self.assertTrue(is_decision_pending(deck, None))
        self.assertFalse(is_decision_pending(deck, decision))
        self.assertTrue(is_decision_pending(changed, decision))
        self.assertIsNotNone(decided_choices(deck, decision))
        self.assertIsNone(decided_choices(deck, decision | {"failure": "timeout"}))

    def test_the_most_likely_layout_is_taken_unless_it_repeats_the_body_page_before(self):
        deck = body_deck("", "")
        choices = answer({"cover_typography_hero": 0.9}, {"hero_big_number": 0.8, "three_column_cards": 0.1}, {"hero_big_number": 0.7, "timeline_horizontal": 0.2}, {"closing_cta": 0.9})
        self.assertEqual(assigned_layouts(deck, choices), ["cover_typography_hero", "hero_big_number", "timeline_horizontal", "closing_cta"])

    def test_the_page_with_the_smallest_margin_moves_to_its_next_layout_until_three_are_used(self):
        deck = body_deck("", "", "", "")
        choices = answer(
            {"cover_typography_hero": 0.9},
            {"hero_big_number": 0.9, "two_column_comparison": 0.05},
            {"three_column_cards": 0.9, "timeline_horizontal": 0.05},
            {"hero_big_number": 0.5, "two_column_comparison": 0.45},
            {"three_column_cards": 0.9, "timeline_horizontal": 0.05},
            {"closing_cta": 0.9},
        )
        layouts = assigned_layouts(deck, choices)
        self.assertEqual(layouts, ["cover_typography_hero", "hero_big_number", "three_column_cards", "two_column_comparison", "three_column_cards", "closing_cta"])
        self.assertEqual(layout_issues(deck.with_layouts(layouts)), [])


def write_context(directory: Path, **fields) -> Path:
    context = {"requester": {"name": "이샘플", "email": "sample@example.com"}, "today": "2026-10-05", "company": {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": False, "choosesDeckLayouts": True, "deckLayouts": None, "judgesDraftClaims": True, "draftClaims": None} | fields
    path = directory / "office-runtime-context.json"
    path.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
    return path


def answer_as_host(context_path: Path, flagged: tuple[str, ...] = ()) -> None:
    context = json.loads(context_path.read_text(encoding="utf-8"))
    request = (context_path.parent / "deck-layouts-request.json").read_bytes()
    claims = (context_path.parent / "draft-claims-request.json").read_bytes()
    questions = json.loads(request)["questions"]
    context["deckLayouts"] = {"digest": hashlib.sha256(request).hexdigest(), "choices": {name: {"option": sorted(question["options"])[0], "probabilities": {option: 0.5 for option in question["options"]} | {sorted(question["options"])[0]: 0.9}} for name, question in questions.items()}}
    context["draftClaims"] = {"digest": hashlib.sha256(claims).hexdigest(), "unsupported": [claim for claim in json.loads(claims)["claims"] if claim["text"] in flagged]}
    context_path.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")


OUTLINE = {"core_hook": "Delivery got faster and repeat orders rose", "pages": [
    {"title": "Faster delivery", "type": "cover", "brief": ["Third quarter review"], "photos": []},
    {"title": "Repeat orders rose", "type": "content", "brief": ["Repeat orders rose 12 percent", "A rival cut prices"], "photos": []},
    {"title": "Approve the budget", "type": "closing", "brief": ["Budget of 6 million"], "photos": []},
]}


class OutlineStageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        (self.directory / "DESIGN.md").write_text(style_sheet_markdown(), encoding="utf-8")
        (self.directory / "outline.json").write_text(json.dumps(OUTLINE), encoding="utf-8")
        self.context = write_context(self.directory)
        previous = os.environ.get(RUNTIME_CONTEXT_VARIABLE)
        os.environ[RUNTIME_CONTEXT_VARIABLE] = str(self.context)
        self.addCleanup(lambda: os.environ.pop(RUNTIME_CONTEXT_VARIABLE, None) if previous is None else os.environ.__setitem__(RUNTIME_CONTEXT_VARIABLE, previous))

    def check(self):
        return check_outline(self.directory / "outline.json", None)

    def test_the_outline_waits_for_the_host_then_gains_a_layout_per_page(self):
        waiting = self.check()
        self.assertEqual([issue.kind.code for issue in waiting.issues], ["OUTLINE_BEING_PREPARED"])
        self.assertTrue((self.directory / "deck-layouts-request.json").is_file())
        self.assertIn("run office check outline.json again as your next command", waiting.summary)
        self.assertIn("nothing is asked of the person", waiting.summary)
        answer_as_host(self.context)
        ready = self.check()
        written, _ = read_outline(self.directory / "outline.json")
        self.assertEqual(ready.status, "ok", ready.summary)
        self.assertTrue(all(page.layout for page in written.pages))
        self.assertIn(written.pages[1].layout, ready.summary)

    def test_a_statement_the_host_flags_is_refused_once_before_any_page_exists(self):
        self.check()
        answer_as_host(self.context, flagged=("A rival cut prices",))
        refused = self.check()
        self.assertEqual([(issue.kind.code, issue.location) for issue in refused.issues], [("UNSUPPORTED_CLAIM", "outline page 2")])
        sent = json.loads((self.directory / "draft-claims-request.json").read_text(encoding="utf-8"))["claims"]
        self.assertIn({"path": "outline.pages[1].brief[1]", "at": "outline page 2 brief", "text": "A rival cut prices"}, sent)
        self.assertNotEqual(self.check().status, "error")


if __name__ == "__main__":
    unittest.main()
