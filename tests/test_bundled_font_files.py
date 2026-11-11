from pathlib import Path
import sys
import unicodedata
import unittest

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from fonts.registry import BUNDLED_FAMILIES  # noqa: E402


# Default_Ignorable_Code_Point letters, Unicode DerivedCoreProperties.txt
INVISIBLE_LETTERS = frozenset("\u115f\u1160\u3164\uffa0")


def is_visible(character: str) -> bool:
    return unicodedata.category(character)[0] in "LNPS" and character not in INVISIBLE_LETTERS


def mapped_characters_drawing_nothing(font_path: Path) -> list[str]:
    font = TTFont(str(font_path), fontNumber=0)
    draws_nothing = outline_test(font)
    return [chr(code_point) for code_point, glyph_name in font.getBestCmap().items() if is_visible(chr(code_point)) and draws_nothing(glyph_name)]


def outline_test(font: TTFont):
    if "glyf" in font:
        return lambda glyph_name: has_no_glyph_data(font, font.getGlyphID(glyph_name))
    glyph_set = font.getGlyphSet()
    return lambda glyph_name: bounds(glyph_set, glyph_name) is None


def has_no_glyph_data(font: TTFont, glyph_index: int) -> bool:
    offsets = font["loca"]
    return offsets[glyph_index] == offsets[glyph_index + 1]


CONJOINING_JAMO_BLOCKS = ((0x1100, 0x11FF), (0xA960, 0xA97F), (0xD7B0, 0xD7FF))
# OpenType Hangul shaping, Microsoft Typography "Developing OpenType Fonts for Korean Hangul Script"
JAMO_FEATURES = frozenset({"ljmo", "vjmo", "tjmo"})


def maps_jamo_it_cannot_compose(font_path: Path) -> bool:
    font = TTFont(str(font_path), fontNumber=0)
    maps_jamo = any(start <= code_point <= end for code_point in font.getBestCmap() for start, end in CONJOINING_JAMO_BLOCKS)
    return maps_jamo and not JAMO_FEATURES <= substitution_features(font)


def substitution_features(font: TTFont) -> set[str]:
    if "GSUB" not in font:
        return set()
    return {record.FeatureTag for record in font["GSUB"].table.FeatureList.FeatureRecord}


def bounds(glyph_set, glyph_name: str):
    pen = BoundsPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return pen.bounds


class BundledFontFilesTest(unittest.TestCase):
    def test_every_bundled_face_maps_only_characters_it_draws(self):
        for family in BUNDLED_FAMILIES:
            for face in family.faces:
                with self.subTest(face=face.file_name):
                    self.assertEqual(mapped_characters_drawing_nothing(family.path(face))[:20], [])

    def test_every_bundled_face_that_maps_conjoining_jamo_composes_them(self):
        for family in BUNDLED_FAMILIES:
            for face in family.faces:
                with self.subTest(face=face.file_name):
                    self.assertFalse(maps_jamo_it_cannot_compose(family.path(face)))


if __name__ == "__main__":
    unittest.main()
