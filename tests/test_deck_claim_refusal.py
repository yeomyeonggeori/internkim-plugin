import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from design_gate_slides import CLEAN, CLEAN_STYLE
from host_fixture import FakeHost
from render_fixture import can_render
from staged_deck_fixture import build_deck, write_staged_deck
from task_context_fixture import environment_with_context, write_context_at

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"

INVENTED = "Open the Incheon depot"
REQUEST = "Make a deck on the third quarter: Q3 revenue 128M against a plan of 140M, regions Seoul 52M, Busan 41M, Daegu 35M; in the fourth quarter we move peak routes to night shifts, review cost per parcel with the board and publish the new route map."


def judging_invented(body: dict) -> dict:
    claims = body["state"].get("claims") or {}
    answers = {key: answer_for(claims.get(key), question) for key, question in body["questions"].items()}
    return {"answers": answers, "modelName": "jev", "usage": {"costUSD": 0.001}}


def answer_for(claim: dict | None, question: dict) -> dict:
    if claim is None:
        kind = next(iter(question["criteria"]))
    else:
        kind = "claim" if INVENTED in claim["text"] else "source"
    return {"type": "choice", "choice": kind, "probabilities": {kind: 0.9}}


@unittest.skipUnless(can_render(), "the renderer is not available")
class DeckClaimRefusalTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = write_staged_deck(Path(self.temporary.name), CLEAN[0], CLEAN_STYLE)
        self.context = write_context_at(self.directory / "task" / "task-context.json", {"today": "2026-10-04", "request": [REQUEST]})
        envelope = build_deck(self.directory, extension="pptx", environment=environment_with_context(self.context))
        self.assertNotEqual(envelope["status"], "error", envelope["summary"])

    def deliver(self, name: str) -> dict:
        with FakeHost(decide=judging_invented):
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "delivery-check", f"build/{name}"], capture_output=True, text=True, cwd=self.directory, env=environment_with_context(self.context))
        return json.loads(completed.stdout)

    def metadata(self, name: str) -> dict:
        return json.loads((self.directory / "build" / f"{name}.meta.json").read_text(encoding="utf-8"))

    def page(self, number: int) -> str:
        return (self.directory / "pages" / f"{number:02d}.html").read_text(encoding="utf-8")

    def outcome(self, envelope: dict) -> str:
        return envelope["details"]["claimCheck"][0]["outcome"]

    def test_an_unsupported_list_item_refuses_the_deck_and_leaves_the_page_for_the_model_to_rewrite(self):
        envelope = self.deliver("deck.pptx")
        self.assertEqual(self.outcome(envelope), "refused")
        self.assertIn(INVENTED, self.page(4))
        metadata = self.metadata("deck.pptx")
        self.assertEqual(metadata["notes"], [])
        self.assertIn("deck.pptx was not delivered", metadata["refusal"])
        self.assertIn("slide 4", metadata["refusal"])
        self.assertIn(INVENTED, metadata["refusal"])

    def test_the_other_format_of_the_same_build_is_refused_too(self):
        self.deliver("deck.pptx")
        self.assertEqual(self.outcome(self.deliver("deck.pdf")), "refused")

    def test_a_deck_delivered_again_still_holding_the_statement_has_it_taken_out(self):
        self.deliver("deck.pptx")
        envelope = self.deliver("deck.pptx")
        self.assertEqual(self.outcome(envelope), "blanked")
        self.assertNotIn(INVENTED, self.page(4))
        metadata = self.metadata("deck.pptx")
        self.assertNotIn("refusal", metadata)
        self.assertTrue(any("slide 4" in note for note in metadata["notes"]))

    def test_a_rebuilt_deck_still_holding_the_statement_has_it_taken_out(self):
        self.deliver("deck.pptx")
        self.assertNotEqual(build_deck(self.directory, extension="pptx", environment=environment_with_context(self.context))["status"], "error")
        self.assertEqual(self.outcome(self.deliver("deck.pptx")), "blanked")


if __name__ == "__main__":
    unittest.main()
