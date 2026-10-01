from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))

from core.office_schema import closest_name  # noqa: E402


OPERATIONS = ["set_cell", "set_range", "delete_chart", "hide_sheet", "rename_sheet", "add_table", "add_chart", "format_range"]


class ClosestNameTest(unittest.TestCase):
    def test_a_misspelled_name_finds_the_name_it_meant(self):
        cases = {"set_cel": "set_cell", "setcell": "set_cell", "formatrange": "format_range", "add_charts": "add_chart"}
        for written, meant in cases.items():
            with self.subTest(written=written):
                self.assertEqual(closest_name(written, OPERATIONS), meant)

    def test_an_operation_that_does_not_exist_is_not_steered_to_a_different_one(self):
        for written in ("delete_sheet", "duplicate_sheet", "protect_sheet", "add_image"):
            with self.subTest(written=written):
                self.assertIsNone(closest_name(written, OPERATIONS))

    def test_fields_layouts_and_sheet_names_match_across_casing_and_scripts(self):
        self.assertEqual(closest_name("colour", ["fontColor", "fill", "bold"]), "fontColor")
        self.assertEqual(closest_name("number_format", ["numberFormat", "fill"]), "numberFormat")
        self.assertEqual(closest_name("Heading1", ["Heading 1", "Heading 2", "Title"]), "Heading 1")
        self.assertEqual(closest_name("실젹", ["실적", "요약", "월별"]), "실적")

    def test_a_word_that_means_a_field_names_that_field(self):
        self.assertEqual(closest_name("data", ["dataLabels", "range", "title"]), "range")
        self.assertEqual(closest_name("data", ["title", "rows", "heading"]), "rows")
        self.assertEqual(closest_name("name", ["title", "rows"]), "title")
        self.assertEqual(closest_name("title", ["name", "index"]), "name")

    def test_a_tie_suggests_nothing(self):
        self.assertIsNone(closest_name("colr", ["fillColr", "fontColr"]))


if __name__ == "__main__":
    unittest.main()
