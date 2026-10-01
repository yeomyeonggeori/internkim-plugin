from __future__ import annotations

import re

from core.office_theme import THEME_SLOTS


THEME_COLOR = re.compile(r"(?P<slot>[A-Za-z]+[0-9]?)(?:\s*(?P<sign>[+-])\s*(?P<percent>[0-9]{1,3})%)?")


def theme_reference(text: str) -> tuple[int, float] | None:
    match = THEME_COLOR.fullmatch(text.strip())
    slots = [slot.casefold() for slot in THEME_SLOTS]
    if match is None or match["slot"].casefold() not in slots or int(match["percent"] or 0) > 100:
        return None
    tint = int(match["percent"] or 0) / 100
    return slots.index(match["slot"].casefold()), -tint if match["sign"] == "-" else tint
