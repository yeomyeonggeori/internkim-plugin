from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))

from deck.deck_claims import blanked_deck, deck_claims
from schemas.blank_paths import blanked, replacement_map
from test_deck_claims import DECK


class ReplaceClaimTest(unittest.TestCase):
    def test_a_replacement_names_its_path_and_keeps_an_equals_sign_in_its_text(self):
        self.assertEqual(replacement_map(["sections[0].title=A=B"]), {"sections[0].title": "A=B"})

    def test_a_replacement_without_a_path_is_refused(self):
        with self.assertRaises(ValueError):
            replacement_map(["no separator"])

    def test_a_value_is_replaced_in_place(self):
        values = {"sections": [{"title": "Intro", "text": "One. Two. Three."}]}
        result = blanked(values, [], {"sections[0].title": "Overview"})
        self.assertEqual(result["sections"][0]["title"], "Overview")
        self.assertEqual(values["sections"][0]["title"], "Intro")

    def test_a_sentence_is_replaced_and_the_others_keep_their_places_beside_a_blank(self):
        values = {"sections": [{"text": "One. Two. Three."}]}
        result = blanked(values, ["sections[0].text#2"], {"sections[0].text#0": "First."})
        self.assertEqual(result["sections"][0]["text"], "First. Two.")

    def test_a_path_that_is_not_there_is_ignored(self):
        values = {"a": "x"}
        self.assertEqual(blanked(values, [], {"b[3].c": "y"}), values)

    def test_a_deck_sentence_is_replaced_and_the_rest_of_its_paragraph_stays(self):
        lead = next(claim for claim in deck_claims(DECK) if claim["text"].startswith("검증된 수요"))
        result = blanked_deck(DECK, [], {lead["path"]: "수요는 계약으로 확인했습니다."})
        self.assertIn("수요는 계약으로 확인했습니다. 2025년 흑자를 달성했습니다.", result)
        self.assertNotIn("검증된 수요", result)

    def test_a_deck_title_is_replaced_whole_and_stays_a_title(self):
        title = next(claim for claim in deck_claims(DECK) if claim["text"].startswith("50억으로"))
        result = blanked_deck(DECK, [], {title["path"]: "다음 성장 계획"})
        self.assertIn("<h2>다음 성장 계획</h2>", result)

    def test_a_replacement_is_escaped_as_text(self):
        title = next(claim for claim in deck_claims(DECK) if claim["text"].startswith("50억으로"))
        result = blanked_deck(DECK, [], {title["path"]: "A <b> & B"})
        self.assertIn("A &lt;b&gt; &amp; B", result)


if __name__ == "__main__":
    unittest.main()
