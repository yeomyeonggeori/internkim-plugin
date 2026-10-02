from pathlib import Path
import sys
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "deck"
sys.path.insert(0, str(SCRIPTS_PATH.parent))

from deck.slide_structure import inspect_slide_structure  # noqa: E402


CARD_SLIDE = (
    '<section class="slide"><h2>세 지표가 목표를 넘었습니다</h2>'
    '<div class="card"><h3>월평균 처리량은 4,160건으로 지난 분기보다 늘었습니다</h3></div></section>'
)


class SlideTitleTest(unittest.TestCase):
    def test_the_review_takes_the_first_heading(self):
        self.assertEqual(inspect_slide_structure(CARD_SLIDE)["title"], "세 지표가 목표를 넘었습니다")


if __name__ == "__main__":
    unittest.main()
