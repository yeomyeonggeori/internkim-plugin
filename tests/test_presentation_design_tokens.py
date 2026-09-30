from pathlib import Path
import sys
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "deck"
sys.path.insert(0, str(SCRIPTS_PATH))

import html_export  # noqa: E402
import render_review  # noqa: E402


DESIGN_DOCUMENT = """---
colors:
  accent: "#0E59B3"
  ink: '#111111'
layout:
  margin: '80px'
---
The visual system.
"""


class DesignTokenTest(unittest.TestCase):
    def test_export_and_review_read_tokens_the_same_way(self):
        self.assertIs(html_export.read_design_tokens, render_review.read_design_tokens)

    def test_single_and_double_quotes_are_both_stripped(self):
        self.assertEqual(
            render_review.read_design_tokens(DESIGN_DOCUMENT),
            {"colors.accent": "#0E59B3", "colors.ink": "#111111", "layout.margin": "80px"},
        )


if __name__ == "__main__":
    unittest.main()
