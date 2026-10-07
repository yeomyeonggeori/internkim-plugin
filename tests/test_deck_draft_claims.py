import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from design_gate_slides import BODY, HEADING
from staged_deck_fixture import write_staged_deck
from render_fixture import can_render

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from host_fixture import FakeHost  # noqa: E402
from task_context_fixture import environment_with_context, write_context_at  # noqa: E402

INVENTED = "Churn fell to 1.2 percent after the pilot."
SLIDES = [f"{HEADING}{BODY}<p>{INVENTED}</p>"]


def judging_invented(body: dict) -> dict:
    claims = body["state"].get("claims") or {}
    answers = {key: answer_for(claims.get(key), question) for key, question in body["questions"].items()}
    return {"answers": answers, "modelName": "jev", "usage": {"costUSD": 0.001}}


def answer_for(claim: dict | None, question: dict) -> dict:
    kind = ("claim" if claim["text"] == INVENTED else "source") if claim else next(iter(question["criteria"]))
    return {"type": "choice", "choice": kind, "probabilities": {kind: 0.9}}


def run_office(directory: Path, *arguments: str, environment: dict | None = None) -> dict:
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=directory, env=environment)
    return json.loads(completed.stdout)


@unittest.skipUnless(can_render(), "the renderer is not available")
class DraftClaimsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)
        write_staged_deck(self.path, SLIDES)
        self.addCleanup(self.directory.cleanup)
        self.context = write_context_at(self.path / "task" / "task-context.json", {"today": "2026-10-04", "request": ["Make a deck about the sample"]})
        self.state = self.context.parent / "office"

    def unanswering_host(self) -> dict:
        return {"SKILL_HOST_URL": "http://127.0.0.1:9", "SKILL_HOST_TOKEN": "unused"}

    def codes(self, envelope: dict) -> list[str]:
        return [issue["code"] for issue in envelope["issues"]]

    def check_page(self, environment: dict | None = None) -> dict:
        return run_office(self.path, "check", "pages/01.html", environment=environment or environment_with_context(self.context))

    def test_a_check_judges_the_decks_claims_against_the_request_once_per_draft(self):
        with FakeHost(decide=judging_invented) as host:
            first = self.check_page()
            self.check_page()
        asked = host.requests_to("decide")
        self.assertEqual(len(asked), 1)
        texts = [claim["text"] for claim in asked[0]["state"]["claims"].values()]
        self.assertIn(INVENTED, texts)
        self.assertIn("A sample deck for the tests", texts)
        self.assertEqual(asked[0]["state"]["request"], "Make a deck about the sample")
        self.assertIn("UNSUPPORTED_CLAIM", self.codes(first))

    def test_a_host_without_a_script_host_judges_nothing(self):
        envelope = self.check_page()
        self.assertNotIn("UNSUPPORTED_CLAIM", self.codes(envelope))
        self.assertFalse((self.state / "draft-claims.json").exists())

    def test_a_unit_judged_unsupported_is_refused_once_with_its_text(self):
        with FakeHost(decide=judging_invented):
            first = self.check_page()
            again = self.check_page()
        refusal = next(issue for issue in first["issues"] if issue["code"] == "UNSUPPORTED_CLAIM")
        self.assertEqual(refusal["severity"], "error")
        self.assertEqual(refusal["location"], "page 1")
        self.assertIn(INVENTED, refusal["message"])
        self.assertNotIn("UNSUPPORTED_CLAIM", self.codes(again))
        self.assertTrue((self.state / "draft-claims-reported.json").exists())

    def test_a_unit_that_was_restated_is_not_refused(self):
        self.state.mkdir(parents=True)
        (self.state / "draft-claims.json").write_text(json.dumps({"digest": "x", "unsupported": [{"path": "slides[0].units[2]", "at": "slide 1 text", "text": "A sentence no longer in the deck."}]}), encoding="utf-8")
        envelope = run_office(self.path, "create", "build/deck.pdf", ".", environment=environment_with_context(self.context) | self.unanswering_host())
        self.assertNotIn("UNSUPPORTED_CLAIM", self.codes(envelope))

    def test_a_build_refuses_only_what_the_last_check_judged_and_asks_nothing_new(self):
        self.state.mkdir(parents=True)
        (self.state / "draft-claims.json").write_text(json.dumps({"digest": "x", "unsupported": [{"path": "slides[0].units[2]", "at": "slide 1 text", "text": INVENTED}]}), encoding="utf-8")
        with FakeHost(decide=judging_invented) as host:
            envelope = run_office(self.path, "create", "build/deck.pdf", ".", environment=environment_with_context(self.context))
        self.assertIn("UNSUPPORTED_CLAIM", self.codes(envelope))
        self.assertEqual(host.requests, [])

    def test_a_remake_that_blanks_values_is_not_refused_for_the_claims_it_is_blanking(self):
        self.state.mkdir(parents=True)
        (self.state / "draft-claims.json").write_text(json.dumps({"digest": "x", "unsupported": [{"path": "slides[0].units[2]", "at": "slide 1 text", "text": INVENTED}]}), encoding="utf-8")
        with FakeHost(decide=judging_invented):
            envelope = run_office(self.path, "create", "build/deck.pdf", ".", "--blank", "slides[0].units[2]", environment=environment_with_context(self.context))
        self.assertNotIn("UNSUPPORTED_CLAIM", self.codes(envelope))


if __name__ == "__main__":
    unittest.main()
