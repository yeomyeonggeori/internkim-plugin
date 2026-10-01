from pathlib import Path
import sys
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "deck"
sys.path.insert(0, str(SCRIPTS_PATH.parent))

from deck.content_warnings import apply_missing_speaker_notes_warning  # noqa: E402
from deck.slide_model import create_slide_models, extract_notes  # noqa: E402
from deck.slide_structure import visible_slide_text  # noqa: E402


FOOTNOTE_SLIDE = '<section><h2>매출이 늘었습니다</h2><p>본문</p><div class="footnotes">출처 내부 자료</div></section>'
SIDEBAR_SLIDE = '<section><h2>인력이 늘었습니다</h2><p>본문</p><aside class="footnotes">출처 인사팀</aside></section>'
NOTES_SLIDE = '<section><h2>비용이 줄었습니다</h2><p>본문</p><aside class="notes lead">발표 노트</aside></section>'


class SpeakerNotesTest(unittest.TestCase):
    def test_a_footnote_stays_visible_text(self):
        self.assertIn("출처 내부 자료", create_slide_models([FOOTNOTE_SLIDE])[0].lines)
        self.assertIn("출처 내부 자료", visible_slide_text(FOOTNOTE_SLIDE))
        self.assertEqual(extract_notes(FOOTNOTE_SLIDE), "")

    def test_the_notes_class_marks_speaker_notes(self):
        self.assertEqual(extract_notes(NOTES_SLIDE), "발표 노트")
        self.assertNotIn("발표 노트", visible_slide_text(NOTES_SLIDE))

    def test_missing_notes_warning_ignores_footnotes(self):
        slides = [{"warnings": []}, {"warnings": []}]
        apply_missing_speaker_notes_warning(slides, SIDEBAR_SLIDE + NOTES_SLIDE)
        self.assertEqual(len(slides[0]["warnings"]), 1)
        self.assertIn("slide 1 lacks", slides[0]["warnings"][0].message)


if __name__ == "__main__":
    unittest.main()
