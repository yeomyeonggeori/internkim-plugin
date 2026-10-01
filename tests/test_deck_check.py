import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))
sys.path.insert(0, str(SCRIPTS_PATH / "deck"))

from check_deck import CheckRequest, check_deck  # noqa: E402


def kit_deck(*slides: str, theme: str = "corporate", head: str = "") -> str:
    return (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>샘플전자 보고</title>{head}</head>'
        f'<body data-theme="{theme}">' + "".join(slides) + "</body></html>"
    )


COVER = '<section data-layout="cover"><h1>샘플전자 3분기 매출이 늘었습니다</h1><p class="meta">이샘플</p></section>'
STATEMENT = '<section data-layout="statement"><h2>배송이 빨라지면 재구매가 늘어납니다</h2></section>'
KPI = (
    '<section data-layout="kpi"><h2>매출과 이익이 모두 늘었습니다</h2>'
    '<div class="kpi"><p class="value">128억</p><p class="label">매출</p></div>'
    '<div class="kpi"><p class="value">14%</p><p class="label">이익률</p></div></section>'
)
CHART = (
    '<section data-layout="chart"><h2>매출이 네 분기 연속 늘었습니다</h2>'
    '<figure data-chart="column" data-labels="1Q, 2Q, 3Q" data-values="96, 104, 128" data-unit="억"></figure></section>'
)
TABLE = '<section data-layout="table"><h2>수도권이 성장을 이끌었습니다</h2><table><tr><th>지역</th><th>매출</th></tr><tr><td>수도권</td><td>58억</td></tr></table></section>'
CLOSING = '<section data-layout="closing"><h2>예산을 승인해 주십시오</h2></section>'
CLEAN_DECK = kit_deck(COVER, STATEMENT, KPI, CHART, TABLE, CLOSING)


class DeckCheckTest(unittest.TestCase):
    def check(self, source: str, slides: int | None = None, required_text: tuple[str, ...] = (), files: dict[str, str] | None = None):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            (deck_path / "slides.html").write_text(source, encoding="utf-8")
            for name, content in (files or {}).items():
                (deck_path / name).parent.mkdir(parents=True, exist_ok=True)
                (deck_path / name).write_text(content, encoding="utf-8")
            return check_deck(CheckRequest(deck_path / "slides.html", slides, required_text))

    def codes(self, source: str, **options) -> list[tuple[str, str | None]]:
        return [(issue.kind.code, issue.location) for issue in self.check(source, **options).issues]

    def test_a_clean_kit_deck_is_ready_to_build_and_reports_its_outline(self):
        result = self.check(CLEAN_DECK, slides=6, required_text=("128억", "수도권"))
        self.assertEqual(result.status, "ok")
        self.assertEqual([entry["layout"] for entry in result.details["outline"]], ["cover", "statement", "kpi", "chart", "table", "closing"])
        self.assertEqual(result.details["outline"][2]["title"], "매출과 이익이 모두 늘었습니다")

    def test_a_deck_that_does_not_open_on_a_cover_or_end_on_a_closing_is_warned(self):
        codes = self.codes(kit_deck(STATEMENT, KPI, CHART))
        self.assertIn(("FIRST_SLIDE_NOT_COVER", "slide 1"), codes)
        self.assertIn(("LAST_SLIDE_NOT_CLOSING", "slide 3"), codes)
        self.assertEqual(self.check(kit_deck(STATEMENT, KPI, CHART)).status, "warning")
        self.assertNotIn("LAST_SLIDE_NOT_CLOSING", [code for code, _ in self.codes(kit_deck(COVER, STATEMENT))])

    def test_an_unknown_layout_names_the_closest_one(self):
        result = self.check(kit_deck(COVER, '<section data-layout="kpis"><h2>지표가 좋아졌습니다</h2></section>'))
        issue = next(issue for issue in result.issues if issue.kind.code == "LAYOUT_UNKNOWN")
        self.assertEqual(issue.location, "slide 2")
        self.assertEqual(issue.suggestion["didYouMean"], "kpi")
        self.assertIn("timeline", issue.suggestion["available"])

    def test_every_structural_error_is_reported_in_one_pass(self):
        typo_with_one_kpi = '<section data-layout="kpii"><h2>지표가 좋습니다</h2><div class="kpi"><p class="value">1</p><p class="label">매출</p></div></section>'
        typo_with_short_values = '<section data-layout="chart"><h2>매출이 늘었습니다</h2><figure data-chart="colum" data-labels="1Q, 2Q, 3Q" data-values="1, 2"></figure></section>'
        result = self.check(kit_deck(COVER, typo_with_one_kpi, typo_with_short_values, CLOSING))
        errors = [(issue.kind.code, issue.location) for issue in result.issues if issue.kind.severity == "error"]
        self.assertEqual(errors, [("LAYOUT_UNKNOWN", "slide 2"), ("LAYOUT_PART_MISSING", "slide 2"), ("CHART_DATA_INVALID", "slide 3"), ("CHART_DATA_INVALID", "slide 3")])
        chart_type = next(issue for issue in result.issues if 'colum"' in issue.message)
        self.assertEqual(chart_type.suggestion["didYouMean"], "column")
        for issue in result.issues:
            self.assertIn(issue.message, result.summary)

    def test_a_layout_typo_counts_as_the_layout_it_names_for_repetition(self):
        typo = STATEMENT.replace('data-layout="statement"', 'data-layout="statment"')
        self.assertIn(("LAYOUT_REPEATED", "slide 3"), self.codes(kit_deck(COVER, STATEMENT, typo, STATEMENT)))

    def test_an_unknown_theme_names_the_closest_one(self):
        result = self.check(kit_deck(COVER, theme="midnite"))
        issue = next(issue for issue in result.issues if issue.kind.code == "THEME_UNKNOWN")
        self.assertEqual(issue.suggestion["didYouMean"], "midnight")

    def test_a_slide_without_a_layout_in_a_kit_deck_is_an_error(self):
        self.assertIn(("LAYOUT_MISSING", "slide 2"), self.codes(kit_deck(COVER, "<section><h2>레이아웃이 없습니다</h2></section>")))

    def test_parts_must_be_direct_children_in_the_count_the_layout_holds(self):
        wrapped = '<section data-layout="kpi"><h2>지표</h2><div class="row"><div class="kpi"><p class="value">1</p></div><div class="kpi"><p class="value">2</p></div></div></section>'
        too_many = '<section data-layout="cards"><h2>다섯 장입니다</h2>' + '<div class="card"><h3>항목</h3></div>' * 5 + "</section>"
        result = self.check(kit_deck(COVER, wrapped, too_many))
        missing = next(issue for issue in result.issues if issue.kind.code == "LAYOUT_PART_MISSING")
        self.assertEqual(missing.location, "slide 2")
        self.assertIn(".kpi x2-4", missing.message)
        self.assertEqual(missing.suggestion["layout"], "kpi")
        self.assertIn(("LAYOUT_PART_EXCESS", "slide 3"), [(issue.kind.code, issue.location) for issue in result.issues])

    def test_three_slides_in_a_row_with_one_layout_are_an_error(self):
        codes = self.codes(kit_deck(COVER, STATEMENT, STATEMENT, STATEMENT))
        self.assertIn(("LAYOUT_REPEATED", "slide 3"), codes)

    def test_three_chart_slides_in_a_row_are_a_repeat_whatever_their_chart_kinds(self):
        line = CHART.replace('data-chart="column"', 'data-chart="line"')
        bar = CHART.replace('data-chart="column"', 'data-chart="bar"')
        self.assertIn(("LAYOUT_REPEATED", "slide 3"), self.codes(kit_deck(COVER, CHART, line, bar)))
        self.assertNotIn("LAYOUT_REPEATED", [code for code, _ in self.codes(kit_deck(COVER, CHART, line, STATEMENT, bar))])

    def test_a_long_deck_needs_three_layouts(self):
        codes = self.codes(kit_deck(STATEMENT, KPI, STATEMENT, KPI, STATEMENT, KPI))
        self.assertIn(("TOO_FEW_LAYOUTS", "deck"), codes)

    def test_the_requested_slide_count_is_enforced(self):
        self.assertIn(("SLIDE_COUNT_MISMATCH", "deck"), self.codes(CLEAN_DECK, slides=8))

    def test_placeholders_left_in_slide_text_are_errors(self):
        draft = '<section data-layout="statement"><h2>매출이 XX억 늘었습니다 TODO</h2></section>'
        result = self.check(kit_deck(COVER, draft))
        issue = next(issue for issue in result.issues if issue.kind.code == "PLACEHOLDER_LEFT")
        self.assertEqual(issue.location, "slide 2")
        self.assertIn("XX", issue.message)
        self.assertIn("TODO", issue.message)

    def test_required_text_is_matched_across_line_breaks_and_spacing(self):
        result = self.check(CLEAN_DECK, required_text=("매출과 이익이\n모두 늘었습니다", "호남"))
        self.assertEqual([(issue.kind.code, issue.location) for issue in result.issues], [("REQUIRED_TEXT_MISSING", "호남")])

    def test_an_empty_slide_is_an_error(self):
        self.assertIn(("SLIDE_WITHOUT_CONTENT", "slide 2"), self.codes(kit_deck(COVER, '<section data-layout="statement"><h2> </h2></section>')))

    def test_chart_data_must_parse_and_line_up(self):
        broken = (
            '<section data-layout="chart"><h2>차트가 깨졌습니다</h2>'
            '<figure data-chart="column" data-labels="1Q, 2Q, 3Q" data-values="96억, 104, 128"></figure></section>',
            '<section data-layout="chart"><h2>길이가 다릅니다</h2>'
            '<figure data-chart="stacked" data-labels="1Q, 2Q" data-series="가: 1, 2; 나: 3"></figure></section>',
            '<section data-layout="chart"><h2>종류가 없습니다</h2>'
            '<figure data-chart="radar" data-labels="1Q, 2Q" data-values="1, 2"></figure></section>',
            '<section data-layout="chart"><h2>도넛은 양수만 받습니다</h2>'
            '<figure data-chart="donut" data-labels="가, 나" data-values="3, -1" data-highlight="다"></figure></section>',
        )
        result = self.check(kit_deck(COVER, *broken))
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
            '<section data-layout="chart"><h2>콤보는 두 계열이 필요합니다</h2><figure data-chart="combo" data-labels="1Q, 2Q" data-values="1, 2"></figure></section>',
            '<section data-layout="chart"><h2>산점도는 두 축이 필요합니다</h2><figure data-chart="scatter" data-labels="가, 나" data-series="x: 1, 2; y: 3, 4; z: 5, 6"></figure></section>',
            '<section data-layout="chart"><h2>쌓는 차트는 음수를 받지 않습니다</h2><figure data-chart="area" data-labels="1Q, 2Q" data-series="가: 1, -2; 나: 3, 4"></figure></section>',
            '<section data-layout="chart"><h2>제대로 된 산점도입니다</h2><figure data-chart="scatter" data-labels="가, 나" data-series="매출: 1, 2; 이익률: 3, 4" data-unit="억, %"></figure></section>',
        )
        result = self.check(kit_deck(COVER, *shaped))
        messages = {issue.location: issue.message for issue in result.issues if issue.kind.code == "CHART_DATA_INVALID"}
        self.assertIn("column series first and the line series last", messages["slide 2"])
        self.assertIn("exactly two series", messages["slide 3"])
        self.assertIn("zero or more", messages["slide 4"])
        self.assertNotIn("slide 5", messages)

    def test_grouped_thousands_are_one_number_when_values_are_comma_space_separated(self):
        grouped = '<section data-layout="chart"><h2>매출이 늘었습니다</h2><figure data-chart="column" data-labels="1월, 2월" data-values="1,200, 1,350" data-unit="만원"></figure></section>'
        self.assertNotIn("CHART_DATA_INVALID", [code for code, _ in self.codes(kit_deck(COVER, grouped))])
        packed = grouped.replace("1,200, 1,350", "1,200,1,350")
        messages = [issue.message for issue in self.check(kit_deck(COVER, packed)).issues if issue.kind.code == "CHART_DATA_INVALID"]
        self.assertIn("comma and a space", " ".join(messages))

    def test_images_must_be_local_files_that_exist(self):
        slides = (
            '<section data-layout="image"><h2>원격 이미지입니다</h2><img src="https://example.com/a.jpg"></section>',
            '<section data-layout="image"><h2>없는 파일입니다</h2><img src="images/missing.jpg"></section>',
            '<section data-layout="image"><h2>있는 파일입니다</h2><img src="images/present.jpg"></section>',
        )
        codes = self.codes(kit_deck(COVER, *slides), files={"images/present.jpg": "jpeg bytes"})
        self.assertIn(("IMAGE_NOT_FOUND", "slide 2"), codes)
        self.assertIn(("IMAGE_NOT_FOUND", "slide 3"), codes)
        self.assertNotIn(("IMAGE_NOT_FOUND", "slide 4"), codes)

    def test_colors_outside_the_theme_are_reported_but_theme_tokens_and_brand_overrides_are_not(self):
        head = "<style>:root { --accent: #E4002B; } .note { color: #1A56DB; border-color: rgba(12, 26, 48, 0.2); background: #FF00AA; } .x { color: hsl(120, 100%, 25%); }</style>"
        result = self.check(kit_deck(COVER, head=head))
        issue = next(issue for issue in result.issues if issue.kind.code == "OFF_PALETTE_COLOR")
        self.assertEqual(issue.kind.severity, "warning")
        self.assertEqual(issue.suggestion["offPalette"], ["#008000", "#FF00AA"])
        self.assertIn("#E4002B", issue.suggestion["palette"])

    def test_a_design_document_palette_also_governs_a_deck_without_the_kit(self):
        custom = '<html><head><style>h2 { color: #123456; } p { color: #654321; }</style></head><body><section><h2>제목</h2><p>본문</p></section></body></html>'
        design = "---\ncolors:\n  ink: \"#123456\"\n---\n# Design\n"
        self.assertEqual(self.codes(custom, files={"DESIGN.md": design}), [("OFF_PALETTE_COLOR", "slides.html")])
        self.assertEqual(self.codes(custom), [])


class DeckCheckCommandTest(unittest.TestCase):
    def test_the_command_prints_the_envelope_and_exits_one_on_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "slides.html").write_text(kit_deck(COVER, '<section data-layout="hero"><h2>제목</h2></section>'), encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "check", "--slide-count", "2"], capture_output=True, text=True, cwd=directory)
        envelope = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["LAYOUT_UNKNOWN"])
        self.assertIn("before it can be built", envelope["summary"])


if __name__ == "__main__":
    unittest.main()
