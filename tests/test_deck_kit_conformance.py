from pathlib import Path
import re
import sys
import unittest


OFFICE_PATH = Path(__file__).resolve().parents[1] / "skills" / "office"
KIT_SCRIPT = (OFFICE_PATH / "assets" / "deck-kit" / "deck-kit.js").read_text(encoding="utf-8")
KIT_STYLE = (OFFICE_PATH / "assets" / "deck-kit" / "deck-kit.css").read_text(encoding="utf-8")
sys.path.insert(0, str(OFFICE_PATH / "scripts"))
sys.path.insert(0, str(OFFICE_PATH / "scripts" / "deck"))

from deck_definitions import KIT_LAYOUT_NAMES, KIT_LAYOUTS, kit_layout  # noqa: E402
from kit_fixes import DEAD_ZONE_ADVICE, LIST_ADVICE, PART_LABELS  # noqa: E402


def constant(source: str, name: str) -> str:
    return re.search(rf"const {name} = (.+?);", source).group(1)


def renderer_source(name: str) -> str:
    return (OFFICE_PATH / "scripts" / "render" / name).read_text(encoding="utf-8")


class KitConformanceTest(unittest.TestCase):
    def test_the_renderer_reads_the_attributes_the_kit_writes(self):
        self.assertEqual(constant(KIT_SCRIPT, "capacityAttribute"), constant(renderer_source("page_geometry.mjs"), "capacityAttribute"))
        self.assertEqual(constant(KIT_SCRIPT, "connectorLayerAttribute"), constant(renderer_source("native_connectors.mjs"), "nativeConnectorsAttribute"))

    def test_every_layout_that_counts_list_items_has_a_kit_diagram_and_no_other(self):
        planners = re.search(r"const diagramPlanners = \{(.*?)\n  \};", KIT_SCRIPT, re.DOTALL).group(1)
        drawn = set(re.findall(r"^\s+(\w+): ", planners, re.MULTILINE))
        counted = {layout.name for layout in KIT_LAYOUTS if any(part.items for part in layout.parts)}
        self.assertEqual(drawn, counted)

    def test_the_kit_grid_holds_as_many_cards_as_the_layout_allows(self):
        cards = next(part for part in kit_layout("cards").parts if part.selector == ".card")
        self.assertEqual(int(constant(KIT_SCRIPT, "gridCardCount")), cards.maximum)

    def test_the_stylesheet_styles_every_layout_the_checker_knows_and_no_other(self):
        self.assertEqual(set(re.findall(r'data-layout="(\w+)"', KIT_STYLE)), set(KIT_LAYOUT_NAMES))

    def test_the_kit_script_names_only_layouts_the_checker_knows(self):
        named = set(re.findall(r"data-layout='(\w+)'", KIT_SCRIPT)) | set(re.findall(r'"(\w+)"', constant(KIT_SCRIPT, "footerlessLayouts")))
        self.assertLessEqual(named, set(KIT_LAYOUT_NAMES))

    def test_the_kit_script_takes_its_layout_thresholds_from_the_build(self):
        self.assertNotIn("const geometryThresholds", renderer_source("render_html.mjs"))
        self.assertIn("request.geometryThresholds", renderer_source("render_html.mjs"))

    def test_advice_names_only_parts_and_layouts_the_kit_has(self):
        part_names = set(re.findall(r'\["[^"]+", "(\w+)"\]', constant(KIT_SCRIPT, "capacityPartNames")))
        self.assertLessEqual(set(PART_LABELS), part_names)
        self.assertLessEqual(set(DEAD_ZONE_ADVICE) | set(LIST_ADVICE), set(KIT_LAYOUT_NAMES))


if __name__ == "__main__":
    unittest.main()
