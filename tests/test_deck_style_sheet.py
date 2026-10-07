from pathlib import Path
import tempfile
import unittest

from staged_deck_fixture import style_sheet_markdown

from deck.design_system import design_style, read_design_system  # noqa: E402


def read(overrides: dict | None = None, text: str | None = None):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "DESIGN.md"
        path.write_text(style_sheet_markdown(overrides) if text is None else text, encoding="utf-8")
        return read_design_system(path)


def unclosed_style_sheet() -> str:
    return style_sheet_markdown().rstrip("\n").removesuffix("---").rstrip("\n") + "\n"


def codes(overrides: dict | None = None) -> set[str]:
    return {issue.kind.code for issue in read(overrides)[1]}


class StyleSheetTest(unittest.TestCase):
    def test_a_complete_style_sheet_passes_and_keeps_its_own_colors(self):
        system, issues = read()
        self.assertEqual(issues, [])
        self.assertEqual(system.colors["accent"], "0E7C66")
        self.assertEqual(system.backgrounds["cover"], "FFFFFF")
        self.assertEqual(system.sizes["title"], 56)
        self.assertEqual(system.fonts["display"], "Paperlogy")

    def test_a_missing_style_sheet_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual([issue.kind.code for issue in read_design_system(Path(directory) / "DESIGN.md")[1]], ["DESIGN_MISSING"])

    def test_a_missing_value_is_named(self):
        system, issues = read({"backgrounds": {"data": None}, "style": None})
        self.assertIsNone(system)
        self.assertEqual({issue.kind.code for issue in issues}, {"DESIGN_INCOMPLETE"})
        self.assertEqual(sorted(issue.message for issue in issues), ["DESIGN.md has no backgrounds.data", "DESIGN.md has no style"])

    def test_front_matter_never_closed_is_named_with_the_line_the_fence_belongs_on(self):
        system, issues = read(text=unclosed_style_sheet())
        self.assertIsNone(system)
        self.assertEqual([issue.kind.code for issue in issues], ["DESIGN_FRONT_MATTER"])
        self.assertIn("line 19", issues[0].message)
        self.assertIn("closing ---", issues[0].message)

    def test_front_matter_closed_before_prose_names_the_line_after_its_last_value(self):
        issues = read(text=unclosed_style_sheet() + "\n# Notes\n\nA calm deck.\n")[1]
        self.assertEqual([issue.kind.code for issue in issues], ["DESIGN_FRONT_MATTER"])
        self.assertIn("line 19", issues[0].message)

    def test_a_style_sheet_without_an_opening_fence_is_named_as_such(self):
        issues = read(text=style_sheet_markdown().removeprefix("---\n"))[1]
        self.assertEqual([issue.kind.code for issue in issues], ["DESIGN_FRONT_MATTER"])
        self.assertIn("line 1", issues[0].message)

    def test_a_value_containing_three_dashes_does_not_end_the_front_matter(self):
        system, issues = read({"style": "calm --- one green accent"})
        self.assertEqual(issues, [])
        self.assertEqual(system.style, "calm --- one green accent")

    def test_an_unknown_key_or_role_is_refused(self):
        self.assertEqual(codes({"palette": "primary"}), {"DESIGN_VALUE_INVALID"})
        self.assertEqual(codes({"colors": {"tertiary": "#123456"}}), {"DESIGN_VALUE_INVALID"})

    def test_a_color_that_is_not_hex_is_refused(self):
        self.assertEqual(codes({"colors": {"accent": "green"}}), {"DESIGN_VALUE_INVALID"})

    def test_sizes_under_the_floors_are_refused(self):
        _, issues = read({"sizes": {"body": "22px", "small": "16px"}})
        messages = " ".join(issue.message for issue in issues)
        self.assertIn("sizes.body is 22px; it needs at least 28px", messages)
        self.assertIn("sizes.small is 16px; it needs at least 20px", messages)

    def test_text_and_accent_too_close_to_their_background_are_refused(self):
        _, issues = read({"colors": {"text": "#DDDDDD", "accent": "#F0F0F0"}})
        messages = " ".join(issue.message for issue in issues)
        self.assertEqual({issue.kind.code for issue in issues}, {"DESIGN_LOW_CONTRAST"})
        self.assertIn("colors.text on backgrounds.content", messages)
        self.assertIn("colors.accent on backgrounds.content", messages)

    def test_a_typeface_outside_the_three_shipped_is_refused_and_one_of_them_is_used(self):
        self.assertEqual(codes({"type": "helvetica"}), {"DESIGN_VALUE_INVALID"})
        system, _ = read({"type": "freesentation"})
        self.assertEqual(system.fonts, {"display": "Freesentation", "body": "Freesentation"})

    def test_each_page_type_takes_its_background_and_a_readable_ink(self):
        system, _ = read({"backgrounds": {"cover": "#0B1320"}})
        style = design_style(system)
        self.assertIn('section[data-type="cover"] { --ground: var(--bg-cover); background: var(--bg-cover); color: var(--on-cover); }', style)
        self.assertIn("--bg-cover: #0B1320;", style)
        self.assertIn("--on-cover: #FFFFFF;", style)
        self.assertIn("--on-content: #14213D;", style)



class StyleSheetReferenceTest(unittest.TestCase):
    def test_the_reference_shows_the_shape_of_a_style_sheet_and_no_palette_to_copy(self):
        reference = (Path(__file__).resolve().parents[1] / "skills" / "office" / "references" / "deck.md").read_text(encoding="utf-8")
        example = reference.split("```markdown", 1)[1].split("```", 1)[0]
        self.assertIn("accent:", example)
        self.assertNotRegex(example, r"#[0-9A-Fa-f]{6}\b")


if __name__ == "__main__":
    unittest.main()
