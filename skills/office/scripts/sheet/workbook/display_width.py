from __future__ import annotations

import unicodedata


def display_width(value) -> int:
    lines = str(value or "").split("\n")
    return max(sum(character_width(character) for character in line) for line in lines)


def character_width(character: str) -> int:
    return 2 if unicodedata.east_asian_width(character) in ("W", "F") else 1
