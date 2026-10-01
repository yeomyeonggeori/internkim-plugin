from __future__ import annotations

import re


THEME_SLOTS = ("lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink")
THEME_COLOR = re.compile(r"(?P<slot>[A-Za-z]+[0-9]?)(?:\s*(?P<sign>[+-])\s*(?P<percent>[0-9]{1,3})%)?")


def theme_reference(text: str) -> tuple[int, float] | None:
    match = THEME_COLOR.fullmatch(text.strip())
    slots = [slot.casefold() for slot in THEME_SLOTS]
    if match is None or match["slot"].casefold() not in slots or int(match["percent"] or 0) > 100:
        return None
    tint = int(match["percent"] or 0) / 100
    return slots.index(match["slot"].casefold()), -tint if match["sign"] == "-" else tint
