from pathlib import Path
import sys
import unittest

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))
sys.path.insert(0, str(SCRIPTS_PATH / "deck"))

from fetch_image import candidate_path, no_image_issue, save_candidates  # noqa: E402


class ImageCandidateTest(unittest.TestCase):
    def test_candidates_sit_beside_the_requested_path(self):
        output = Path("images/shelves.jpg")
        self.assertEqual([candidate_path(output, position) for position in (1, 2, 3)], [output, Path("images/shelves-2.jpg"), Path("images/shelves-3.jpg")])

    def test_a_korean_query_that_finds_nothing_is_told_to_search_in_english(self):
        self.assertIn("concrete English scene", no_image_issue("물류 창고").suggestion)
        self.assertNotIn("concrete English scene", no_image_issue("warehouse").suggestion)

    def test_results_without_a_url_save_nothing(self):
        self.assertEqual(save_candidates([{"title": "no url"}], Path("images/x.jpg"), 3), [])


if __name__ == "__main__":
    unittest.main()
