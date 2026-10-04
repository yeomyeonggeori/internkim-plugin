import json
from pathlib import Path
import unittest


REVIEW_DEFINITION = json.loads((Path(__file__).resolve().parents[1] / "skills" / "office" / "assets" / "deck-kit" / "visual-review.json").read_text(encoding="utf-8"))
JUDGMENT_PATTERNS = ("hero_metric_template", "rough_illustration", "monotonous_spacing", "fake_sequence_numbering")


class JudgmentChoiceTest(unittest.TestCase):
    def test_the_visual_choice_carries_each_judgment_pattern_and_none(self):
        options = REVIEW_DEFINITION["question"]["options"]
        self.assertIn("none", options)
        for pattern in JUDGMENT_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertTrue(options[pattern].strip())

    def test_a_pattern_threshold_names_a_defect_option_and_sits_between_zero_and_one(self):
        options = REVIEW_DEFINITION["question"]["options"]
        for pattern, threshold in REVIEW_DEFINITION["patternThresholds"].items():
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, options)
                self.assertNotEqual(pattern, REVIEW_DEFINITION["question"]["cleanOption"])
                self.assertTrue(0 < threshold < REVIEW_DEFINITION["threshold"])

    def test_the_stat_hero_template_is_flagged_below_the_score_the_one_slide_that_showed_it_earned(self):
        self.assertLessEqual(REVIEW_DEFINITION["patternThresholds"]["hero_metric_template"], 0.27)

    def test_the_clean_option_is_none(self):
        self.assertEqual(REVIEW_DEFINITION["question"]["cleanOption"], "none")

    def test_the_question_pairs_each_check_with_a_rule_against_inventing(self):
        instructions = REVIEW_DEFINITION["question"]["instructions"]
        self.assertIn("Do not invent defects", instructions)
        self.assertIn("Choose none", instructions)

    def test_no_option_still_names_a_template_or_a_theme(self):
        text = json.dumps(REVIEW_DEFINITION).lower()
        for word in ("data-layout", "theme", "kit"):
            self.assertNotIn(word, text)

    def test_the_fixer_is_told_never_to_add_a_pattern_the_build_refuses(self):
        self.assertIn("Never add a pattern the build refuses", REVIEW_DEFINITION["fixer"]["instructions"])


if __name__ == "__main__":
    unittest.main()
