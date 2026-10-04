from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))

from deck.deck_claims import blank_labels, blanked_deck, deck_claims

DECK = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>견본테크 투자 제안</title></head>
<body data-theme="corporate">
<section data-layout="cover">
  <h1>견본테크, 3년 만에 매출 <em>4.5배</em></h1>
  <p class="lead">검증된 수요 위에서 성장합니다. 2025년 흑자를 달성했습니다.</p>
  <aside class="notes">매출 10억에서 45억.</aside>
</section>
<section data-layout="chart">
  <h2>매출이 3년 연속 늘었습니다</h2>
  <figure data-chart="column" data-labels="2023, 2024, 2025" data-values="10, 21, 45" data-unit="억"><figcaption>연도별 매출</figcaption></figure>
  <div class="insight"><p class="value">92%</p><p>재계약률</p></div>
</section>
<section data-layout="closing">
  <h2>50억으로 다음 성장을 엽니다</h2>
  <ol><li>R&amp;D 30억</li><li>국내 시장 점유율 1위</li></ol>
  <table><tr><th>용도</th><td>영업 20억</td></tr></table>
</section>
</body>
</html>
"""


def claim_at(text):
    return next(claim for claim in deck_claims(DECK) if claim["text"] == text)


class DeckClaimTest(unittest.TestCase):
    def test_every_written_unit_is_a_claim_and_speaker_notes_are_not(self):
        texts = [claim["text"] for claim in deck_claims(DECK)]
        self.assertIn("견본테크, 3년 만에 매출 4.5배", texts)
        self.assertIn("2025년 흑자를 달성했습니다.", texts)
        self.assertIn("column chart: 2023 10억, 2024 21억, 2025 45억", texts)
        self.assertIn("92%", texts)
        self.assertIn("영업 20억", texts)
        self.assertNotIn("매출 10억에서 45억.", texts)

    def test_a_claim_names_its_slide_and_role_in_the_deck_language(self):
        self.assertEqual(claim_at("92%")["at"], "슬라이드 2 수치")
        self.assertEqual(claim_at("국내 시장 점유율 1위")["at"], "슬라이드 3 항목")

    def test_a_blank_sentence_leaves_the_rest_of_its_paragraph(self):
        result = blanked_deck(DECK, [claim_at("2025년 흑자를 달성했습니다.")["path"]])
        self.assertIn('<p class="lead">검증된 수요 위에서 성장합니다.</p>', result)

    def test_a_blank_item_is_removed_and_a_title_value_or_cell_keeps_its_frame(self):
        paths = [claim_at(text)["path"] for text in ("국내 시장 점유율 1위", "92%", "영업 20억", "50억으로 다음 성장을 엽니다")]
        result = blanked_deck(DECK, paths)
        self.assertIn("<ol><li>R&amp;D 30억</li></ol>", result)
        self.assertIn('<p class="value"></p>', result)
        self.assertIn("<td></td>", result)
        self.assertIn("<h2></h2>", result)

    def test_an_unsupported_chart_takes_its_slide_with_it(self):
        paths = [claim_at("column chart: 2023 10억, 2024 21억, 2025 45억")["path"], claim_at("92%")["path"]]
        result = blanked_deck(DECK, paths)
        self.assertNotIn('data-layout="chart"', result)
        self.assertEqual(result.count("<section"), 2)
        self.assertIn("국내 시장 점유율 1위", result)

    def test_each_blank_is_listed_with_its_place(self):
        path = claim_at("92%")["path"]
        self.assertEqual(blank_labels(DECK, [path]), [{"field": path, "label": "슬라이드 2 수치"}])


if __name__ == "__main__":
    unittest.main()
