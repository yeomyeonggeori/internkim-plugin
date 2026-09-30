import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

OFFICE_SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"


def create_workbook(directory, rows):
    specification_path = Path(directory) / "spec.json"
    specification_path.write_text(json.dumps({"sheets": [{"title": "Sheet", "rows": rows}]}, ensure_ascii=False), encoding="utf-8")
    workbook_path = Path(directory) / "book.xlsx"
    completed = subprocess.run(
        [sys.executable, str(OFFICE_SCRIPTS_PATH / "sheet" / "create_xlsx.py"), str(workbook_path), "--spec", str(specification_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(OFFICE_SCRIPTS_PATH)},
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stdout + completed.stderr)
    return workbook_path


def column_width(rows, letter):
    from openpyxl import load_workbook

    with tempfile.TemporaryDirectory() as directory:
        return load_workbook(create_workbook(directory, rows))["Sheet"].column_dimensions[letter].width


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
