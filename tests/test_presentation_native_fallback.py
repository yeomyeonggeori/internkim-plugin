import html
import html.parser
from pathlib import Path
import re
import sys
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "presentation" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from native_pptx import native_slide_xml  # noqa: E402
from slide_model import create_slide_models  # noqa: E402
from slide_source import split_slide_sources  # noqa: E402


TOKEN_SEPARATORS = r"[\s:：·/|,.()\[\]]+"
BOARD_DECK = """
<section data-slide-role="cover"><h1>이샘플 주식회사 3분기 운영 보고</h1><p>매출 12억</p><p>제공된 자료 없음</p></section>
<section data-slide-role="summary"><h2>Executive Summary</h2><p>성과:</p><p>과제:</p><p>매출 목표 달성</p><p>결함 미달</p></section>
<section data-slide-role="metrics"><h2>Metrics against target</h2><table>
<tr><th>Metric</th><th>Q1 2026</th><th>Q2 2026</th><th>Target</th><th>Note</th></tr>
<tr><td>Revenue</td><td>10</td><td>12</td><td>11</td><td>met</td></tr>
<tr><td>Uptime</td><td>99.1</td><td>98.2</td><td>99.5</td><td>miss</td></tr>
</table></section>
<section data-slide-role="risk"><h2>Risks</h2><table><tr><th>Risk</th><th>Evidence</th><th>Response</th></tr>
<tr><td>Defect rate</td><td>3%</td><td>QA sprint</td></tr></table></section>
<section data-slide-role="approval"><h2>Next steps</h2><p>Approve budget</p><p>Hire two engineers</p><p>Review in October</p></section>
"""
PLAN_DECK = """
<section data-slide-role="title"><h1>Roadmap for the launch</h1></section>
<section data-slide-role="timeline"><h2>Roadmap milestones</h2><table><tr><th>Phase</th><th>Date</th><th>Owner</th></tr>
<tr><td>Pilot</td><td>2026-08-01</td><td>박예시</td></tr><tr><td>Launch</td><td>2026-09-15</td><td>최견본</td></tr></table></section>
<section data-slide-role="timeline"><h2>Timeline without dates</h2><ol><li>first step</li><li>second step</li></ol></section>
<section data-slide-role="risk"><h2>리스크와 대응</h2><p>공급 지연</p><p>증거:</p><p>입고 2주 지연</p></section>
<section data-slide-role="summary"></section>
<section data-slide-role="metrics"><h2>Metric with one row</h2><table><tr><th>Only</th><th>Header</th></tr></table></section>
"""
ROLE_DECK = """
<section><h1>Quarterly summary and approval</h1><p>Risks on the roadmap, metrics against target</p></section>
<section data-slide-role=" Timeline "><h2>Plain words only</h2></section>
<section class="risk summary" data-slide-role="thesis"><h2>Executive summary</h2><p>Approve the risk response</p></section>
<section data-slide-role="metrics"><h2>Nothing numeric</h2></section>
<section><h2>Next steps and approval</h2><p>Roadmap milestone 2026-08-12</p></section>
"""
NATIVE_LAYOUT_KINDS = {"cover", "summary", "metrics", "timeline", "risk", "approval", "content"}


class VisibleTextParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden_depth = 0
        self.texts: list[str] = []

    def handle_starttag(self, tag, attributes):
        if tag in {"style", "script"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        if tag in {"style", "script"}:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth:
            self.texts.append(data)


def text_tokens(text: str) -> set[str]:
    return {token.casefold() for token in re.split(TOKEN_SEPARATORS, text) if token}


def deck_tokens(deck_html: str) -> set[str]:
    parser = VisibleTextParser()
    parser.feed(deck_html)
    return text_tokens(" ".join(parser.texts))


def slide_models(deck_html: str):
    return create_slide_models(split_slide_sources(deck_html))


def text_runs(slide_xml: str) -> list[str]:
    return [html.unescape(run) for run in re.findall(r"<a:t>(.*?)</a:t>", slide_xml, flags=re.DOTALL)]


class NativeFallbackTextTest(unittest.TestCase):
    def test_every_text_run_comes_from_the_deck(self):
        for deck_html in (BOARD_DECK, PLAN_DECK, ROLE_DECK):
            allowed_tokens = deck_tokens(deck_html)
            for model in slide_models(deck_html):
                for run in text_runs(native_slide_xml(model, {})):
                    invented_tokens = text_tokens(run) - allowed_tokens
                    self.assertEqual(invented_tokens, set(), f"slide {model.index} ({model.kind}) wrote {run!r}")

    def test_the_decks_reach_every_native_layout(self):
        kinds = {model.kind for deck_html in (BOARD_DECK, PLAN_DECK, ROLE_DECK) for model in slide_models(deck_html)}
        self.assertEqual(kinds, NATIVE_LAYOUT_KINDS)

    def test_slide_kind_comes_from_the_declared_role(self):
        kinds = [model.kind for model in slide_models(ROLE_DECK)]
        self.assertEqual(kinds, ["content", "timeline", "content", "metrics", "content"])


if __name__ == "__main__":
    unittest.main()
