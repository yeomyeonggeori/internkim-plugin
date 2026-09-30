from __future__ import annotations

import functools
import math
import re
from typing import Callable

from xlcalculator.xlfunctions import func_xltypes, xlerrors


BLANK = "blank"
NUMBER = "number"
TEXT = "text"
LOGICAL = "logical"
ERROR = "error"
TYPE_RANK = {NUMBER: 0, TEXT: 1, LOGICAL: 2}
CRITERIA_PATTERN = re.compile(r"^(>=|<=|<>|>|<|=)?(.*)$", re.DOTALL)


class Item:
    __slots__ = ("kind", "value")

    def __init__(self, kind: str, value):
        self.kind = kind
        self.value = value


def classify(raw) -> Item:
    if isinstance(raw, xlerrors.ExcelError):
        return Item(ERROR, raw)
    if isinstance(raw, func_xltypes.Blank) or raw is None:
        return Item(BLANK, None)
    if isinstance(raw, func_xltypes.DateTime):
        return Item(NUMBER, float(raw))
    if isinstance(raw, func_xltypes.ExcelType):
        return classify(raw.value)
    if isinstance(raw, bool):
        return Item(LOGICAL, raw)
    if isinstance(raw, (int, float)) or hasattr(raw, "item") and isinstance(raw.item(), (int, float)):
        return Item(NUMBER, float(raw))
    if isinstance(raw, str):
        return Item(TEXT, raw)
    raise NotImplementedError(f"cannot read a {type(raw).__name__} value")


def grid(argument) -> list[list[Item]]:
    rows = func_xltypes.Array.cast(argument).values.tolist()
    return [[classify(raw) for raw in row] for row in rows]


def is_range(argument) -> bool:
    return isinstance(argument, func_xltypes.Array)


def require_scalar(argument):
    if is_range(argument):
        raise NotImplementedError("array arithmetic is not evaluated")
    return argument


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
        raise xlerrors.ValueExcelError(f"{text!r} is not a number") from error


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
        raise xlerrors.ValueExcelError(f"{item.value!r} is not TRUE or FALSE")
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


def excel_function(function: Callable) -> Callable:
    @functools.wraps(function)
    def wrapper(*arguments):
        try:
            return func_xltypes.ExcelType.cast_from_native(function(*arguments))
        except xlerrors.ExcelError as error:
            return error
    return wrapper


def arithmetic(operation: Callable[[float, float], float]) -> Callable:
    def operator(left, right):
        left_item, right_item = classify(require_scalar(left)), classify(require_scalar(right))
        error = first_error([left_item, right_item])
        if error is not None:
            return error
        try:
            return operation(to_number(left_item), to_number(right_item))
        except xlerrors.ExcelError as error:
            return error
        except (OverflowError, ZeroDivisionError):
            return xlerrors.NumExcelError("the result is out of range")
    return operator


def divide(left: float, right: float) -> float:
    if right == 0:
        raise xlerrors.DivZeroExcelError()
    return left / right


def power(base: float, exponent: float) -> float:
    if base == 0 and exponent == 0:
        raise xlerrors.NumExcelError("0 to the power 0")
    result = base ** exponent
    if isinstance(result, complex):
        raise xlerrors.NumExcelError("a negative base with a fractional exponent")
    return result


def negate(value):
    item = classify(require_scalar(value))
    if item.kind == ERROR:
        return item.value
    try:
        return -to_number(item)
    except xlerrors.ExcelError as error:
        return error


def percent(value):
    item = classify(require_scalar(value))
    if item.kind == ERROR:
        return item.value
    try:
        return to_number(item) / 100
    except xlerrors.ExcelError as error:
        return error


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
        left_item, right_item = classify(require_scalar(left)), classify(require_scalar(right))
        error = first_error([left_item, right_item])
        return error if error is not None else accepts(order(left_item, right_item))
    return operator


def concatenate_operator(left, right):
    left_item, right_item = classify(require_scalar(left)), classify(require_scalar(right))
    error = first_error([left_item, right_item])
    return error if error is not None else to_text(left_item) + to_text(right_item)


def concatenate_items(arguments) -> object:
    items = [item for argument in arguments for row in grid(argument) for item in row]
    error = first_error(items)
    return error if error is not None else "".join(to_text(item) for item in items)


def numbers_in(arguments) -> list[float]:
    numbers = []
    for argument in arguments:
        items = [item for row in grid(argument) for item in row]
        error = first_error(items)
        if error is not None:
            raise error
        counts_logicals = not is_range(argument)
        numbers.extend(float(item.value) for item in items if item.kind == NUMBER or (item.kind == LOGICAL and counts_logicals))
    return numbers


def sum_numbers(*arguments):
    return math.fsum(numbers_in(arguments))


def average_numbers(*arguments):
    numbers = numbers_in(arguments)
    if not numbers:
        raise xlerrors.DivZeroExcelError()
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


def classify_scalar(criteria):
    return criteria.values.tolist()[0][0] if is_range(criteria) else criteria


def intersect(position_lists: list[list[tuple[int, int]]]) -> list[tuple[int, int]]:
    common = set(position_lists[0])
    for positions in position_lists[1:]:
        common &= set(positions)
    return sorted(common)


def criteria_positions(pairs) -> list[tuple[int, int]]:
    if len(pairs) % 2 != 0 or not pairs:
        raise xlerrors.ValueExcelError("criteria come as range and criterion pairs")
    shapes = {shape_of(range_argument) for range_argument in pairs[0::2]}
    if len(shapes) != 1:
        raise xlerrors.ValueExcelError("criteria ranges differ in size")
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
        raise xlerrors.DivZeroExcelError()
    return math.fsum(numbers) / len(numbers)


def averageif(range_argument, criteria, average_range=None):
    return average_items(summed_items(average_range if average_range is not None else range_argument, [range_argument, criteria]))


def averageifs(average_range, *criteria_pairs):
    return average_items(summed_items(average_range, list(criteria_pairs)))


def sumproduct(*arrays):
    grids = [grid(array) for array in arrays]
    if len({(len(rows), len(rows[0])) for rows in grids}) != 1:
        raise xlerrors.ValueExcelError("the arrays differ in size")
    products = []
    for position_items in zip(*[[item for row in rows for item in row] for rows in grids]):
        error = first_error(list(position_items))
        if error is not None:
            raise error
        products.append(math.prod(item.value if item.kind == NUMBER else 0.0 for item in position_items))
    return math.fsum(products)
