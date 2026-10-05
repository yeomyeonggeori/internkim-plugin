import json
from pathlib import Path
import unittest


REVIEW_DEFINITION = json.loads((Path(__file__).resolve().parents[1] / "skills" / "office" / "assets" / "deck-kit" / "visual-review.json").read_text(encoding="utf-8"))
OBJECTIVE_DEFECTS = {"overlap", "cramped", "wasted_space", "misaligned", "unreadable_chart", "poor_image_or_icon_use"}
DECK_DEFECTS = ("repetitive_layout",)
DECK_QUESTION = REVIEW_DEFINITION["deck"]


class JudgmentChoiceTest(unittest.TestCase):
    def test_each_slide_is_asked_only_about_defects_a_render_shows_plainly(self):
        options = REVIEW_DEFINITION["question"]["options"]
        self.assertEqual(set(options), {"none", *OBJECTIVE_DEFECTS})
        for defect in OBJECTIVE_DEFECTS:
            with self.subTest(defect=defect):
                self.assertTrue(options[defect].strip())

    def test_the_slide_question_leaves_taste_hierarchy_and_balance_alone(self):
        instructions = REVIEW_DEFINITION["question"]["instructions"]
        for judgment in ("taste", "hierarchy", "balance"):
            self.assertIn(judgment, instructions.split("Do not invent defects")[1])

    def test_the_deck_question_names_only_repetition_and_none(self):
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
        for option in ("overlap", "wasted_space", "repetitive_layout"):
            with self.subTest(option=option):
                self.assertIn(option, thresholds)

    def test_a_chosen_composition_such_as_one_huge_number_is_not_a_defect(self):
        self.assertNotIn("hero_metric_template", REVIEW_DEFINITION["question"]["options"])
        self.assertIn("one huge number", REVIEW_DEFINITION["question"]["instructions"])

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

    def test_the_fixer_rewrites_the_page_section_and_keeps_a_clean_page(self):
        instructions = REVIEW_DEFINITION["fixer"]["instructions"]
        self.assertIn("Answer with the whole corrected <section>", instructions)
        self.assertIn("Keep the copy, the facts, the palette and the composition", instructions)
        self.assertIn("do not redesign a page that is clean", instructions)
        self.assertIn("add no words, numbers or claims of your own", instructions)

    def test_the_fixer_recomposes_a_page_the_claim_check_emptied(self):
        self.assertIn("When recompose is true", REVIEW_DEFINITION["fixer"]["instructions"])

    def test_the_review_allows_at_most_two_fix_rounds(self):
        self.assertEqual(REVIEW_DEFINITION["rounds"], 2)


if __name__ == "__main__":
    unittest.main()
