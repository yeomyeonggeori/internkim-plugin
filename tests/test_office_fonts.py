from pathlib import Path
import sys
import unittest


OFFICE_SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(OFFICE_SCRIPTS_PATH))
sys.path.insert(0, str(OFFICE_SCRIPTS_PATH / "deck"))

from native_preview import preview_font_candidates  # noqa: E402
from skill_runtime import HANGUL_FONT_PATHS  # noqa: E402


class KoreanFontListTest(unittest.TestCase):
    def test_deck_previews_search_the_shared_korean_font_list_first(self):
        for is_bold in (False, True):
            candidates = preview_font_candidates(is_bold)
            self.assertEqual(candidates[:len(HANGUL_FONT_PATHS)], HANGUL_FONT_PATHS)
            self.assertEqual(len(candidates), len(HANGUL_FONT_PATHS) + 1)


if __name__ == "__main__":
    unittest.main()
