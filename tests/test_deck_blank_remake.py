import json
import os
from pathlib import Path
import tempfile
import unittest

from design_gate_slides import BODY, CLEAN, CLEAN_STYLE, HEADING
from host_fixture import FakeHost
from render_fixture import can_render
from staged_deck_fixture import build_deck, check_deck, write_staged_deck
from task_context_fixture import environment_with_context, write_context_at

from deck.deck_claims import deck_units  # noqa: E402


def blank_arguments(blanked: list[str], replaced: dict[str, str] | None = None) -> list[str]:
    return [argument for path in blanked for argument in ("--blank", path)] + [argument for path, text in (replaced or {}).items() for argument in ("--replace", f"{path}={text}")]


def unit_paths(directory: Path) -> dict[str, str]:
    check_deck(directory)
    return {unit.path: unit.text for unit in deck_units((directory / "slides.html").read_text(encoding="utf-8"))}


def claim_check_remake(directory: Path) -> dict:
    context = write_context_at(directory / "task" / "task-context.json", {"today": "2026-10-04"})
    script_host = {"SKILL_HOST_URL": "http://127.0.0.1:9", "SKILL_HOST_TOKEN": "unused", "OFFICE_IS_REMAKE": "1"}
    return environment_with_context(context) | script_host


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

    def test_blanks_after_a_page_taken_out_name_the_slide_as_the_remade_deck_numbers_it(self):
        chart_title = self.outline()["pages"][1]["title"]
        envelope = self.remake(["slides[1].units[1]", "slides[3].units[1]"])
        self.assertNotEqual(envelope["status"], "error", envelope["summary"])
        blanks = envelope["details"]["blanks"]
        self.assertIn({"field": "slides[2].units[1]", "label": "slide 3 item", "withdrawn": "text"}, blanks)
        self.assertIn({"field": "slides[1]", "label": f'slide "{chart_title}"', "withdrawn": "slide"}, blanks)
        self.assertFalse(any(blank["label"].startswith("slide 4") or blank["label"].startswith("slide 2 chart") for blank in blanks))

    def test_a_page_the_claim_check_changed_is_handed_to_the_visual_review_to_recompose(self):
        self.remake([self.path_of("Busan")], environment=claim_check_remake(self.directory))
        snapshot = json.loads((self.directory / "build" / "deck.pdf.source.json").read_text(encoding="utf-8"))
        review = json.loads(Path(snapshot["visualReview"]).read_text(encoding="utf-8"))
        self.assertEqual([slide["number"] for slide in review["slides"] if slide.get("recompose")], [3])

    def test_a_remake_recomposes_the_page_it_emptied_through_the_page_fixer(self):
        page = self.directory / "pages" / "03.html"

        def recomposed(body: dict) -> dict:
            payload = json.loads(body["prompt"])
            self.assertIs(payload["recompose"], True)
            return {"answer": {"section": payload["section"].replace("</section>", "<p>Seoul leads.</p></section>", 1), "change": "recomposed"}, "usage": {"costUSD": 0.0}}
        clean = {"answers": {"visual_defect": {"type": "choice", "probabilities": {"none": 0.97}}}, "usage": {"costUSD": 0.0}}
        with FakeHost(decide=lambda body: clean, generate=recomposed) as host:
            environment = claim_check_remake(self.directory) | {name: os.environ[name] for name in ("SKILL_HOST_URL", "SKILL_HOST_TOKEN")}
            envelope = self.remake([self.path_of("Busan")], environment=environment)
        self.assertNotEqual(envelope["status"], "error", envelope["summary"])
        self.assertEqual(len(host.requests_to("generate")), 1)
        self.assertIn("Seoul leads.", page.read_text(encoding="utf-8"))

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
