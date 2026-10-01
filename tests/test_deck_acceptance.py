import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))
sys.path.insert(0, str(SCRIPTS_PATH / "deck"))

from acceptance import FIX_ROUNDS_ALLOWED, judge_build  # noqa: E402
from deck_definitions import MISSING_SPEAKER_NOTES, TEXT_OVERLAP  # noqa: E402
from render_fixture import can_render  # noqa: E402


OVERLAP = TEXT_OVERLAP.issue("two text blocks cover each other", "slide 3")
NO_NOTES = MISSING_SPEAKER_NOTES.issue("slide 8 has no speaker notes", "slide 8")


class AcceptanceTest(unittest.TestCase):
    def judge(self, build_path: Path, source: str, issues: list, measured: bool = True):
        return judge_build(build_path, source, issues, str(build_path / "deck.pdf"), measured)

    def test_advice_alone_is_acceptable_and_says_not_to_redesign(self):
        with tempfile.TemporaryDirectory() as directory:
            acceptance = self.judge(Path(directory), "<section>a</section>", [NO_NOTES])
        self.assertTrue(acceptance.acceptable)
        self.assertTrue(acceptance.verdict.startswith("ACCEPTABLE"))
        self.assertIn("do not redesign", acceptance.verdict)

    def test_an_objective_defect_opens_a_fix_round_that_names_it(self):
        with tempfile.TemporaryDirectory() as directory:
            acceptance = self.judge(Path(directory), "<section>a</section>", [OVERLAP, NO_NOTES])
        self.assertFalse(acceptance.acceptable)
        self.assertTrue(acceptance.verdict.startswith(f"FIX ROUND 1 OF {FIX_ROUNDS_ALLOWED}"))
        self.assertIn("TEXT_OVERLAP on slide 3", acceptance.verdict)
        self.assertNotIn("MISSING_SPEAKER_NOTES", acceptance.verdict)

    def test_fixing_stops_after_the_allowed_rounds_and_a_rebuild_of_one_source_is_not_a_round(self):
        with tempfile.TemporaryDirectory() as directory:
            build_path = Path(directory)
            rounds = [self.judge(build_path, f"<section>version {number}</section>", [OVERLAP]) for number in range(FIX_ROUNDS_ALLOWED + 1)]
            repeated = self.judge(build_path, f"<section>version {FIX_ROUNDS_ALLOWED}</section>", [OVERLAP])
        self.assertEqual([acceptance.fix_round for acceptance in rounds], list(range(FIX_ROUNDS_ALLOWED + 1)))
        self.assertTrue(rounds[-1].verdict.startswith("STOP FIXING"))
        self.assertEqual(repeated.fix_round, FIX_ROUNDS_ALLOWED)

    def test_rounds_count_fixes_since_the_last_acceptable_build_not_all_history(self):
        with tempfile.TemporaryDirectory() as directory:
            build_path = Path(directory)
            clean = [self.judge(build_path, f"<section>accepted {number}</section>", []) for number in range(3)]
            defective = self.judge(build_path, "<section>user edit with an overlap</section>", [OVERLAP])
        self.assertTrue(all(acceptance.acceptable for acceptance in clean))
        self.assertEqual(defective.fix_round, 0)
        self.assertTrue(defective.verdict.startswith(f"FIX ROUND 1 OF {FIX_ROUNDS_ALLOWED}"))

    def test_a_change_after_fixing_stopped_starts_new_rounds(self):
        with tempfile.TemporaryDirectory() as directory:
            build_path = Path(directory)
            for number in range(FIX_ROUNDS_ALLOWED + 1):
                self.judge(build_path, f"<section>attempt {number}</section>", [OVERLAP])
            next_request = self.judge(build_path, "<section>the user's next change</section>", [OVERLAP])
        self.assertEqual(next_request.fix_round, 0)

    def test_an_unmeasured_build_is_never_called_acceptable(self):
        with tempfile.TemporaryDirectory() as directory:
            acceptance = self.judge(Path(directory), "<section>a</section>", [], measured=False)
        self.assertFalse(acceptance.acceptable)
        self.assertTrue(acceptance.verdict.startswith("NOT MEASURED"))


FREE_HTML_DECK = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>자유 형식</title>
<style>section{width:1600px;height:900px;padding:80px;box-sizing:border-box;font-family:sans-serif;background:#fff} h1{font-size:64px} td{font-size:12px}</style></head><body>
<section><h1>지역별 매출이 늘었습니다</h1><table><tr><td>수도권</td><td>58억</td></tr><tr><td>영남</td><td>31억</td></tr></table></section>
</body></html>"""


class FreeHtmlGateTest(unittest.TestCase):
    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_a_deck_without_the_kit_is_held_to_the_measured_bar(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "slides.html").write_text(FREE_HTML_DECK, encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build"], capture_output=True, text=True, cwd=directory)
            acceptance = json.loads(completed.stdout)["details"]["acceptance"]
        self.assertFalse(acceptance["acceptable"])
        self.assertTrue(acceptance["verdict"].startswith("FIX ROUND 1"))
        self.assertTrue({"TINY_TEXT", "VERTICAL_DEAD_ZONE"} <= {defect["code"] for defect in acceptance["defects"]})


class BuildHelpTest(unittest.TestCase):
    def test_help_prints_usage_and_never_builds(self):
        for verb in ("build", "image"):
            with self.subTest(verb), tempfile.TemporaryDirectory() as directory:
                completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", verb, "--help"], capture_output=True, text=True, cwd=directory)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("usage:", completed.stdout)
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_an_unknown_format_is_refused_before_anything_renders(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "slides.html").write_text('<body data-theme="editorial"><section data-layout="statement"><h2>배송이 빨라집니다</h2></section></body>', encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build", "--format", "keynote"], capture_output=True, text=True, cwd=directory)
            envelope = json.loads(completed.stdout)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("UNKNOWN_FORMAT", {issue["code"] for issue in envelope["issues"]})
            self.assertFalse((Path(directory) / "build").exists())


if __name__ == "__main__":
    unittest.main()
