from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Callable


BLANK = "blank"
NUMBER = "number"
TEXT = "text"
LOGICAL = "logical"
ERROR = "error"
TYPE_RANK = {NUMBER: 0, TEXT: 1, LOGICAL: 2}
CRITERIA_PATTERN = re.compile(r"^(>=|<=|<>|>|<|=)?(.*)$", re.DOTALL)

DIVIDE_BY_ZERO = "#DIV/0!"
INVALID_VALUE = "#VALUE!"
UNKNOWN_NAME = "#NAME?"
INVALID_NUMBER = "#NUM!"
NOT_AVAILABLE = "#N/A"


class ExcelError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code


@dataclass(frozen=True)
class Item:
    kind: str
    value: object


@dataclass(frozen=True)
class Range:
    rows: list


def classify(argument) -> Item:
    if not is_range(argument):
        return argument
    if len(argument.rows) == 1 and len(argument.rows[0]) == 1:
        return argument.rows[0][0]
    raise NotImplementedError("array arithmetic is not evaluated")


def grid(argument) -> list[list[Item]]:
    return argument.rows if is_range(argument) else [[argument]]


def is_range(argument) -> bool:
    return isinstance(argument, Range)


def first_error(items: list[Item]):
    return next((item.value for item in items if item.kind == ERROR), None)


def to_number(item: Item) -> float:
    if item.kind == BLANK:
        return 0.0
    if item.kind in (NUMBER, LOGICAL):
        return float(item.value)
    if item.kind == TEXT:
        return parse_number_text(item.value)
    raise item.value


def parse_number_text(text: str) -> float:
    try:
        return float(text.strip())
    except ValueError as error:
        raise ExcelError(INVALID_VALUE, f"{text!r} is not a number") from error


def to_logical(item: Item) -> bool:
    if item.kind == BLANK:
        return False
    if item.kind == LOGICAL:
        return item.value
    if item.kind == NUMBER:
        return item.value != 0
    if item.kind == TEXT and item.value.upper() in ("TRUE", "FALSE"):
        return item.value.upper() == "TRUE"
    if item.kind == TEXT:
        raise ExcelError(INVALID_VALUE, f"{item.value!r} is not TRUE or FALSE")
    raise item.value


def number_text(number: float) -> str:
    if number.is_integer() and abs(number) < 1e15:
        return str(int(number))
    return f"{number:.15g}"


def to_text(item: Item) -> str:
    if item.kind == BLANK:
        return ""
    if item.kind == NUMBER:
        return number_text(item.value)
    if item.kind == LOGICAL:
        return "TRUE" if item.value else "FALSE"
    if item.kind == TEXT:
        return item.value
    raise item.value


def arithmetic(operation: Callable[[float, float], float]) -> Callable:
    def operator(left, right):
        return operation(to_number(classify(left)), to_number(classify(right)))
    return operator


def divide(left: float, right: float) -> float:
    if right == 0:
        raise ExcelError(DIVIDE_BY_ZERO)
    return left / right


def power(base: float, exponent: float) -> float:
    if base == 0 and exponent == 0:
        raise ExcelError(INVALID_NUMBER, "0 to the power 0")
    if base == 0 and exponent < 0:
        raise ExcelError(DIVIDE_BY_ZERO)
    result = base ** exponent
    if isinstance(result, complex):
        raise ExcelError(INVALID_NUMBER, "a negative base with a fractional exponent")
    return result


def negate(value):
    return -to_number(classify(value))


def percent(value):
    return to_number(classify(value)) / 100


def comparison_operands(left: Item, right: Item) -> tuple[Item, Item]:
    return fill_blank(left, right), fill_blank(right, left)


def fill_blank(item: Item, other: Item) -> Item:
    if item.kind != BLANK or other.kind == BLANK:
        return item
    if other.kind == TEXT:
        return Item(TEXT, "")
    if other.kind == LOGICAL:
        return Item(LOGICAL, False)
    return Item(NUMBER, 0.0)


def order(left: Item, right: Item) -> int:
    if left.kind == BLANK and right.kind == BLANK:
        return 0
    left, right = comparison_operands(left, right)
    if left.kind != right.kind:
        return -1 if TYPE_RANK[left.kind] < TYPE_RANK[right.kind] else 1
    left_key = left.value.casefold() if left.kind == TEXT else left.value
    right_key = right.value.casefold() if right.kind == TEXT else right.value
    return (left_key > right_key) - (left_key < right_key)


def comparison(accepts: Callable[[int], bool]) -> Callable:
    def operator(left, right):
        left_item, right_item = classify(left), classify(right)
        error = first_error([left_item, right_item])
        return error if error is not None else accepts(order(left_item, right_item))
    return operator


def concatenate_operator(left, right):
    return to_text(classify(left)) + to_text(classify(right))


def concatenate_items(arguments) -> object:
    items = [item for argument in arguments for row in grid(argument) for item in row]
    error = first_error(items)
    return error if error is not None else "".join(to_text(item) for item in items)


def numbers_in(arguments) -> list[float]:
    numbers = []
    for argument in arguments:
        if is_range(argument):
            numbers.extend(range_numbers(argument))
        else:
            numbers.append(typed_number(argument))
    return numbers


def range_numbers(argument) -> list[float]:
    items = [item for row in grid(argument) for item in row]
    error = first_error(items)
    if error is not None:
        raise error
    return [item.value for item in items if item.kind == NUMBER]


def typed_number(item: Item) -> float:
    if item.kind == BLANK:
        raise NotImplementedError("an empty argument to an aggregate is not evaluated")
    return to_number(item)


def sum_numbers(*arguments):
    return math.fsum(numbers_in(arguments))


def average_numbers(*arguments):
    numbers = numbers_in(arguments)
    if not numbers:
        raise ExcelError(DIVIDE_BY_ZERO)
    return math.fsum(numbers) / len(numbers)


def maximum(*arguments):
    numbers = numbers_in(arguments)
    return max(numbers) if numbers else 0


def minimum(*arguments):
    numbers = numbers_in(arguments)
    return min(numbers) if numbers else 0


def count_numbers(*arguments):
    return sum(1 for argument in arguments for row in grid(argument) for item in row if item.kind == NUMBER)


def count_filled(*arguments):
    return sum(1 for argument in arguments for row in grid(argument) for item in row if item.kind != BLANK)


def count_blank(range_argument):
    return sum(1 for row in grid(range_argument) for item in row if item.kind == BLANK or (item.kind == TEXT and item.value == ""))


def wildcard_pattern(text: str) -> re.Pattern:
    pieces = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == "~" and index + 1 < len(text):
            pieces.append(re.escape(text[index + 1]))
            index += 2
            continue
        pieces.append(".*" if character == "*" else "." if character == "?" else re.escape(character))
        index += 1
    return re.compile("".join(pieces), re.IGNORECASE | re.DOTALL)


def criteria_test(criteria) -> Callable[[Item], bool]:
    item = classify(criteria)
    if item.kind == ERROR:
        raise item.value
    if item.kind == BLANK:
        return numeric_test("=", 0.0)
    if item.kind == NUMBER:
        return numeric_test("=", item.value)
    if item.kind == LOGICAL:
        return lambda cell: cell.kind == LOGICAL and cell.value == item.value
    operator, operand = CRITERIA_PATTERN.match(item.value).groups()
    return operand_test(operator or "=", operand)


def operand_test(operator: str, operand: str) -> Callable[[Item], bool]:
    stripped = operand.strip()
    try:
        return numeric_test(operator, float(stripped))
    except ValueError:
        pass
    if stripped.upper() in ("TRUE", "FALSE"):
        expected = stripped.upper() == "TRUE"
        return lambda cell: (cell.kind == LOGICAL and cell.value == expected) == (operator != "<>")
    if operand == "":
        return lambda cell: (cell.kind == BLANK or cell.kind == TEXT and cell.value == "") == (operator in ("=", ""))
    return text_test(operator, operand)


def numeric_test(operator: str, expected: float) -> Callable[[Item], bool]:
    comparisons = {"=": lambda value: value == expected, "<>": lambda value: value != expected, ">": lambda value: value > expected, "<": lambda value: value < expected, ">=": lambda value: value >= expected, "<=": lambda value: value <= expected}
    compare = comparisons[operator]

    def test(cell: Item) -> bool:
        if cell.kind == NUMBER:
            return compare(cell.value)
        if cell.kind == TEXT and operator in ("=", "<>"):
            return compare_numeric_text(cell.value, compare, operator)
        return operator == "<>"
    return test


def compare_numeric_text(text: str, compare: Callable[[float], bool], operator: str) -> bool:
    try:
        return compare(float(text.strip()))
    except ValueError:
        return operator == "<>"


def text_test(operator: str, operand: str) -> Callable[[Item], bool]:
    if operator in ("=", "<>"):
        pattern = wildcard_pattern(operand)
        return lambda cell: (cell.kind == TEXT and pattern.fullmatch(cell.value) is not None) == (operator == "=")
    ordered = {">": lambda order_value: order_value > 0, "<": lambda order_value: order_value < 0, ">=": lambda order_value: order_value >= 0, "<=": lambda order_value: order_value <= 0}[operator]
    return lambda cell: cell.kind == TEXT and ordered(order(cell, Item(TEXT, operand)))


def matching_positions(range_argument, criteria) -> list[tuple[int, int]]:
    test = criteria_test(classify_scalar(criteria))
    return [(row_index, column_index) for row_index, row in enumerate(grid(range_argument)) for column_index, item in enumerate(row) if test(item)]


def classify_scalar(criteria) -> Item:
    return criteria.rows[0][0] if is_range(criteria) else criteria


def intersect(position_lists: list[list[tuple[int, int]]]) -> list[tuple[int, int]]:
    common = set(position_lists[0])
    for positions in position_lists[1:]:
        common &= set(positions)
    return sorted(common)


def criteria_positions(pairs) -> list[tuple[int, int]]:
    if len(pairs) % 2 != 0 or not pairs:
        raise ExcelError(INVALID_VALUE, "criteria come as range and criterion pairs")
    shapes = {shape_of(range_argument) for range_argument in pairs[0::2]}
    if len(shapes) != 1:
        raise ExcelError(INVALID_VALUE, "criteria ranges differ in size")
    return intersect([matching_positions(pairs[index], pairs[index + 1]) for index in range(0, len(pairs), 2)])


def shape_of(range_argument) -> tuple[int, int]:
    rows = grid(range_argument)
    return len(rows), len(rows[0]) if rows else 0


def values_at(range_argument, positions: list[tuple[int, int]], expected_shape: tuple[int, int]) -> list[Item]:
    if shape_of(range_argument) != expected_shape:
        raise NotImplementedError("a summed range of another size is not evaluated")
    rows = grid(range_argument)
    return [rows[row_index][column_index] for row_index, column_index in positions]


def sum_items(items: list[Item]) -> float:
    error = first_error(items)
    if error is not None:
        raise error
    return math.fsum(item.value for item in items if item.kind == NUMBER)


def summed_items(sum_range, criteria_pairs) -> list[Item]:
    positions = criteria_positions(criteria_pairs)
    return values_at(sum_range, positions, shape_of(criteria_pairs[0]))


def sumif(range_argument, criteria, sum_range=None):
    return sum_items(summed_items(sum_range if sum_range is not None else range_argument, [range_argument, criteria]))


def sumifs(sum_range, *criteria_pairs):
    return sum_items(summed_items(sum_range, list(criteria_pairs)))


def countif(range_argument, criteria):
    return len(criteria_positions([range_argument, criteria]))


def countifs(*criteria_pairs):
    return len(criteria_positions(list(criteria_pairs)))


def average_items(items: list[Item]) -> float:
    error = first_error(items)
    if error is not None:
        raise error
    numbers = [item.value for item in items if item.kind == NUMBER]
    if not numbers:
        raise ExcelError(DIVIDE_BY_ZERO)
    return math.fsum(numbers) / len(numbers)


def averageif(range_argument, criteria, average_range=None):
    return average_items(summed_items(average_range if average_range is not None else range_argument, [range_argument, criteria]))


def averageifs(average_range, *criteria_pairs):
    return average_items(summed_items(average_range, list(criteria_pairs)))


def sumproduct(*arrays):
    grids = [grid(array) for array in arrays]
    if len({(len(rows), len(rows[0])) for rows in grids}) != 1:
        raise ExcelError(INVALID_VALUE, "the arrays differ in size")
    products = []
    for position_items in zip(*[[item for row in rows for item in row] for rows in grids]):
        error = first_error(list(position_items))
        if error is not None:
            raise error
        products.append(math.prod(item.value if item.kind == NUMBER else 0.0 for item in position_items))
    return math.fsum(products)
