from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))

from deck.deck_claims import blanked_deck, deck_claims
from deck.deck_holds import deck_slides
from delivery.delivered_metadata import holds_of

DECK = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>견본로보틱스 시리즈 A</title></head>
<body>
<section>
  <p class="eyebrow">시리즈 A 투자 제안서</p>
  <h1>견본로보틱스: 창고 로봇을 <em>월 구독</em>으로</h1>
  <aside class="notes">대표가 소개합니다.</aside>
</section>
<section>
  <h2>2026년에 흑자로 전환합니다</h2>
  <table>
    <tr><th>구분 (백만 원)</th><th>2025</th><th>2026E</th></tr>
    <tr class="pick"><td>영업이익</td><td>-310</td><td>920</td></tr>
  </table>
  <p class="takeaway">손실 폭이 줄었습니다.</p>
</section>
<section>
  <h2>자금은 연구개발에 가장 많이 씁니다</h2>
  <figure data-chart="donut" data-labels="연구개발, 영업, 운영" data-values="45, 30, 25" data-unit="%"><figcaption>단위: %</figcaption></figure>
  <div class="card"><i data-icon="mail"></i><h3>문의</h3><p>ir@example.com</p></div>
</section>
</body>
</html>
"""


class DeckHoldsTest(unittest.TestCase):
    def test_each_slide_holds_its_title_text_tables_charts_and_icons_in_order(self):
        self.assertEqual(deck_slides(DECK), [
            {"slide": 1, "title": "견본로보틱스: 창고 로봇을 월 구독으로", "text": ["시리즈 A 투자 제안서"]},
            {"slide": 2, "title": "2026년에 흑자로 전환합니다", "text": ["손실 폭이 줄었습니다."],
             "tables": [[["구분 (백만 원)", "2025", "2026E"], ["영업이익", "-310", "920"]]]},
            {"slide": 3, "title": "자금은 연구개발에 가장 많이 씁니다", "text": ["단위: %", "문의", "ir@example.com"],
             "charts": [{"type": "donut", "labels": ["연구개발", "영업", "운영"], "values": ["45", "30", "25"], "unit": "%"}], "icons": ["mail"]},
        ])

    def test_a_chart_keeps_grouped_numbers_whole(self):
        grouped = DECK.replace('data-values="45, 30, 25"', 'data-values="3,100, 3,500, 4,200"')
        self.assertEqual(deck_slides(grouped)[2]["charts"][0]["values"], ["3,100", "3,500", "4,200"])

    def test_a_blanked_value_is_absent_and_a_blanked_title_stays_empty(self):
        paths = [claim["path"] for claim in deck_claims(DECK) if claim["text"] in ("2026년에 흑자로 전환합니다", "920", "손실 폭이 줄었습니다.")]
        slide = deck_slides(blanked_deck(DECK, paths))[1]
        self.assertEqual(slide["title"], "")
        self.assertNotIn("text", slide)
        self.assertEqual(slide["tables"], [[["구분 (백만 원)", "2025", "2026E"], ["영업이익", "-310", ""]]])

    def test_a_deck_snapshot_holds_its_slides_and_blanks_and_nothing_else(self):
        snapshot = {"command": "office create", "deck": "/deck", "claims": deck_claims(DECK), "slides": deck_slides(DECK), "blanks": [{"field": "f", "label": "l"}]}
        self.assertEqual(holds_of(snapshot), {"slides": deck_slides(DECK), "blanks": [{"field": "f", "label": "l"}]})

    def test_a_snapshot_holding_only_its_blanks_holds_nothing(self):
        self.assertEqual(holds_of({"command": "office create", "blanks": []}), {})


if __name__ == "__main__":
    unittest.main()
