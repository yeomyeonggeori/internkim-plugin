from pathlib import Path
import sys
import unittest


OFFICE_SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(OFFICE_SCRIPTS_PATH))
sys.path.insert(0, str(OFFICE_SCRIPTS_PATH / "deck"))

from fonts.registry import DECK, FAMILIES, FONT_DIRECTORY, ROLE_GENERIC_FAMILIES, default_family, renderer_fonts, resolved_face  # noqa: E402
from native_preview import preview_font_path  # noqa: E402

HANGUL_SYLLABLES = range(0xAC00, 0xD7A4)
FAMILY_NOTES = ("OFL.txt", "README.md")


def shipped_font_files() -> set[Path]:
    return {path for path in FONT_DIRECTORY.rglob("*") if path.is_file() and path.name not in FAMILY_NOTES}


def registered_font_files() -> set[Path]:
    return {family.asset(face) for family in FAMILIES for face in family.faces}


class BundledFontRegistryTest(unittest.TestCase):
    def test_the_registry_names_every_shipped_font_file_and_nothing_else(self):
        self.assertEqual(shipped_font_files(), registered_font_files())

    def test_every_family_ships_its_license_and_a_readme_naming_each_file(self):
        for family in FAMILIES:
            with self.subTest(family=family.name):
                directory = FONT_DIRECTORY / family.directory
                self.assertIn("SIL Open Font License, Version 1.1", (directory / "OFL.txt").read_text(encoding="utf-8"))
                readme = (directory / "README.md").read_text(encoding="utf-8")
                for path in {path for path in registered_font_files() if path.parent == directory}:
                    self.assertIn(f"`{path.name}`", readme)

    def test_every_face_draws_every_hangul_syllable(self):
        from fontTools.ttLib import TTFont

        for path in sorted(path for path in registered_font_files() if path.suffix != ".woff2"):
            with self.subTest(font=path.name):
                with TTFont(str(path), lazy=True) as font:
                    covered = font.getBestCmap()
                self.assertEqual([code for code in HANGUL_SYLLABLES if code not in covered], [])

    def test_each_generic_family_keyword_reaches_exactly_one_family(self):
        generics = [entry["generic"] for entry in renderer_fonts() if entry["generic"]]
        self.assertEqual(set(generics), set(ROLE_GENERIC_FAMILIES.values()))
        for generic in ROLE_GENERIC_FAMILIES.values():
            self.assertEqual(len({entry["family"] for entry in renderer_fonts() if entry["generic"] == generic}), 1)

    def test_a_font_the_skill_does_not_ship_is_drawn_by_a_bundled_family_of_its_role(self):
        self.assertTrue(resolved_face("Times New Roman").is_substitute)
        self.assertEqual(resolved_face("Times New Roman").family, resolved_face("serif").family)
        self.assertEqual(resolved_face("An Unknown Family").family, resolved_face("sans-serif").family)
        self.assertEqual(resolved_face("Courier New").family, resolved_face("monospace").family)

    def test_a_face_is_found_by_the_family_name_its_file_carries(self):
        for family in FAMILIES:
            for face in family.faces:
                with self.subTest(face=face.file_name):
                    resolved = resolved_face(resolved_face(family.name, face.weight).typeface, face.weight)
                    self.assertEqual((resolved.family, resolved.face, resolved.is_substitute), (family, face, False))


class NativeReviewImageFontTest(unittest.TestCase):
    def test_native_review_images_draw_with_the_deck_family(self):
        deck = default_family(DECK)
        self.assertEqual(preview_font_path(False), deck.path(deck.face(400)))
        self.assertEqual(preview_font_path(True), deck.path(deck.face(700)))


if __name__ == "__main__":
    unittest.main()
