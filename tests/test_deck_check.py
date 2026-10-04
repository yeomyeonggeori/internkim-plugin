import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deck.check_deck import CheckRequest, check_deck  # noqa: E402


from design_gate_fixture import design_markdown, legacy_tokens_markdown  # noqa: E402
from design_gate_slides import fill_sections  # noqa: E402


def free_deck(*slides: str, head: str = "") -> str:
    return (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>샘플전자 보고</title><style>section {{ padding: var(--margin); }}</style>{head}</head>'
        "<body>" + fill_sections("".join(slides)) + "</body></html>"
    )


COVER = "<section><h1>샘플전자 3분기 매출이 늘었습니다</h1><p>이샘플</p></section>"
STATEMENT = "<section><h2>배송이 빨라지면 재구매가 늘어납니다</h2></section>"
KPI = (
    "<section><h2>매출과 이익이 모두 늘었습니다</h2>"
    "<p>매출 128억</p><p>이익률 14%</p></section>"
)
CHART = (
    "<section><h2>매출이 네 분기 연속 늘었습니다</h2>"
    '<figure style="width: 1200px; height: 600px" data-chart="column" data-labels="1Q, 2Q, 3Q" data-values="96, 104, 128" data-unit="억"></figure></section>'
)
TABLE = "<section><h2>수도권이 성장을 이끌었습니다</h2><table><tr><th>지역</th><th>매출</th></tr><tr><td>수도권</td><td>58억</td></tr></table></section>"
CLOSING = "<section><h2>예산을 승인해 주십시오</h2><ol><li>예산 6억 원</li><li>11월 3일 출시</li></ol></section>"
def primary_accent() -> str:
    from deck.deck_design import palette_candidates
    from deck.deck_preparation import prepare_deck

    return palette_candidates(prepare_deck().design)[0]["colors"]["accent"]


OWN_ACCENT = primary_accent()
CLEAN_DECK = free_deck(COVER, STATEMENT, KPI, CHART, TABLE, CLOSING)


class DeckCheckTest(unittest.TestCase):
    def check(self, source: str, slides: int | None = None, required_text: tuple[str, ...] = (), files: dict[str, str] | None = None, design: str | None = None):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            (deck_path / "slides.html").write_text(source, encoding="utf-8")
            (deck_path / "DESIGN.md").write_text(design_markdown() if design is None else design, encoding="utf-8")
            for name, content in (files or {}).items():
                (deck_path / name).parent.mkdir(parents=True, exist_ok=True)
                (deck_path / name).write_text(content, encoding="utf-8")
            return check_deck(CheckRequest(deck_path / "slides.html", slides, required_text))

    def codes(self, source: str, **options) -> list[tuple[str, str | None]]:
        return [(issue.kind.code, issue.location) for issue in self.check(source, **options).issues]

    def test_a_clean_deck_is_ready_to_build_and_reports_its_outline(self):
        result = self.check(CLEAN_DECK, slides=6, required_text=("128억", "수도권"))
        self.assertEqual(result.status, "ok", result.summary)
        self.assertEqual(result.details["outline"][2]["title"], "매출과 이익이 모두 늘었습니다")
        self.assertEqual(len(result.details["outline"]), 6)

    def test_the_requested_slide_count_is_enforced(self):
        self.assertIn(("SLIDE_COUNT_MISMATCH", "deck"), self.codes(CLEAN_DECK, slides=8))

    def test_placeholders_left_in_slide_text_are_errors(self):
        draft = "<section><h2>매출이 XX억 늘었습니다 TODO</h2></section>"
        result = self.check(free_deck(COVER, draft))
        issue = next(issue for issue in result.issues if issue.kind.code == "PLACEHOLDER_LEFT")
        self.assertEqual(issue.location, "slide 2")
        self.assertIn("XX", issue.message)
        self.assertIn("TODO", issue.message)

    def test_required_text_is_matched_across_line_breaks_and_spacing(self):
        result = self.check(CLEAN_DECK, required_text=("매출과 이익이\n모두 늘었습니다", "호남"))
        self.assertEqual([(issue.kind.code, issue.location) for issue in result.issues], [("REQUIRED_TEXT_MISSING", "호남")])

    def test_an_empty_slide_is_an_error(self):
        self.assertIn(("SLIDE_WITHOUT_CONTENT", "slide 2"), self.codes(free_deck(COVER, "<section><h2> </h2></section>")))

    def test_chart_data_must_parse_and_line_up(self):
        broken = (
            '<section><h2>차트가 깨졌습니다</h2><figure data-chart="column" data-labels="1Q, 2Q, 3Q" data-values="96억, 104, 128"></figure></section>',
            '<section><h2>길이가 다릅니다</h2><figure data-chart="stacked" data-labels="1Q, 2Q" data-series="가: 1, 2; 나: 3"></figure></section>',
            '<section><h2>종류가 없습니다</h2><figure data-chart="radar" data-labels="1Q, 2Q" data-values="1, 2"></figure></section>',
            '<section><h2>도넛은 양수만 받습니다</h2><figure data-chart="donut" data-labels="가, 나" data-values="3, -1" data-highlight="다"></figure></section>',
        )
        result = self.check(free_deck(COVER, *broken))
        messages = {issue.location: [] for issue in result.issues}
        for issue in result.issues:
            if issue.kind.code == "CHART_DATA_INVALID":
                messages[issue.location].append(issue.message)
        self.assertIn("96억", " ".join(messages["slide 2"]))
        self.assertIn("1 numbers for 2 labels", " ".join(messages["slide 3"]))
        self.assertIn("radar", " ".join(messages["slide 4"]))
        self.assertIn("positive shares", " ".join(messages["slide 5"]))
        self.assertIn("data-highlight", " ".join(messages["slide 5"]))

    def test_two_axis_and_stacking_charts_need_their_own_data_shape(self):
        shaped = (
            '<section><h2>콤보는 두 계열이 필요합니다</h2><figure data-chart="combo" data-labels="1Q, 2Q" data-values="1, 2"></figure></section>',
            '<section><h2>산점도는 두 축이 필요합니다</h2><figure data-chart="scatter" data-labels="가, 나" data-series="x: 1, 2; y: 3, 4; z: 5, 6"></figure></section>',
            '<section><h2>쌓는 차트는 음수를 받지 않습니다</h2><figure data-chart="area" data-labels="1Q, 2Q" data-series="가: 1, -2; 나: 3, 4"></figure></section>',
            '<section><h2>제대로 된 산점도입니다</h2><figure data-chart="scatter" data-labels="가, 나" data-series="매출: 1, 2; 이익률: 3, 4" data-unit="억, %"></figure></section>',
        )
        result = self.check(free_deck(COVER, *shaped))
        messages = {issue.location: issue.message for issue in result.issues if issue.kind.code == "CHART_DATA_INVALID"}
        self.assertIn("column series first and the line series last", messages["slide 2"])
        self.assertIn("exactly two series", messages["slide 3"])
        self.assertIn("zero or more", messages["slide 4"])
        self.assertNotIn("slide 5", messages)

    def test_grouped_thousands_are_one_number_when_values_are_comma_space_separated(self):
        grouped = '<section><h2>매출이 늘었습니다</h2><figure style="width: 1200px; height: 600px" data-chart="column" data-labels="1월, 2월" data-values="1,200, 1,350" data-unit="만원"></figure></section>'
        self.assertNotIn("CHART_DATA_INVALID", [code for code, _ in self.codes(free_deck(COVER, grouped))])
        packed = grouped.replace("1,200, 1,350", "1,200,1,350")
        messages = [issue.message for issue in self.check(free_deck(COVER, packed)).issues if issue.kind.code == "CHART_DATA_INVALID"]
        self.assertIn("comma and a space", " ".join(messages))

    def test_images_must_be_local_files_that_exist(self):
        slides = (
            '<section><h2>원격 이미지입니다</h2><img src="https://example.com/a.jpg"></section>',
            '<section><h2>없는 파일입니다</h2><img src="images/missing.jpg"></section>',
            '<section><h2>있는 파일입니다</h2><img src="images/present.jpg"></section>',
        )
        codes = self.codes(free_deck(COVER, *slides), files={"images/present.jpg": "jpeg bytes"})
        self.assertIn(("IMAGE_NOT_FOUND", "slide 2"), codes)
        self.assertIn(("IMAGE_NOT_FOUND", "slide 3"), codes)
        self.assertNotIn(("IMAGE_NOT_FOUND", "slide 4"), codes)

    def test_colors_outside_the_design_system_are_reported_but_its_own_colors_are_not(self):
        head = f"<style>.note {{ color: #1A56DB; border-color: rgba(12, 26, 48, 0.2); background: #FF00AA; }} .x {{ color: hsl(120, 100%, 25%); }} .own {{ color: {OWN_ACCENT}; }}</style>"
        result = self.check(free_deck(COVER, head=head))
        issue = next(issue for issue in result.issues if issue.kind.code == "OFF_PALETTE_COLOR")
        self.assertEqual(issue.kind.severity, "warning")
        self.assertIn("#008000, #0C1A30, #1A56DB, #FF00AA", issue.message)
        self.assertNotIn(OWN_ACCENT, issue.message.split(":", 1)[1])

    def test_the_design_gate_stops_the_check_before_any_slide_is_measured(self):
        result = self.check(CLEAN_DECK, design=legacy_tokens_markdown({"colors": {"ground": "#F5EFE0"}}))
        self.assertEqual({issue.kind.code for issue in result.issues}, {"DESIGN_VALUE_INVALID"})
        self.assertEqual(result.status, "error")

    def test_a_deck_without_a_design_document_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "slides.html").write_text(CLEAN_DECK, encoding="utf-8")
            result = check_deck(CheckRequest(Path(directory) / "slides.html"))
        self.assertEqual([issue.kind.code for issue in result.issues], ["DESIGN_MISSING"])

    def test_the_render_gate_refuses_with_the_code_the_slide_and_the_selector(self):
        slop = '<section><div class="bar"><h2>막대가 한쪽에 붙었습니다</h2></div></section>'
        head = "<style>.bar { border-left: 10px solid var(--accent); padding: 24px; background: var(--surface); }</style>"
        result = self.check(free_deck(COVER, slop, head=head))
        issue = next(issue for issue in result.issues if issue.kind.code == "ONE_SIDED_ACCENT_BAR")
        self.assertEqual((issue.kind.severity, issue.location), ("error", "slide 2"))
        self.assertIn("div.bar", issue.message)


class DeckCheckCommandTest(unittest.TestCase):
    def test_the_command_prints_the_envelope_and_exits_one_on_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "slides.html").write_text(free_deck(COVER, "<section><h2>제목</h2></section>"), encoding="utf-8")
            (Path(directory) / "DESIGN.md").write_text(legacy_tokens_markdown({"radius": "40px"}), encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "check", "slides.html", "--slide-count", "2"], capture_output=True, text=True, cwd=directory)
        envelope = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual({issue["code"] for issue in envelope["issues"]}, {"DESIGN_VALUE_INVALID"})
        self.assertIn("before the deck can be built", envelope["summary"])


if __name__ == "__main__":
    unittest.main()
