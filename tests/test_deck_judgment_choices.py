import json
from pathlib import Path
import unittest


REVIEW_DEFINITION = json.loads((Path(__file__).resolve().parents[1] / "skills" / "office" / "assets" / "deck-kit" / "visual-review.json").read_text(encoding="utf-8"))
JUDGMENT_PATTERNS = ("hero_metric_template", "rough_illustration", "monotonous_spacing", "fake_sequence_numbering")
ARRANGEMENT_DEFECTS = ("overlap", "weak_hierarchy", "cramped", "wasted_space", "misaligned", "unbalanced")
DECK_DEFECTS = ("repetitive_layout", "inconsistent_style")
DECK_QUESTION = REVIEW_DEFINITION["deck"]


class JudgmentChoiceTest(unittest.TestCase):
    def test_the_visual_choice_carries_each_judgment_pattern_and_none(self):
        options = REVIEW_DEFINITION["question"]["options"]
        self.assertIn("none", options)
        for pattern in JUDGMENT_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertTrue(options[pattern].strip())

    def test_the_slide_question_names_each_way_an_arrangement_hides_its_message(self):
        options = REVIEW_DEFINITION["question"]["options"]
        for defect in ARRANGEMENT_DEFECTS:
            with self.subTest(defect=defect):
                self.assertTrue(options[defect].strip())
        for merged in ("crowded", "imbalanced_layout"):
            self.assertNotIn(merged, options)

    def test_the_slide_question_defines_poor_design_once_and_leaves_taste_alone(self):
        instructions = REVIEW_DEFINITION["question"]["instructions"]
        self.assertIn("harder to find or read than the content requires", instructions)
        self.assertIn("taste", instructions)
        self.assertIn("consistently applied", instructions)

    def test_the_deck_question_names_repetition_and_inconsistency_and_none(self):
        options = DECK_QUESTION["options"]
        self.assertEqual(set(options), {"none", *DECK_DEFECTS})
        self.assertEqual(DECK_QUESTION["cleanOption"], "none")
        for defect in DECK_DEFECTS:
            self.assertTrue(options[defect].strip())

    def test_the_deck_question_pairs_each_check_with_a_rule_against_inventing(self):
        self.assertIn("Do not invent defects", DECK_QUESTION["instructions"])
        self.assertIn("Choose none", DECK_QUESTION["instructions"])

    def test_the_deck_question_shares_no_defect_with_the_slide_question(self):
        shared = set(DECK_QUESTION["options"]) & set(REVIEW_DEFINITION["question"]["options"])
        self.assertEqual(shared, {"none"})

    def test_the_fixer_is_told_what_a_refusal_of_its_last_rewrite_means(self):
        self.assertIn("refusedLastTime", REVIEW_DEFINITION["fixer"]["instructions"])

    def test_the_fixer_is_told_what_to_do_with_a_deck_finding(self):
        instructions = REVIEW_DEFINITION["fixer"]["instructions"]
        for defect in DECK_DEFECTS:
            self.assertIn(defect, instructions)

    def test_a_pattern_threshold_names_a_defect_option_and_sits_between_zero_and_one(self):
        options = {**REVIEW_DEFINITION["question"]["options"], **DECK_QUESTION["options"]}
        for pattern, threshold in REVIEW_DEFINITION["patternThresholds"].items():
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, options)
                self.assertNotEqual(pattern, REVIEW_DEFINITION["question"]["cleanOption"])
                self.assertTrue(0 < threshold < 1)

    def test_each_option_calibrated_on_recorded_renders_has_its_own_threshold(self):
        thresholds = REVIEW_DEFINITION["patternThresholds"]
        for option in ("overlap", "wasted_space", "unbalanced", "fake_sequence_numbering", "repetitive_layout"):
            with self.subTest(option=option):
                self.assertIn(option, thresholds)

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

    def test_the_fixer_chooses_among_edits_and_writes_no_markup(self):
        instructions = REVIEW_DEFINITION["fixer"]["instructions"]
        self.assertIn("Choose from edits only", instructions)
        self.assertIn("Do not write markup", instructions)
        self.assertNotIn("Return the whole <section>", instructions)


if __name__ == "__main__":
    unittest.main()
