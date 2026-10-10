import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from render_fixture import can_render
from staged_deck_fixture import OFFICE_ENTRY, PICTURE, style_sheet_markdown, write_staged_deck

from deck.check_deck import DeckRequest, check_page, check_staged_deck  # noqa: E402


COVER = "<h1>샘플전자 3분기 매출이 늘었습니다</h1><p>이샘플</p>"
STATEMENT = f'<h2>배송이 빨라지면 재구매가 늘어납니다</h2>{PICTURE}'
KPI = f'<h2>매출과 이익이 모두 늘었습니다</h2><div class="fill"><p>매출 128억</p><p>이익률 14%</p></div>{PICTURE}'
CHART = '<h2>매출이 네 분기 연속 늘었습니다</h2><figure style="width: 1200px; height: 600px" data-chart="column" data-labels="1Q, 2Q, 3Q" data-values="96, 104, 128" data-unit="억"></figure>'
TABLE = '<h2>수도권이 성장을 이끌었습니다</h2><table style="flex: 1"><tr><th>지역</th><th>매출</th></tr><tr><td>수도권</td><td>58억</td></tr></table>'
CLOSING = "<h2>예산을 승인해 주십시오</h2><ol><li>예산 6억 원</li><li>11월 3일 출시</li></ol>"
CLEAN = [COVER, STATEMENT, KPI, CHART, TABLE, CLOSING]


def codes_of(result) -> list[tuple[str, str | None]]:
    return [(issue.kind.code, issue.location) for issue in result.issues]


class StagedDeckCheckTest(unittest.TestCase):
    def check(self, sections: list, slides: int | None = None, required_text: tuple[str, ...] = (), files: dict[str, str] | None = None, style: str = "", design: dict | None = None):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = write_staged_deck(Path(directory), sections, style, design)
            for name, content in (files or {}).items():
                (deck_path / name).parent.mkdir(parents=True, exist_ok=True)
                (deck_path / name).write_text(content, encoding="utf-8")
            return check_staged_deck(DeckRequest(deck_path, slides, required_text)).result

    @unittest.skipUnless(can_render(), "needs the renderer")
    def test_a_clean_deck_is_ready_to_build(self):
        result = self.check(CLEAN, slides=6, required_text=("128억", "수도권"))
        self.assertNotEqual(result.status, "error", result.summary)
        self.assertEqual(result.details["slideCount"], 6)

    def test_the_requested_slide_count_is_enforced(self):
        self.assertIn(("SLIDE_COUNT_MISMATCH", "outline"), codes_of(self.check(CLEAN, slides=8)))

    def test_placeholders_left_in_page_text_are_errors(self):
        result = self.check([COVER, "<h2>매출이 XX억 늘었습니다 TODO</h2>"])
        messages = [issue.message for issue in result.issues if issue.kind.code == "PLACEHOLDER_LEFT" and issue.location == "page 2"]
        self.assertTrue(any("XX" in message and "TODO" in message for message in messages), messages)

    def test_required_text_is_matched_across_line_breaks_and_spacing(self):
        result = self.check(CLEAN, required_text=("매출과 이익이\n모두 늘었습니다", "호남"))
        missing = [issue.location for issue in result.issues if issue.kind.code == "REQUIRED_TEXT_MISSING"]
        self.assertEqual(missing, ["호남"])

    def test_an_empty_page_is_an_error(self):
        self.assertIn(("SLIDE_WITHOUT_CONTENT", "page 2"), codes_of(self.check([COVER, "<h2> </h2>"])))

    def test_chart_data_must_parse_and_line_up(self):
        broken = [
            '<h2>차트가 깨졌습니다</h2><figure data-chart="column" data-labels="1Q, 2Q, 3Q" data-values="96억, 104, 128"></figure>',
            '<h2>길이가 다릅니다</h2><figure data-chart="stacked" data-labels="1Q, 2Q" data-series="가: 1, 2; 나: 3"></figure>',
            '<h2>종류가 없습니다</h2><figure data-chart="radar" data-labels="1Q, 2Q" data-values="1, 2"></figure>',
            '<h2>도넛은 양수만 받습니다</h2><figure data-chart="donut" data-labels="가, 나" data-values="3, -1" data-highlight="다"></figure>',
        ]
        result = self.check([COVER, *broken])
        messages = {}
        for issue in result.issues:
            if issue.kind.code == "CHART_DATA_INVALID":
                messages.setdefault(issue.location, []).append(issue.message)
        self.assertIn("96억", " ".join(messages["page 2"]))
        self.assertIn("1 numbers for 2 labels", " ".join(messages["page 3"]))
        self.assertIn("radar", " ".join(messages["page 4"]))
        self.assertIn("positive shares", " ".join(messages["page 5"]))
        self.assertIn("data-highlight", " ".join(messages["page 5"]))

    def test_two_axis_and_stacking_charts_need_their_own_data_shape(self):
        shaped = [
            '<h2>콤보는 두 계열이 필요합니다</h2><figure data-chart="combo" data-labels="1Q, 2Q" data-values="1, 2"></figure>',
            '<h2>산점도는 두 축이 필요합니다</h2><figure data-chart="scatter" data-labels="가, 나" data-series="x: 1, 2; y: 3, 4; z: 5, 6"></figure>',
            '<h2>쌓는 차트는 음수를 받지 않습니다</h2><figure data-chart="area" data-labels="1Q, 2Q" data-series="가: 1, -2; 나: 3, 4"></figure>',
            '<h2>제대로 된 산점도입니다</h2><figure data-chart="scatter" data-labels="가, 나" data-series="매출: 1, 2; 이익률: 3, 4" data-unit="억, %"></figure>',
        ]
        result = self.check([COVER, *shaped])
        messages = {issue.location: issue.message for issue in result.issues if issue.kind.code == "CHART_DATA_INVALID"}
        self.assertIn("column series first and the line series last", messages["page 2"])
        self.assertIn("exactly two series", messages["page 3"])
        self.assertIn("zero or more", messages["page 4"])
        self.assertNotIn("page 5", messages)

    def test_a_round_chart_needs_more_than_one_part_of_its_whole(self):
        round_charts = [
            '<h2>한 조각뿐인 도넛</h2><figure data-chart="donut" data-labels="완성차 1차 협력사" data-values="72" data-unit="%"></figure>',
            '<h2>한 조각뿐인 파이</h2><figure data-chart="pie" data-labels="정부 지원금" data-values="4.5" data-unit="억 원"></figure>',
            '<h2>나머지를 함께 그린 도넛</h2><figure data-chart="donut" data-labels="완성차 1차 협력사, 그 밖의 고객" data-values="72, 28" data-unit="%"></figure>',
        ]
        result = self.check([COVER, *round_charts])
        messages = {issue.location: issue.message for issue in result.issues if issue.kind.code == "CHART_DATA_INVALID"}
        self.assertIn("reads as 100%", messages["page 2"])
        self.assertIn("reads as 100%", messages["page 3"])
        self.assertNotIn("page 4", messages)

    def test_grouped_thousands_are_one_number_when_values_are_comma_space_separated(self):
        grouped = '<h2>매출이 늘었습니다</h2><figure style="width: 1200px; height: 600px" data-chart="column" data-labels="1월, 2월" data-values="1,200, 1,350" data-unit="만원"></figure>'
        self.assertNotIn("CHART_DATA_INVALID", [code for code, _ in codes_of(self.check([COVER, grouped]))])
        packed = grouped.replace("1,200, 1,350", "1,200,1,350")
        messages = [issue.message for issue in self.check([COVER, packed]).issues if issue.kind.code == "CHART_DATA_INVALID"]
        self.assertIn("comma and a space", " ".join(messages))

    def test_images_must_be_local_files_that_exist(self):
        pages = [
            '<h2>원격 이미지입니다</h2><img src="https://example.com/a.jpg">',
            '<h2>없는 파일입니다</h2><img src="images/missing.jpg">',
            '<h2>있는 파일입니다</h2><img src="images/present.jpg">',
        ]
        codes = codes_of(self.check([COVER, *pages], files={"images/present.jpg": "jpeg bytes"}))
        self.assertIn(("IMAGE_NOT_FOUND", "page 2"), codes)
        self.assertIn(("IMAGE_NOT_FOUND", "page 3"), codes)
        self.assertNotIn(("IMAGE_NOT_FOUND", "page 4"), codes)

    def test_colors_outside_the_style_sheet_are_a_warning_and_its_own_colors_are_not_named(self):
        style = ".note { color: #1A56DB; border-color: rgba(12, 26, 48, 0.2); background: #FF00AA; } .x { color: hsl(120, 100%, 25%); } .own { color: #0E7C66; background: #EEF5F2; }"
        result = self.check([COVER, STATEMENT], style=style)
        issue = next(issue for issue in result.issues if issue.kind.code == "OFF_PALETTE_COLOR")
        self.assertEqual(issue.kind.severity, "warning")
        self.assertIn("#008000, #0C1A30, #1A56DB, #FF00AA", issue.message)
        self.assertNotIn("#0E7C66", issue.message.split("outside")[0])

    def test_a_style_sheet_that_does_not_pass_stops_the_check_before_any_page(self):
        result = self.check(CLEAN, design={"colors": {"text": "#F0F0F0"}})
        self.assertEqual({issue.kind.code for issue in result.issues}, {"DESIGN_LOW_CONTRAST", "STAGE_NOT_READY"})

    def test_a_missing_page_file_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = write_staged_deck(Path(directory), CLEAN)
            (deck_path / "pages" / "03.html").unlink()
            result = check_staged_deck(DeckRequest(deck_path)).result
        self.assertIn(("PAGE_MISSING", "page 3"), codes_of(result))

    @unittest.skipUnless(can_render(), "needs the renderer")
    def test_the_render_gate_refuses_with_the_code_the_page_and_the_selector(self):
        slop = '<div class="bar"><h2>막대가 한쪽에 붙었습니다</h2></div>'
        style = ".bar { border-left: 10px solid var(--accent); padding: 24px; background: var(--surface); }"
        result = self.check([COVER, slop], style=style)
        issue = next(issue for issue in result.issues if issue.kind.code == "ONE_SIDED_ACCENT_BAR")
        self.assertEqual((issue.kind.severity, issue.location), ("error", "page 2"))
        self.assertIn("div.bar", issue.message)


class PageCheckTest(unittest.TestCase):
    def check_page(self, sections: list, number: int, page: str | None = None, layouts: list[str] | None = None, photos: dict | None = None):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = write_staged_deck(Path(directory), sections, layouts=layouts, photos=photos)
            if page is not None:
                (deck_path / "pages" / f"{number:02d}.html").write_text(page, encoding="utf-8")
            return check_page(deck_path / "pages" / f"{number:02d}.html")

    def test_a_page_file_that_is_not_one_section_is_refused(self):
        result = self.check_page([COVER, STATEMENT], 2, page="<section><h2>하나</h2></section><section><h2>둘</h2></section>")
        self.assertEqual(codes_of(result), [("PAGE_NOT_ONE_SECTION", "page 2")])

    def test_a_page_beyond_the_outline_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = write_staged_deck(Path(directory), [COVER, STATEMENT])
            (deck_path / "pages" / "03.html").write_text("<section><h2>남는 쪽</h2></section>", encoding="utf-8")
            result = check_page(deck_path / "pages" / "03.html")
        self.assertEqual([issue.kind.code for issue in result.issues], ["PAGE_NOT_IN_OUTLINE"])

    def test_a_planned_photo_missing_from_its_page_is_a_warning_and_no_refusal(self):
        result = self.check_page([COVER, STATEMENT, CLOSING], 2, layouts=["cover_typography_hero", "left_text_right_image", "closing_cta"], photos={2: ["photo.jpg"]})
        self.assertEqual([issue.kind.severity for issue in result.issues if issue.kind.code == "PAGE_DIFFERS_FROM_OUTLINE"], ["warning"])
        self.assertEqual([issue.kind.code for issue in result.issues if issue.kind.severity == "error"], [])

    def with_figures(self, sections: list, number: int, figures: list[dict], page: str):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = write_staged_deck(Path(directory), sections)
            outline = json.loads((deck_path / "outline.json").read_text(encoding="utf-8"))
            outline["pages"][number - 1]["figures"] = figures
            (deck_path / "outline.json").write_text(json.dumps(outline, ensure_ascii=False), encoding="utf-8")
            (deck_path / "pages" / f"{number:02d}.html").write_text(page, encoding="utf-8")
            return check_page(deck_path / "pages" / f"{number:02d}.html")

    def test_a_chart_plots_only_its_own_entrys_figures_as_they_are_stated(self):
        figures = [{"label": "1Q", "value": "96", "unit": "억"}, {"label": "2Q", "value": "104", "unit": "억"}]
        foreign = '<section><h2 data-title></h2><figure style="width: 1200px; height: 600px" data-chart="column" data-labels="1Q, 3Q" data-values="96, 128" data-unit="억"></figure></section>'
        changed = foreign.replace('data-labels="1Q, 3Q" data-values="96, 128"', 'data-labels="1Q, 2Q" data-values="96, 140"')
        messages = [issue.message for issue in self.with_figures([COVER, CHART, CLOSING], 2, figures, foreign).issues if issue.kind.code == "CHART_NOT_FROM_FIGURES"]
        self.assertTrue(any('"3Q" is not a figure' in message and "1Q 96억" in message for message in messages), messages)
        messages = [issue.message for issue in self.with_figures([COVER, CHART, CLOSING], 2, figures, changed).issues if issue.kind.code == "CHART_NOT_FROM_FIGURES"]
        self.assertTrue(any("plots 140, but its figure is 104" in message for message in messages), messages)

    def test_one_axis_whose_figures_have_different_units_is_refused(self):
        figures = [{"label": "도입 농가", "value": "64", "unit": "곳"}, {"label": "수확량 증가", "value": "17", "unit": "%"}]
        mixed = '<section><h2 data-title></h2><figure style="width: 1200px; height: 600px" data-chart="column" data-labels="도입 농가, 수확량 증가" data-values="64, 17" data-unit="%"></figure></section>'
        result = self.with_figures([COVER, CHART, CLOSING], 2, figures, mixed)
        messages = [issue.message for issue in result.issues if issue.kind.code == "CHART_MIXED_UNITS"]
        self.assertTrue(any("도입 농가 64곳" in message and "수확량 증가 17%" in message for message in messages), messages)
        self.assertEqual(result.status, "error")

    def test_a_chart_unit_other_than_its_figures_unit_is_refused(self):
        figures = [{"label": "1Q", "value": "96", "unit": "억"}]
        relabeled = '<section><h2 data-title></h2><figure style="width: 1200px; height: 600px" data-chart="column" data-labels="1Q" data-values="96" data-unit="%"></figure></section>'
        messages = [issue.message for issue in self.with_figures([COVER, CHART, CLOSING], 2, figures, relabeled).issues if issue.kind.code == "CHART_NOT_FROM_FIGURES"]
        self.assertTrue(any('data-unit gives "%"' in message for message in messages), messages)

    def test_a_page_without_one_bound_title_is_refused(self):
        typed = "<section><h2>사업 개요와 사업비</h2><p>총 사업비 6억 원</p></section>"
        self.assertIn(("PAGE_TITLE_UNBOUND", "page 2"), codes_of(self.check_page([COVER, STATEMENT, CLOSING], 2, page=typed)))

    def test_a_passing_page_hands_over_the_next_entry_alone(self):
        result = self.check_page([COVER, STATEMENT, CLOSING], 2)
        self.assertIn("pages/03.html from outline entry 3 alone", result.summary)
        self.assertIn("예산을 승인해 주십시오", result.summary)
        self.assertNotIn("배송이 빨라지면", result.summary)

    def test_a_page_composed_without_the_chart_its_layout_suggests_is_not_refused(self):
        result = self.check_page([COVER, KPI, CLOSING], 2, layouts=["cover_typography_hero", "chart_with_insight", "closing_cta"])
        self.assertEqual([issue.kind.code for issue in result.issues if issue.kind.severity == "error"], [])

    def test_the_page_check_does_not_count_the_blocks_a_layout_is_drawn_with(self):
        result = self.check_page([COVER, STATEMENT, CLOSING], 2, layouts=["cover_typography_hero", "three_column_cards", "closing_cta"])
        self.assertNotIn("PAGE_DIFFERS_FROM_OUTLINE", [code for code, _ in codes_of(result)])

    @unittest.skipUnless(can_render(), "needs the renderer")
    def test_the_page_check_measures_the_page_alone(self):
        spill = '<section><style>.spill { position: absolute; left: 1200px; top: 400px; width: 700px; } .faint { color: #EEF5F2; }</style><h2 data-title></h2><p class="spill">수도권 매출이 크게 늘었고 영남과 호남 매출도 함께 늘었습니다</p><p class="faint">재구매가 늘어난 고객이 많습니다</p></section>'
        result = self.check_page([COVER, STATEMENT], 2, page=spill)
        codes = codes_of(result)
        self.assertIn(("OUT_OF_FRAME", "page 2"), codes)
        self.assertIn(("TEXT_LOW_CONTRAST", "page 2"), codes)
        self.assertEqual(result.status, "error")


class DeckCheckCommandTest(unittest.TestCase):
    def test_the_command_prints_the_envelope_and_exits_one_on_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = write_staged_deck(Path(directory), [COVER, STATEMENT])
            (deck_path / "DESIGN.md").write_text(style_sheet_markdown({"radius": "40px"}), encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "check", "DESIGN.md"], capture_output=True, text=True, cwd=directory)
        envelope = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual({issue["code"] for issue in envelope["issues"]}, {"DESIGN_VALUE_INVALID"})
        self.assertIn("problems to fix", envelope["summary"])


if __name__ == "__main__":
    unittest.main()
