import json
import os
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

from core.host_contract import HOST_CONTRACT, RUNTIME_CONTEXT_VARIABLE  # noqa: E402

REQUEST_FILE = HOST_CONTRACT["draftClaims"]["requestFile"]
REPORTED_FILE = HOST_CONTRACT["draftClaims"]["reportedFile"]
INVENTED = "Churn fell to 1.2 percent after the pilot."
SLIDES = [f"{HEADING}{BODY}<p>{INVENTED}</p>"]


def write_context(directory: Path, judges: bool, unsupported: list[dict] | None = None) -> Path:
    context = {"requester": {"name": "", "email": ""}, "today": "2026-10-04", "company": {}, "registeredDocuments": [], "attachments": [], "reviewsDeckRenders": False, "judgesDraftClaims": judges}
    if unsupported is not None:
        context["draftClaims"] = {"digest": "x", "unsupported": unsupported}
    path = directory / "context" / "office-runtime-context.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(context), encoding="utf-8")
    return path


def run_office(directory: Path, context: Path, *arguments: str) -> dict:
    environment = {**os.environ, RUNTIME_CONTEXT_VARIABLE: str(context)}
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=directory, env=environment)
    return json.loads(completed.stdout)


@unittest.skipUnless(can_render(), "the renderer is not available")
class DraftClaimsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)
        write_staged_deck(self.path, SLIDES)
        self.addCleanup(self.directory.cleanup)

    def flagged(self) -> list[dict]:
        return [{"path": "slides[0].units[2]", "at": "slide 1 text", "text": INVENTED}]

    def codes(self, envelope: dict) -> list[str]:
        return [issue["code"] for issue in envelope["issues"]]

    def test_a_check_writes_the_decks_claims_for_the_host_to_judge(self):
        context = write_context(self.path, True)
        run_office(self.path, context, "check", "pages/01.html")
        request = json.loads((context.parent / REQUEST_FILE).read_text(encoding="utf-8"))
        texts = {claim["path"]: claim["text"] for claim in request["claims"]}
        self.assertIn(INVENTED, texts.values())
        self.assertEqual(texts["outline.core_hook"], "A sample deck for the tests")
        self.assertIn(INVENTED, texts["outline.pages[0].brief[0]"])

    def test_a_host_that_does_not_judge_drafts_gets_no_request(self):
        context = write_context(self.path, False)
        run_office(self.path, context, "check", "pages/01.html")
        self.assertFalse((context.parent / REQUEST_FILE).exists())

    def test_a_unit_the_host_judged_unsupported_is_refused_once_with_its_text(self):
        context = write_context(self.path, True, self.flagged())
        first = run_office(self.path, context, "check", "pages/01.html")
        again = run_office(self.path, context, "check", "pages/01.html")
        refusal = next(issue for issue in first["issues"] if issue["code"] == "UNSUPPORTED_CLAIM")
        self.assertEqual(refusal["severity"], "error")
        self.assertEqual(refusal["location"], "page 1")
        self.assertIn(INVENTED, refusal["message"])
        self.assertNotIn("UNSUPPORTED_CLAIM", self.codes(again))
        self.assertTrue((context.parent / REPORTED_FILE).exists())

    def test_a_unit_that_was_restated_is_not_refused(self):
        context = write_context(self.path, True, [{"path": "slides[0].units[2]", "at": "slide 1 text", "text": "A sentence no longer in the deck."}])
        self.assertNotIn("UNSUPPORTED_CLAIM", self.codes(run_office(self.path, context, "check", "pages/01.html")))

    def test_a_remake_that_blanks_values_is_not_refused_for_the_claims_it_is_blanking(self):
        context = write_context(self.path, True, self.flagged())
        envelope = run_office(self.path, context, "create", "build/deck.pdf", ".", "--blank", "slides[0].units[2]")
        self.assertNotIn("UNSUPPORTED_CLAIM", self.codes(envelope))


if __name__ == "__main__":
    unittest.main()
