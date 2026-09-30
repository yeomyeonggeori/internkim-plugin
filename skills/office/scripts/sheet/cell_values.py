from __future__ import annotations

import re
from datetime import date

INTEGER_OR_DECIMAL = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
MAXIMUM_SIGNIFICANT_DIGITS = 15


def typed_cell_value(text):
    if INTEGER_OR_DECIMAL.fullmatch(text):
        return typed_number(text)
    if ISO_DATE.fullmatch(text):
        return typed_date(text)
    return text


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
