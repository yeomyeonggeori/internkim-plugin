import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from design_gate_fixture import OFFICE_ENTRY, design_markdown  # noqa: E402
from design_gate_slides import CLEAN, CLEAN_STYLE, deck  # noqa: E402
from render_fixture import can_render  # noqa: E402

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from deck.deck_claims import deck_units  # noqa: E402


def remake(blanked_paths: list[str], replaced: dict[str, str] | None = None) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / "DESIGN.md").write_text(design_markdown(), encoding="utf-8")
        (path / "slides.html").write_text(deck(CLEAN[0], CLEAN_STYLE), encoding="utf-8")
        arguments = ["create", "build/deck.pdf", "slides.html"] + [argument for blanked in blanked_paths for argument in ("--blank", blanked)] + [argument for path, text in (replaced or {}).items() for argument in ("--replace", f"{path}={text}")]
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=path)
        return completed.returncode, json.loads(completed.stdout)


def every_path() -> list[str]:
    return [unit.path for unit in deck_units(deck(CLEAN[0], CLEAN_STYLE))]


@unittest.skipUnless(can_render(), "the renderer is not available")
class BlankRemakeTest(unittest.TestCase):
    def test_a_remake_that_blanks_a_list_item_still_builds_and_names_the_blank(self):
        code, envelope = remake(["slides[3].units[1]"])
        self.assertEqual(code, 0, envelope["summary"])
        self.assertIn("slide 4 item", [blank["label"] for blank in envelope["details"]["blanks"]])

    def test_a_remake_that_blanks_a_chart_and_a_title_builds(self):
        code, envelope = remake(["slides[1].units[1]", "slides[2].units[0]"])
        self.assertEqual(code, 0, envelope["summary"])
        self.assertEqual(len(envelope["details"]["blanks"]), 2)

    def test_a_remake_that_blanks_the_cover_title_builds(self):
        code, envelope = remake(["slides[0].units[0]"])
        self.assertEqual(code, 0, envelope["summary"])

    def test_a_remake_that_only_replaces_text_builds_even_when_the_new_text_leaves_a_band(self):
        code, envelope = remake([], {"slides[3].units[1]": "Open it"})
        self.assertEqual(code, 0, envelope["summary"])

    def test_a_deck_made_again_from_its_blanked_source_is_still_a_remake_and_keeps_its_blanks(self):
        from design_gate_slides import BODY, HEADING

        clustered = deck([f"{HEADING}{BODY}<p>A second line of the same slide.</p>"], CLEAN_STYLE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "DESIGN.md").write_text(design_markdown(), encoding="utf-8")
            (path / "slides.html").write_text(clustered, encoding="utf-8")
            unit_paths = [unit.path for unit in deck_units(clustered)]
            first = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "build/deck.pdf", "slides.html", "--blank", unit_paths[-1]], capture_output=True, text=True, cwd=path)
            again = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "build/deck.pdf", "slides.html"], capture_output=True, text=True, cwd=path)
            snapshot = json.loads((path / "build" / "deck.pdf.source.json").read_text(encoding="utf-8"))
        self.assertNotEqual(json.loads(first.stdout)["status"], "error", first.stdout[:400])
        self.assertNotEqual(json.loads(again.stdout)["status"], "error", again.stdout[:400])
        self.assertEqual(len(snapshot["blanks"]), 1)

    def test_a_remake_that_blanks_every_value_builds(self):
        code, envelope = remake(every_path())
        self.assertEqual(code, 0, envelope["summary"])
        self.assertNotEqual(envelope["status"], "error")


RECORDED = Path(__file__).resolve().parent / "recorded"
GEOMETRY_CODES = {"CONTENT_OVERFLOW", "OUT_OF_FRAME", "CONTENT_OVERLAP"}


@unittest.skipUnless(can_render(), "the renderer is not available")
class RemadeDeckKeepsItsGeometryFindingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shutil

        cls.directory = tempfile.TemporaryDirectory()
        path = Path(cls.directory.name)
        for source in (RECORDED / "ko_smartfarm_v2").iterdir():
            shutil.copy(source, path / source.name)
        from PIL import Image

        Image.new("RGB", (1200, 800), (90, 140, 70)).save(path / "photo.jpg")
        (path / "context.json").write_text(json.dumps({"requester": {"name": "", "email": ""}, "today": "2026-10-04", "company": {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": True}), encoding="utf-8")
        environment = {**__import__("os").environ, "OFFICE_RUNTIME_CONTEXT": str(path / "context.json")}
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "build/deck.pdf", "slides.html", "--blank", "slides[0].units[0]"], capture_output=True, text=True, cwd=path, env=environment)
        cls.envelope = json.loads(completed.stdout)
        cls.review = json.loads((path / "build" / "review" / "visual-review.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_the_spilling_card_list_is_still_reported_by_the_remake_and_never_dropped(self):
        reported = {(issue["code"], issue["location"]) for issue in self.envelope["issues"]}
        self.assertTrue({("CONTENT_OVERFLOW", "slide 4"), ("OUT_OF_FRAME", "slide 4")} <= reported, reported)

    def test_the_review_hands_those_findings_to_the_host_with_edits_that_pass_the_gate(self):
        slide = next(slide for slide in self.review["slides"] if slide["number"] == 4)
        self.assertTrue(GEOMETRY_CODES & {defect["code"] for defect in slide["measured"]})
        self.assertTrue(slide["edits"], "no verified recomposition is offered for the spilling slide")


if __name__ == "__main__":
    unittest.main()
