from __future__ import annotations

import inspect

from xlcalculator import ast_nodes
from xlcalculator.xlfunctions import func_xltypes, xl, xlerrors

import sheet_semantics as semantics
from sheet_semantics import ERROR, TEXT, Item, classify, excel_function, require_scalar


REFERENCE_ERROR_FUNCTION = "INTERNKIM_REFERENCE_ERROR"
NAME_ERROR_FUNCTION = "INTERNKIM_NAME_ERROR"
UNCOMPUTABLE_FUNCTION = "INTERNKIM_UNCOMPUTABLE"

NATIVE_FUNCTIONS = frozenset((
    "ABS", "AND", "CEILING", "CHOOSE", "DATE", "DATEDIF", "DAY", "EDATE", "EOMONTH", "EVEN", "EXACT", "EXP", "FACT",
    "FALSE", "FIND", "FLOOR", "INT", "ISBLANK", "ISERR", "ISERROR", "ISNA", "ISNUMBER", "ISTEXT", "LEFT", "LEN",
    "LN", "LOG", "LOG10", "LOWER", "MID", "MOD", "MONTH", "NA", "NOT", "NOW", "NPV", "OR", "PI", "PMT", "REPLACE",
    "RIGHT", "ROUND", "ROUNDDOWN", "ROUNDUP", "SIGN", "SQRT", "TODAY", "TRUE", "TRUNC", "UPPER", "WEEKDAY", "YEAR",
))


def register(name: str, function) -> None:
    xl.FUNCTIONS.register(function, name)


def lazy_parameter(name: str, default=inspect.Parameter.empty) -> inspect.Parameter:
    return inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default, annotation=func_xltypes.XlExpr)


@excel_function
def IF(logical_test, value_if_true, value_if_false=None):
    condition = semantics.to_logical(classify(require_scalar(logical_test())))
    chosen = value_if_true if condition else value_if_false
    return False if chosen is None else chosen()


IF.__signature__ = inspect.Signature([lazy_parameter("logical_test"), lazy_parameter("value_if_true"), lazy_parameter("value_if_false", default=None)])


@excel_function
def IFERROR(value, value_if_error):
    return value_if_error if classify(value).kind == ERROR else value


@excel_function
def IFNA(value, value_if_na):
    return value_if_na if isinstance(value, xlerrors.NaExcelError) else value


def vector(argument) -> list:
    rows = func_xltypes.Array.cast(argument).values.tolist()
    if len(rows) != 1 and len(rows[0]) != 1:
        raise xlerrors.NaExcelError("the lookup range is not one row or one column")
    return [value for row in rows for value in row]


def matching_index(lookup_value, raw_values: list, match_type: float):
    target = classify(require_scalar(lookup_value))
    if target.kind == ERROR:
        raise target.value
    items = [classify(raw) for raw in raw_values]
    if match_type == 0:
        return exact_index(target, items)
    if match_type != 1:
        raise NotImplementedError("only exact and ascending matches are evaluated")
    return ascending_index(target, items)


def exact_index(target: Item, items: list):
    if target.kind == TEXT:
        matches = semantics.text_test("=", target.value)
    else:
        matches = lambda item: item.kind == target.kind and semantics.order(item, target) == 0
    return next((index for index, item in enumerate(items) if matches(item)), None)


def ascending_index(target: Item, items: list):
    comparable = [item for item in items if item.kind == target.kind]
    ordered = [semantics.order(left, right) <= 0 for left, right in zip(comparable, comparable[1:])]
    if not all(ordered):
        raise NotImplementedError("an unsorted approximate match is not evaluated")
    candidates = [index for index, item in enumerate(items) if item.kind == target.kind and semantics.order(item, target) <= 0]
    return candidates[-1] if candidates else None


@excel_function
def MATCH(lookup_value, lookup_array, match_type=1):
    index = matching_index(lookup_value, vector(lookup_array), float(semantics.to_number(classify(match_type))))
    if index is None:
        raise xlerrors.NaExcelError("no match")
    return index + 1


@excel_function
def INDEX(array, row_number, column_number=None):
    rows = func_xltypes.Array.cast(array).values.tolist()
    row_index, column_index = index_position(rows, row_number, column_number)
    if not (1 <= row_index <= len(rows) and 1 <= column_index <= len(rows[0])):
        raise xlerrors.RefExcelError("index outside the array")
    return rows[row_index - 1][column_index - 1]


def index_position(rows: list, row_number, column_number) -> tuple[int, int]:
    row_index = int(semantics.to_number(classify(require_scalar(row_number))))
    if column_number is not None:
        return row_index, int(semantics.to_number(classify(require_scalar(column_number))))
    if len(rows) == 1:
        return 1, row_index
    if len(rows[0]) == 1:
        return row_index, 1
    raise NotImplementedError("a whole row or column is not evaluated")


@excel_function
def VLOOKUP(lookup_value, table_array, column_number, range_lookup=True):
    rows = func_xltypes.Array.cast(table_array).values.tolist()
    column_index = int(semantics.to_number(classify(require_scalar(column_number))))
    if not 1 <= column_index <= len(rows[0]):
        raise xlerrors.RefExcelError("column number outside the table")
    is_approximate = semantics.to_logical(classify(require_scalar(range_lookup)))
    index = matching_index(lookup_value, [row[0] for row in rows], 1 if is_approximate else 0)
    if index is None:
        raise xlerrors.NaExcelError("value not found in the first column")
    return rows[index][column_index - 1]


@excel_function
def TRIM(text):
    return " ".join(word for word in semantics.to_text(classify(require_scalar(text))).split(" ") if word)


@excel_function
def CONCAT(*arguments):
    return semantics.concatenate_items(arguments)


def reference_error():
    return xlerrors.RefExcelError("the formula refers to a sheet or cell that does not exist")


def name_error():
    return xlerrors.NameExcelError("the formula names a function Excel does not have")


def uncomputable():
    raise NotImplementedError("the evaluator cannot compute this formula")


def binary_operation(operation):
    return excel_function(semantics.arithmetic(operation))


OPERATORS = {
    "+": binary_operation(lambda left, right: left + right),
    "-": binary_operation(lambda left, right: left - right),
    "*": binary_operation(lambda left, right: left * right),
    "/": binary_operation(semantics.divide),
    "^": binary_operation(semantics.power),
    "&": excel_function(semantics.concatenate_operator),
    "=": excel_function(semantics.comparison(lambda order: order == 0)),
    "<>": excel_function(semantics.comparison(lambda order: order != 0)),
    ">": excel_function(semantics.comparison(lambda order: order > 0)),
    "<": excel_function(semantics.comparison(lambda order: order < 0)),
    ">=": excel_function(semantics.comparison(lambda order: order >= 0)),
    "<=": excel_function(semantics.comparison(lambda order: order <= 0)),
}

AGGREGATES = {
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
}


def install() -> None:
    ast_nodes.INFIX_OP_TO_FUNC.update(OPERATORS)
    ast_nodes.PREFIX_OP_TO_FUNC["-"] = excel_function(semantics.negate)
    ast_nodes.POSTFIX_OP_TO_FUNC["%"] = excel_function(semantics.percent)
    for name, function in AGGREGATES.items():
        register(name, excel_function(function))
    register("IF", IF)
    register("POWER", OPERATORS["^"])
    register("CONCATENATE", CONCAT)
    for function in (CONCAT, IFERROR, IFNA, MATCH, INDEX, VLOOKUP, TRIM):
        register(function.__name__, function)
    register(REFERENCE_ERROR_FUNCTION, reference_error)
    register(NAME_ERROR_FUNCTION, name_error)
    register(UNCOMPUTABLE_FUNCTION, uncomputable)


install()

SUPPORTED_FUNCTIONS = NATIVE_FUNCTIONS | frozenset(AGGREGATES) | frozenset(("IF", "POWER", "CONCAT", "CONCATENATE", "IFERROR", "IFNA", "MATCH", "INDEX", "VLOOKUP", "TRIM"))
