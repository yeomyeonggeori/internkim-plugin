from __future__ import annotations


# Excel specifications and limits (Microsoft Support, "Excel specifications and limits")
MAXIMUM_ROW = 1048576
MAXIMUM_COLUMN = 16384
MAXIMUM_SHEET_NAME_LENGTH = 31
FORBIDDEN_SHEET_NAME_CHARACTERS = frozenset("[]:*?/\\")
CELL_TEXT_LIMIT = 32767
FORMULA_LENGTH_LIMIT = 8192
CHART_TITLE_LIMIT = 255
HEADER_FOOTER_LIMIT = 255
LIST_LENGTH_LIMIT = 255
DEFAULT_SHEET_NAME = "Sheet1"


def column_number(letters: str) -> int:
    number = 0
    for letter in letters.upper():
        number = number * 26 + ord(letter) - ord("A") + 1
    return number


def column_letter(number: int) -> str:
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


LAST_COLUMN = column_letter(MAXIMUM_COLUMN)
SHEET_LIMITS = f"columns run from A to {LAST_COLUMN} and rows from 1 to {MAXIMUM_ROW}"
FORBIDDEN_SHEET_NAME_TEXT = " ".join(sorted(FORBIDDEN_SHEET_NAME_CHARACTERS, key="[]:*?/\\".index))


def fitting_sheet_name(name: str) -> str:
    kept = "".join("_" if character in FORBIDDEN_SHEET_NAME_CHARACTERS else character for character in name).strip("'")
    return kept[:MAXIMUM_SHEET_NAME_LENGTH].rstrip() or DEFAULT_SHEET_NAME
