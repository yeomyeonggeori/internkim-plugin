from pathlib import Path
import sys
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "deck"
sys.path.insert(0, str(SCRIPTS_PATH.parent))

from deck.slide_model import create_slide_models  # noqa: E402
from deck.slide_structure import inspect_slide_structure  # noqa: E402


CARD_SLIDE = (
    '<section class="slide"><h2>세 지표가 목표를 넘었습니다</h2>'
    '<div class="card"><h3>월평균 처리량은 4,160건으로 지난 분기보다 늘었습니다</h3></div></section>'
)


class SlideTitleTest(unittest.TestCase):
    def test_export_and_review_take_the_first_heading(self):
        exported_title = create_slide_models([CARD_SLIDE])[0].title
        reviewed_title = inspect_slide_structure(CARD_SLIDE)["title"]
        self.assertEqual(exported_title, "세 지표가 목표를 넘었습니다")
        self.assertEqual(reviewed_title, exported_title)


if __name__ == "__main__":
    unittest.main()
