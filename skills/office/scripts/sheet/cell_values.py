from __future__ import annotations

import csv
import re
from datetime import date

INTEGER_OR_DECIMAL = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
MAXIMUM_SIGNIFICANT_DIGITS = 15
DISPLAYED_NUMBER = re.compile(r"(?P<open>\()?(?P<sign>[-−])?(?P<currency>[₩$€£¥])?(?P<digits>\d{1,3}(?:,\d{3})+|\d+)(?P<fraction>\.\d+)?(?P<percent>%)?(?P<unit>원)?(?P<close>\))?")
DISPLAYED_DATE = re.compile(r"(?P<year>\d{4})[-./](?P<month>\d{1,2})[-./](?P<day>\d{1,2})\.?")
DATE_FORMAT = "yyyy-mm-dd"


def typed_cell_value(text):
    return typed_number(text) if INTEGER_OR_DECIMAL.fullmatch(text) else text


def argument_row(text: str) -> list:
    return [typed_cell_value(cell.strip()) for cell in next(csv.reader([text], skipinitialspace=True), [])]


def typed_number(text):
    if count_significant_digits(text) > MAXIMUM_SIGNIFICANT_DIGITS:
        return text
    return float(text) if "." in text else int(text)


def count_significant_digits(text):
    return len(text.replace("-", "").replace(".", "").lstrip("0"))


def typed_date(text):
    try:
        return date.fromisoformat(text)
    except ValueError:
        return text


def typed_text(text: str) -> tuple[object, str | None]:
    stripped = text.strip()
    number = DISPLAYED_NUMBER.fullmatch(stripped)
    if number and is_number_shape(number):
        return number_value(number)
    displayed_date = DISPLAYED_DATE.fullmatch(stripped)
    if displayed_date:
        return date_value(displayed_date, stripped)
    return (text if text else None), None


def is_number_shape(match) -> bool:
    if bool(match["open"]) != bool(match["close"]):
        return False
    if match["percent"] and match["unit"]:
        return False
    digits = match["digits"]
    return "," in digits or digits == "0" or not digits.startswith("0")


def number_value(match) -> tuple[float | int, str | None]:
    digits = match["digits"].replace(",", "")
    fraction = match["fraction"] or ""
    value = float(digits + fraction) if fraction else int(digits)
    if match["open"] or match["sign"]:
        value = -value
    decimals = "." + "0" * (len(fraction) - 1) if fraction else ""
    if match["percent"]:
        return value / 100, f"0{decimals}%"
    if match["currency"] is not None:
        return value, f'"{match["currency"]}"#,##0{decimals}'
    if match["unit"] is not None:
        return value, f'#,##0{decimals}"{match["unit"]}"'
    if "," in match["digits"]:
        return value, f"#,##0{decimals}"
    return value, None


def date_value(match, text: str) -> tuple[object, str | None]:
    try:
        return date(int(match["year"]), int(match["month"]), int(match["day"])), DATE_FORMAT
    except ValueError:
        return text, None
