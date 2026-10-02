from __future__ import annotations


HANGUL_RANGES = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))
EAST_ASIAN_RANGES = ((0x1100, 0x11FF), (0x2E80, 0x9FFF), (0xAC00, 0xD7AF), (0xF900, 0xFAFF), (0xFF00, 0xFFEF))


def in_ranges(character: str, ranges: tuple[tuple[int, int], ...]) -> bool:
    code = ord(character)
    return any(low <= code <= high for low, high in ranges)


def is_hangul(character: str) -> bool:
    return in_ranges(character, HANGUL_RANGES)


def is_east_asian(character: str) -> bool:
    return in_ranges(character, EAST_ASIAN_RANGES)


def is_ideograph(character: str) -> bool:
    return is_east_asian(character) and not is_hangul(character)


def has_hangul(text: str) -> bool:
    return any(is_hangul(character) for character in text)


def has_east_asian(text: str) -> bool:
    return any(is_east_asian(character) for character in text)


def hangul_count(text: str) -> int:
    return sum(1 for character in text if is_hangul(character))
