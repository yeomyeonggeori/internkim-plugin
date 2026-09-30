from decimal import ROUND_DOWN, Decimal, InvalidOperation
import re


VAT_RATE_PERCENT = 10
ROUNDING_RULE = "every computed amount drops its fraction below one won (truncates toward zero)"

DIGITS = "영일이삼사오육칠팔구"
SMALL_UNITS = ("", "십", "백", "천")
LARGE_UNITS = ("", "만", "억", "조", "경")
AMOUNT_PATTERN = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def truncate_to_won(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_DOWN))


def row_amount(quantity: Decimal, unit_price: Decimal) -> int:
    return truncate_to_won(quantity * unit_price)


def supply_total(row_amounts: list[int]) -> int:
    return sum(row_amounts)


def value_added_tax(supply: int) -> int:
    return truncate_to_won(Decimal(supply) * VAT_RATE_PERCENT / 100)


def vat_total(row_vats: list[int]) -> int:
    return sum(row_vats)


def grand_total(supply: int, tax: int) -> int:
    return supply + tax


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
