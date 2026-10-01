import json
import re
import subprocess
import sys
import unittest

from render_fixture import SCRIPTS_PATH, can_render

sys.path.insert(0, str(SCRIPTS_PATH))

from css_color import named_color_hex, parse_css_color  # noqa: E402
from render.renderer import javascript_runtime  # noqa: E402
from units import inches_to_pixels, millimetres_to_pixels, points_to_pixels  # noqa: E402

CSS_VALUES = (SCRIPTS_PATH / "render" / "css_values.mjs").as_uri()
LENGTHS = {"1in": inches_to_pixels(1), "2.54cm": inches_to_pixels(1), "10mm": millimetres_to_pixels(10), "12pt": points_to_pixels(12)}
COLORS = ("#1a56db", "#abc", "#1a56db80", "rgb(26, 86, 219)", "rgba(26, 86, 219, 0.5)", "rgb(10% 50% 90% / 25%)", "hsl(220, 79%, 48%)", "transparent", "teal", "crimson")


NAMED_COLORS_PATTERN = re.compile(r"const namedColors = \{(.*?)\};", re.DOTALL)
NAMED_COLOR_PATTERN = re.compile(r"(\w+): \[(\d+), (\d+), (\d+)\]")


def evaluate(script: str):
    runtime = javascript_runtime()
    module_flag = [] if runtime[0].endswith("bun") else ["--input-type=module"]
    completed = subprocess.run([*runtime, *module_flag, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)


def javascript_colors(texts) -> dict:
    return evaluate(f"import {{ parseColor }} from {json.dumps(CSS_VALUES)}; console.log(JSON.stringify(Object.fromEntries({json.dumps(list(texts))}.map((text) => [text, parseColor(text)]))))")


def channels(hex_value: str) -> list[int]:
    return [int(hex_value[index:index + 2], 16) for index in (0, 2, 4)]


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class RendererConformanceTest(unittest.TestCase):
    def test_the_renderer_converts_absolute_lengths_as_the_python_side_does(self):
        context = {"fontSize": 16, "rootFontSize": 16, "viewportWidth": 1600, "viewportHeight": 900}
        measured = evaluate(f"import {{ resolveLength }} from {json.dumps(CSS_VALUES)}; console.log(JSON.stringify(Object.fromEntries({json.dumps(list(LENGTHS))}.map((text) => [text, resolveLength(text, {json.dumps(context)})]))))")
        for text, pixels in LENGTHS.items():
            with self.subTest(length=text):
                self.assertAlmostEqual(measured[text], pixels, places=6)

    def test_the_renderer_reads_colors_as_the_python_side_does(self):
        for text, color in javascript_colors(COLORS).items():
            expected = parse_css_color(text)
            with self.subTest(color=text):
                self.assertEqual([round(color[name]) for name in ("red", "green", "blue")], channels(expected.hex_value))
                self.assertAlmostEqual(color["alpha"], expected.alpha, places=2)

    def test_every_color_name_the_renderer_knows_is_the_css_color_of_that_name(self):
        source = (SCRIPTS_PATH / "render" / "css_values.mjs").read_text(encoding="utf-8")
        for name, *rgb in NAMED_COLOR_PATTERN.findall(NAMED_COLORS_PATTERN.search(source).group(1)):
            with self.subTest(name=name):
                self.assertEqual([int(value) for value in rgb], channels(named_color_hex(name)))


if __name__ == "__main__":
    unittest.main()
