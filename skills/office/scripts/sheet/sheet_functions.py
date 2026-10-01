from __future__ import annotations

import math
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal, localcontext

from formula_references import REFERENCE_ERROR
import sheet_dates as dates
import sheet_semantics as semantics
from sheet_semantics import (
    BLANK,
    DIVIDE_BY_ZERO,
    ERROR,
    INVALID_NUMBER,
    INVALID_VALUE,
    LOGICAL,
    NOT_AVAILABLE,
    NUMBER,
    TEXT,
    ExcelError,
    Item,
    classify,
    grid,
    is_range,
)


DECIMAL_PRECISION = 700
DIGIT_LIMIT = 330


def number(argument) -> float:
    return semantics.to_number(classify(argument))


def integer(argument) -> int:
    return math.trunc(number(argument))


def text(argument) -> str:
    return semantics.to_text(classify(argument))


def logical(argument) -> bool:
    return semantics.to_logical(classify(argument))


def optional_number(argument, default: float) -> float:
    return default if argument is None else number(argument)


def IF(logical_test, value_if_true, value_if_false=None):
    chosen = value_if_true if logical(logical_test()) else value_if_false
    return False if chosen is None else chosen()


def IFERROR(value, value_if_error):
    return value_if_error if classify(value).kind == ERROR else value


def IFNA(value, value_if_na):
    return value_if_na if is_error_code(value, NOT_AVAILABLE) else value


def is_error_code(value, code: str) -> bool:
    item = classify(value)
    return item.kind == ERROR and item.value.code == code


def logicals_in(arguments) -> list[bool]:
    values = []
    for argument in arguments:
        if not is_range(argument):
            values.append(logical(argument))
            continue
        for item in (item for row in grid(argument) for item in row):
            if item.kind == ERROR:
                raise item.value
            if item.kind in (NUMBER, LOGICAL):
                values.append(bool(item.value))
    if not values:
        raise ExcelError(INVALID_VALUE, "no logical values")
    return values


def AND(*arguments):
    return all(logicals_in(arguments))


def OR(*arguments):
    return any(logicals_in(arguments))


def NOT(value):
    return not logical(value)


def CHOOSE(index_number, *values):
    index = integer(index_number)
    if not 1 <= index <= len(values):
        raise ExcelError(INVALID_VALUE, "the index is outside the choices")
    return values[index - 1]


def vector(argument) -> list[Item]:
    rows = grid(argument)
    if len(rows) != 1 and len(rows[0]) != 1:
        raise ExcelError(NOT_AVAILABLE, "the lookup range is not one row or one column")
    return [item for row in rows for item in row]


def matching_index(lookup_value, items: list[Item], match_type: float):
    target = classify(lookup_value)
    if target.kind == ERROR:
        raise target.value
    if match_type == 0:
        return exact_index(target, items)
    if match_type != 1:
        raise NotImplementedError("only exact and ascending matches are evaluated")
    return ascending_index(target, items)


def exact_index(target: Item, items: list[Item]):
    if target.kind == TEXT:
        matches = semantics.text_test("=", target.value)
    else:
        matches = lambda item: item.kind == target.kind and semantics.order(item, target) == 0
    return next((index for index, item in enumerate(items) if matches(item)), None)


def ascending_index(target: Item, items: list[Item]):
    comparable = [item for item in items if item.kind == target.kind]
    ordered = [semantics.order(left, right) <= 0 for left, right in zip(comparable, comparable[1:])]
    if not all(ordered):
        raise NotImplementedError("an unsorted approximate match is not evaluated")
    candidates = [index for index, item in enumerate(items) if item.kind == target.kind and semantics.order(item, target) <= 0]
    return candidates[-1] if candidates else None


def MATCH(lookup_value, lookup_array, match_type=None):
    index = matching_index(lookup_value, vector(lookup_array), optional_number(match_type, 1))
    if index is None:
        raise ExcelError(NOT_AVAILABLE, "no match")
    return index + 1


def INDEX(array, row_number, column_number=None):
    rows = grid(array)
    row_index, column_index = index_position(rows, row_number, column_number)
    if not (1 <= row_index <= len(rows) and 1 <= column_index <= len(rows[0])):
        raise ExcelError(REFERENCE_ERROR, "index outside the array")
    return rows[row_index - 1][column_index - 1]


def index_position(rows: list, row_number, column_number) -> tuple[int, int]:
    row_index = integer(row_number)
    if column_number is not None:
        return row_index, integer(column_number)
    if len(rows) == 1:
        return 1, row_index
    if len(rows[0]) == 1:
        return row_index, 1
    raise NotImplementedError("a whole row or column is not evaluated")


def VLOOKUP(lookup_value, table_array, column_number, range_lookup=None):
    rows = grid(table_array)
    column_index = integer(column_number)
    if not 1 <= column_index <= len(rows[0]):
        raise ExcelError(REFERENCE_ERROR, "column number outside the table")
    is_approximate = True if range_lookup is None else logical(range_lookup)
    index = matching_index(lookup_value, [row[0] for row in rows], 1 if is_approximate else 0)
    if index is None:
        raise ExcelError(NOT_AVAILABLE, "value not found in the first column")
    return rows[index][column_index - 1]


def rounded(amount: float, places: int, rounding: str) -> float:
    bounded_places = max(-DIGIT_LIMIT, min(DIGIT_LIMIT, places))
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        return float(Decimal(repr(amount)).quantize(Decimal(1).scaleb(-bounded_places), rounding=rounding))


def ROUND(value, digits):
    return rounded(number(value), integer(digits), ROUND_HALF_UP)


def ROUNDUP(value, digits):
    return rounded(number(value), integer(digits), ROUND_UP)


def ROUNDDOWN(value, digits):
    return rounded(number(value), integer(digits), ROUND_DOWN)


def TRUNC(value, digits=None):
    return rounded(number(value), 0 if digits is None else integer(digits), ROUND_DOWN)


def INT(value):
    return math.floor(number(value))


def ABS(value):
    return abs(number(value))


def SIGN(value):
    amount = number(value)
    return (amount > 0) - (amount < 0)


def MOD(value, divisor):
    amount, by = number(value), number(divisor)
    if by == 0:
        raise ExcelError(DIVIDE_BY_ZERO)
    return amount % by


def SQRT(value):
    amount = number(value)
    if amount < 0:
        raise ExcelError(INVALID_NUMBER, "the square root of a negative number")
    return math.sqrt(amount)


def EXP(value):
    return math.exp(number(value))


def positive(value) -> float:
    amount = number(value)
    if amount <= 0:
        raise ExcelError(INVALID_NUMBER, "the logarithm of a number that is not positive")
    return amount


def LN(value):
    return math.log(positive(value))


def LOG10(value):
    return math.log10(positive(value))


def LOG(value, base=None):
    amount = positive(value)
    base_amount = 10 if base is None else positive(base)
    if base_amount == 1:
        raise ExcelError(DIVIDE_BY_ZERO)
    return math.log10(amount) if base_amount == 10 else math.log(amount) / math.log(base_amount)


def PI():
    return math.pi


def EVEN(value):
    amount = number(value)
    return math.copysign(math.ceil(abs(amount) / 2) * 2, amount)


def FACT(value):
    amount = number(value)
    if amount < 0:
        raise ExcelError(INVALID_NUMBER, "the factorial of a negative number")
    return float(math.factorial(math.trunc(amount)))


def multiple_of(value, significance, rounds_up: bool) -> float:
    amount, step = Decimal(repr(number(value))), Decimal(repr(number(significance)))
    if step == 0 and rounds_up:
        return 0
    if step == 0:
        raise ExcelError(DIVIDE_BY_ZERO)
    if amount > 0 and step < 0:
        raise ExcelError(INVALID_NUMBER, "a positive number with a negative significance")
    quotient = amount / step
    return float((math.ceil(quotient) if rounds_up else math.floor(quotient)) * step)


def CEILING(value, significance):
    return multiple_of(value, significance, rounds_up=True)


def FLOOR(value, significance):
    return multiple_of(value, significance, rounds_up=False)


def POWER(base, exponent):
    return semantics.power(number(base), number(exponent))


def LEN(value):
    return len(text(value))


def character_count(count) -> int:
    amount = 1 if count is None else integer(count)
    if amount < 0:
        raise ExcelError(INVALID_VALUE, "a negative character count")
    return amount


def LEFT(value, count=None):
    return text(value)[:character_count(count)]


def RIGHT(value, count=None):
    amount = character_count(count)
    return text(value)[-amount:] if amount else ""


def MID(value, start, count):
    first, amount = integer(start), integer(count)
    if first < 1 or amount < 0:
        raise ExcelError(INVALID_VALUE, "a start before the first character or a negative count")
    return text(value)[first - 1:first - 1 + amount]


def UPPER(value):
    return text(value).upper()


def LOWER(value):
    return text(value).lower()


def EXACT(left, right):
    return text(left) == text(right)


def FIND(find_text, within_text, start=None):
    sought, within = text(find_text), text(within_text)
    first = 1 if start is None else integer(start)
    if not 1 <= first <= len(within) + 1:
        raise ExcelError(INVALID_VALUE, "the start is outside the text")
    position = within.find(sought, first - 1)
    if position < 0:
        raise ExcelError(INVALID_VALUE, "the text was not found")
    return position + 1


def REPLACE(old_text, start, count, new_text):
    original, first, amount = text(old_text), integer(start), integer(count)
    if first < 1 or amount < 0:
        raise ExcelError(INVALID_VALUE, "a start before the first character or a negative count")
    return original[:first - 1] + text(new_text) + original[first - 1 + amount:]


def TRIM(value):
    return " ".join(word for word in text(value).split(" ") if word)


def CONCATENATE(*arguments):
    return semantics.concatenate_items(arguments)


def ISBLANK(value):
    return classify(value).kind == BLANK


def ISNUMBER(value):
    return classify(value).kind == NUMBER


def ISTEXT(value):
    return classify(value).kind == TEXT


def ISERROR(value):
    return classify(value).kind == ERROR


def ISNA(value):
    return is_error_code(value, NOT_AVAILABLE)


def ISERR(value):
    return ISERROR(value) and not ISNA(value)


def NA():
    raise ExcelError(NOT_AVAILABLE)


def TRUE():
    return True


def FALSE():
    return False


def cash_flows(arguments) -> list[float]:
    flows = []
    for argument in arguments:
        items = [item for row in grid(argument) for item in row]
        if any(item.kind == ERROR for item in items):
            raise NotImplementedError("an error among the cash flows is not evaluated")
        if is_range(argument):
            flows.extend(item.value for item in items if item.kind == NUMBER)
        elif items[0].kind in (NUMBER, LOGICAL):
            flows.append(float(items[0].value))
        else:
            raise NotImplementedError("a cash flow typed as text or left empty is not evaluated")
    return flows


def NPV(rate, *values):
    discount = 1 + number(rate)
    if discount == 0:
        raise ExcelError(DIVIDE_BY_ZERO)
    return math.fsum(flow / discount ** period for period, flow in enumerate(cash_flows(values), start=1))


def PMT(rate, periods, present_value, future_value=None, payment_type=None):
    interest, count, principal = number(rate), number(periods), number(present_value)
    remaining = optional_number(future_value, 0)
    timing = 1 if optional_number(payment_type, 0) != 0 else 0
    if count == 0:
        raise ExcelError(INVALID_NUMBER, "no payment periods")
    if interest == 0:
        return -(principal + remaining) / count
    growth = (1 + interest) ** count
    return -(remaining + principal * growth) / ((1 + interest * timing) * (growth - 1) / interest)


def DATE(year, month, day):
    return dates.serial_from_parts(integer(year), integer(month), integer(day))


def YEAR(value):
    return dates.date_from_serial(number(value)).year


def MONTH(value):
    return dates.date_from_serial(number(value)).month


def DAY(value):
    return dates.date_from_serial(number(value)).day


def WEEKDAY(value, return_type=None):
    return dates.weekday(dates.date_from_serial(number(value)), 1 if return_type is None else integer(return_type))


def EDATE(start, months):
    return dates.serial_from_date(dates.months_later(dates.date_from_serial(number(start)), integer(months)))


def EOMONTH(start, months):
    return dates.serial_from_date(dates.month_end(dates.months_later(dates.date_from_serial(number(start)), integer(months))))


def DATEDIF(start, end, unit):
    return dates.difference(dates.date_from_serial(number(start)), dates.date_from_serial(number(end)), text(unit).upper())


def TODAY():
    return dates.today_serial()


def NOW():
    return dates.now_serial()


LAZY_FUNCTIONS = frozenset(("IF",))

FUNCTIONS = {
    "SUM": semantics.sum_numbers,
    "AVERAGE": semantics.average_numbers,
    "MAX": semantics.maximum,
    "MIN": semantics.minimum,
    "COUNT": semantics.count_numbers,
    "COUNTA": semantics.count_filled,
    "COUNTBLANK": semantics.count_blank,
    "SUMIF": semantics.sumif,
    "SUMIFS": semantics.sumifs,
    "COUNTIF": semantics.countif,
    "COUNTIFS": semantics.countifs,
    "AVERAGEIF": semantics.averageif,
    "AVERAGEIFS": semantics.averageifs,
    "SUMPRODUCT": semantics.sumproduct,
    "CONCAT": CONCATENATE,
    **{
        function.__name__: function
        for function in (
            IF, IFERROR, IFNA, AND, OR, NOT, CHOOSE, MATCH, INDEX, VLOOKUP,
            ROUND, ROUNDUP, ROUNDDOWN, TRUNC, INT, ABS, SIGN, MOD, SQRT, EXP, LN, LOG10, LOG, PI, EVEN, FACT,
            CEILING, FLOOR, POWER,
            LEN, LEFT, RIGHT, MID, UPPER, LOWER, EXACT, FIND, REPLACE, TRIM, CONCATENATE,
            ISBLANK, ISNUMBER, ISTEXT, ISERROR, ISERR, ISNA, NA, TRUE, FALSE,
            NPV, PMT, DATE, YEAR, MONTH, DAY, WEEKDAY, EDATE, EOMONTH, DATEDIF, TODAY, NOW,
        )
    },
}

OPERATORS = {
    "+": semantics.arithmetic(lambda left, right: left + right),
    "-": semantics.arithmetic(lambda left, right: left - right),
    "*": semantics.arithmetic(lambda left, right: left * right),
    "/": semantics.arithmetic(semantics.divide),
    "^": semantics.arithmetic(semantics.power),
    "&": semantics.concatenate_operator,
    "=": semantics.comparison(lambda order: order == 0),
    "<>": semantics.comparison(lambda order: order != 0),
    ">": semantics.comparison(lambda order: order > 0),
    "<": semantics.comparison(lambda order: order < 0),
    ">=": semantics.comparison(lambda order: order >= 0),
    "<=": semantics.comparison(lambda order: order <= 0),
}

PREFIX_OPERATORS = {
    "-": semantics.negate,
    "+": lambda value: value,
}

POSTFIX_OPERATORS = {
    "%": semantics.percent,
}
