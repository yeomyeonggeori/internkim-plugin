from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re


DIGITS = "영일이삼사오육칠팔구"
SMALL_UNITS = ("", "십", "백", "천")
LARGE_UNITS = ("", "만", "억", "조", "경")
AMOUNT_PATTERN = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def parse_amount(text: object) -> Decimal | None:
    match = AMOUNT_PATTERN.search(str(text))
    if match is None:
        return None
    try:
        return Decimal(match.group().replace(",", ""))
    except InvalidOperation:
        return None


def korean_number_words(amount: int) -> str:
    if amount == 0:
        return DIGITS[0]
    groups = [(amount // 10_000**power) % 10_000 for power in range(len(LARGE_UNITS))]
    spoken = [
        korean_group_words(group) + LARGE_UNITS[power]
        for power, group in enumerate(groups)
        if group
    ]
    return "".join(reversed(spoken))


def korean_group_words(group: int) -> str:
    places = [(group // 10**power) % 10 for power in range(4)]
    return "".join(
        DIGITS[digit] + SMALL_UNITS[power]
        for power, digit in reversed(list(enumerate(places)))
        if digit
    )


def korean_amount_in_words(amount: int) -> str:
    return f"일금 {korean_number_words(amount)}원정"
