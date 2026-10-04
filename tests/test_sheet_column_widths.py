import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from sheet_fixture import run_office_python


def column_width(rows, letter):
    with tempfile.TemporaryDirectory() as directory:
        run_office_python(f"""
            from sheet.tabular_workbook import create_workbook
            create_workbook({{"sheets": [{{"title": "Sheet", "rows": {json.dumps(rows, ensure_ascii=False)}}}]}}).save("book.xlsx")
        """, directory)
        return load_workbook(Path(directory) / "book.xlsx")["Sheet"].column_dimensions[letter].width


class KoreanColumnWidthTest(unittest.TestCase):
    def test_wide_characters_count_as_two(self):
        self.assertEqual(column_width([["상호"], ["주식회사 여명거리"]], "A"), 19)

    def test_latin_text_keeps_one_per_character(self):
        self.assertEqual(column_width([["name"], ["Yeomyeong Geori Inc"]], "A"), 21)

    def test_a_multi_line_cell_is_measured_by_its_longest_line(self):
        self.assertEqual(column_width([["메모"], ["가나다라마바사\nabc"]], "A"), 16)

    def test_width_stays_within_the_existing_clamp(self):
        self.assertEqual(column_width([["제목"], ["가" * 60]], "A"), 48)
        self.assertEqual(column_width([["a"], ["b"]], "A"), 10)


if __name__ == "__main__":
    unittest.main()
