from __future__ import annotations

import re


GROUPED_NUMBER_PATTERN = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")
SPACED_SEPARATOR_PATTERN = re.compile(r",\s")
UNICODE_MINUS = "−"


def split_chart_list(text: str) -> list[str]:
    separator = r",\s+" if SPACED_SEPARATOR_PATTERN.search(text) else ","
    return [value.strip() for value in re.split(separator, text) if value.strip()]


def chart_number(text: str) -> float | None:
    compact = re.sub(r"\s", "", text).replace(UNICODE_MINUS, "-")
    if GROUPED_NUMBER_PATTERN.match(compact):
        compact = compact.replace(",", "")
    try:
        return float(compact)
    except ValueError:
        return None
