import unittest

import staged_deck_fixture  # noqa: F401

from deck.outline import Outline, OutlinePage  # noqa: E402
from deck.page_files import assembled_deck, lone_section, scoped_stylesheet  # noqa: E402


PAGE = """<section class="hero">
<style>
:root { --wide: 1200px; }
section { padding: 96px; }
.hero h2, p > b { color: var(--accent); }
@media (min-width: 1000px) { .card { padding: 24px; } }
@font-face { font-family: "Brand"; src: url("brand.woff2"); }
</style>
<h2>Revenue grew</h2><p>By <b>18%</b></p>
</section>"""


class ScopedStyleTest(unittest.TestCase):
    def test_each_selector_is_scoped_to_its_page(self):
        scoped = scoped_stylesheet(".card { padding: 24px; } h2, p > b { color: red; }", "page-03")
        self.assertIn("#page-03 .card, section#page-03.card {", scoped)
        self.assertIn("#page-03 h2, #page-03 p > b {", scoped)

    def test_root_and_section_rules_land_on_the_page_section(self):
        scoped = scoped_stylesheet(":root { --wide: 1200px; } section { padding: 96px; } body .note { color: red; }", "page-01")
        self.assertIn("section#page-01 { --wide: 1200px; }", scoped)
        self.assertIn("section#page-01 { padding: 96px; }", scoped)
        self.assertIn("section#page-01 .note {", scoped)

    def test_media_rules_are_scoped_inside_and_font_faces_are_kept(self):
        scoped = scoped_stylesheet("@media (min-width: 1000px) { .card { padding: 24px; } } @font-face { font-family: \"Brand\"; }", "page-02")
        self.assertIn("@media (min-width: 1000px) {#page-02 .card, section#page-02.card {", scoped)
        self.assertIn('@font-face { font-family: "Brand"; }', scoped)


class AssembledDeckTest(unittest.TestCase):
    def test_pages_are_assembled_with_their_styles_in_the_head_and_their_outline_entry_on_the_section(self):
        outline = Outline("hook", (OutlinePage("Cover", "cover", ("a",), ()), OutlinePage("Revenue grew", "content", ("b",), (), "hero_big_number")))
        document = assembled_deck(outline, {2: PAGE})
        head, body = document.split("</head>")
        self.assertIn("section#page-02 { padding: 96px; }", head)
        self.assertNotIn("<style", body)
        self.assertIn('<section id="page-02" data-page="2" data-type="content" data-layout="hero_big_number" class="hero">', body)
        self.assertIn("<title>Cover</title>", head)
        self.assertIn('<html lang="en">', document)

    def test_a_file_holding_more_than_one_section_is_not_a_page(self):
        self.assertIsNone(lone_section("<section>a</section><section>b</section>"))
        self.assertIsNone(lone_section("<p>outside</p><section>a</section>"))
        self.assertEqual(lone_section("\n<section>a</section>\n"), "<section>a</section>")


if __name__ == "__main__":
    unittest.main()
