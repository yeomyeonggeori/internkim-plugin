import json
import os
from pathlib import Path
import tempfile
import unittest

from design_gate_slides import BODY, CLEAN, CLEAN_STYLE, HEADING
from render_fixture import can_render
from staged_deck_fixture import RUNTIME_CONTEXT_VARIABLE, build_deck, check_deck, write_staged_deck

from deck.deck_claims import deck_units  # noqa: E402


def blank_arguments(blanked: list[str], replaced: dict[str, str] | None = None) -> list[str]:
    return [argument for path in blanked for argument in ("--blank", path)] + [argument for path, text in (replaced or {}).items() for argument in ("--replace", f"{path}={text}")]


def unit_paths(directory: Path) -> dict[str, str]:
    check_deck(directory)
    return {unit.path: unit.text for unit in deck_units((directory / "slides.html").read_text(encoding="utf-8"))}


def reviewing_host(directory: Path) -> dict:
    context = directory / "context.json"
    context.write_text(json.dumps({"requester": {"name": "", "email": ""}, "today": "2026-10-04", "company": {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": True}), encoding="utf-8")
    return {**os.environ, RUNTIME_CONTEXT_VARIABLE: str(context)}


@unittest.skipUnless(can_render(), "the renderer is not available")
class PageBlankRemakeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = write_staged_deck(Path(self.temporary.name), CLEAN[0], CLEAN_STYLE)
        self.units = unit_paths(self.directory)

    def remake(self, blanked: list[str], replaced: dict[str, str] | None = None, environment: dict | None = None) -> dict:
        return build_deck(self.directory, extension="pdf", extra=blank_arguments(blanked, replaced), environment=environment)

    def outline(self) -> dict:
        return json.loads((self.directory / "outline.json").read_text(encoding="utf-8"))

    def path_of(self, text: str) -> str:
        return next(path for path, unit_text in self.units.items() if unit_text == text)

    def test_a_blanked_value_leaves_its_page_file_and_its_outline_brief(self):
        envelope = self.remake([self.path_of("Busan")])
        self.assertNotEqual(envelope["status"], "error", envelope["summary"])
        self.assertIn("slide 3 table", [blank["label"] for blank in envelope["details"]["blanks"]])
        self.assertNotIn("Busan", (self.directory / "pages" / "03.html").read_text(encoding="utf-8"))
        self.assertFalse(any("Busan" in line for line in self.outline()["pages"][2]["brief"]))
        self.assertIn("Seoul", (self.directory / "pages" / "03.html").read_text(encoding="utf-8"))

    def test_a_blanked_chart_takes_its_page_out_and_the_pages_after_it_move_up(self):
        last_title = self.units["slides[3].units[0]"]
        envelope = self.remake(["slides[1].units[1]"])
        self.assertNotEqual(envelope["status"], "error", envelope["summary"])
        self.assertEqual(len(self.outline()["pages"]), 3)
        self.assertFalse((self.directory / "pages" / "04.html").exists())
        self.assertIn(last_title, (self.directory / "pages" / "03.html").read_text(encoding="utf-8"))

    def test_a_page_the_claim_check_changed_is_handed_to_the_visual_review_to_recompose(self):
        envelope = self.remake([self.path_of("Busan")], environment=reviewing_host(self.directory))
        review = json.loads(Path(envelope["details"]["visualReview"]).read_text(encoding="utf-8"))
        self.assertEqual([slide["number"] for slide in review["slides"] if slide.get("recompose")], [3])

    def test_a_blanked_title_inside_the_deck_is_not_replaced_by_the_deck_title(self):
        deck_title = self.units["slides[0].units[0]"]
        envelope = self.remake(["slides[2].units[0]"])
        self.assertNotEqual(envelope["status"], "error", envelope["summary"])
        self.assertNotIn(deck_title, (self.directory / "pages" / "03.html").read_text(encoding="utf-8"))

    def test_a_replaced_title_becomes_its_outline_entrys_title_so_the_build_keeps_it(self):
        envelope = self.remake([], {"slides[2].units[0]": "Regional results"})
        self.assertNotEqual(envelope["status"], "error", envelope["summary"])
        self.assertEqual(self.outline()["pages"][2]["title"], "Regional results")
        self.assertIn("Regional results", (self.directory / "slides.html").read_text(encoding="utf-8"))

    def test_a_brief_line_naming_a_blanked_value_in_another_case_leaves_the_outline(self):
        outline = self.outline()
        outline["pages"][2]["brief"] = ["regional results: seoul, busan and daegu"]
        (self.directory / "outline.json").write_text(json.dumps(outline), encoding="utf-8")
        self.remake([self.path_of("Busan")])
        self.assertEqual(self.outline()["pages"][2]["brief"], [])

    def test_a_remake_that_blanks_the_cover_title_builds(self):
        self.assertNotEqual(self.remake(["slides[0].units[0]"])["status"], "error")

    def test_a_remake_that_only_replaces_text_builds(self):
        envelope = self.remake([], {"slides[3].units[1]": "Open it"})
        self.assertNotEqual(envelope["status"], "error", envelope["summary"])
        self.assertIn("Open it", (self.directory / "pages" / "04.html").read_text(encoding="utf-8"))

    def test_a_remake_that_blanks_every_value_builds(self):
        envelope = self.remake(list(self.units))
        self.assertNotEqual(envelope["status"], "error", envelope["summary"])


@unittest.skipUnless(can_render(), "the renderer is not available")
class BlanksHeldAcrossBuildsTest(unittest.TestCase):
    def test_a_deck_built_again_after_a_remake_keeps_its_blanks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_staged_deck(Path(directory), [f"{HEADING}{BODY}", f"{HEADING}{BODY}<p>A second line of the same slide.</p>"], CLEAN_STYLE)
            last = list(unit_paths(path))[-1]
            first = build_deck(path, extension="pdf", extra=["--blank", last])
            again = build_deck(path, extension="pdf")
            snapshot = json.loads((path / "build" / "deck.pdf.source.json").read_text(encoding="utf-8"))
        self.assertNotEqual(first["status"], "error", first["summary"])
        self.assertNotEqual(again["status"], "error", again["summary"])
        self.assertEqual(len(snapshot["blanks"]), 1)


if __name__ == "__main__":
    unittest.main()
