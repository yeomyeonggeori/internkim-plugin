from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
import re
from typing import Callable

from core.office_result import INVALID_VALUE, OfficeFailure


TOKEN = re.compile(r"\s*(?:(?P<number>\d+(?:\.\d+)?)|(?P<quoted>`[^`]+`)|(?P<name>[^\W\d]\w*(?:\.[^\W\d]\w*)*)|(?P<symbol>[-+*/(),]))")
ROW_FUNCTIONS = ("floor", "round", "if", "words", "money", "addDays")
LIST_FUNCTIONS = ("sum", "count")
VIEW_FUNCTIONS = ("change", "percentChange", "share")
FUNCTIONS = ROW_FUNCTIONS + LIST_FUNCTIONS + VIEW_FUNCTIONS
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Number:
    value: Decimal


@dataclass(frozen=True)
class Path:
    name: str


@dataclass(frozen=True)
class Call:
    function: str
    arguments: tuple


@dataclass(frozen=True)
class Binary:
    operator: str
    left: object
    right: object


@dataclass(frozen=True)
class Negate:
    operand: object


def tokens(text: str, location: str) -> list[tuple[str, str]]:
    found, position = [], 0
    while position < len(text.rstrip()):
        match = TOKEN.match(text, position)
        if match is None:
            raise OfficeFailure(INVALID_VALUE.issue(f"{location}: cannot read {text[position:]!r} in {text!r}", location))
        kind = match.lastgroup
        text_found = match.group(kind)
        found.append(("name", text_found[1:-1]) if kind == "quoted" else (kind, text_found))
        position = match.end()
    return found


class Parser:
    def __init__(self, text: str, location: str):
        self.text = text
        self.location = location
        self.tokens = tokens(text, location)
        self.position = 0

    def fail(self, message: str):
        raise OfficeFailure(INVALID_VALUE.issue(f"{self.location}: {message} in {self.text!r}", self.location))

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self, symbol: str | None = None) -> tuple[str, str]:
        token = self.peek()
        if token is None or symbol is not None and token[1] != symbol:
            self.fail(f"expected {symbol or 'more'}")
        self.position += 1
        return token

    def parse(self):
        expression = self.sum()
        if self.peek() is not None:
            self.fail(f"unexpected {self.peek()[1]!r}")
        return expression

    def sum(self):
        expression = self.product()
        while self.peek() and self.peek()[1] in "+-":
            operator = self.take()[1]
            expression = Binary(operator, expression, self.product())
        return expression

    def product(self):
        expression = self.factor()
        while self.peek() and self.peek()[1] in "*/":
            operator = self.take()[1]
            expression = Binary(operator, expression, self.factor())
        return expression

    def factor(self):
        token = self.take()
        if token[1] == "-":
            return Negate(self.factor())
        if token[1] == "(":
            expression = self.sum()
            self.take(")")
            return expression
        if token[0] == "number":
            return Number(Decimal(token[1]))
        if token[0] != "name":
            self.fail(f"unexpected {token[1]!r}")
        if self.peek() and self.peek()[1] == "(":
            return self.call(token[1])
        return Path(token[1])

    def call(self, function: str):
        if function not in FUNCTIONS:
            self.fail(f"{function!r} is not one of {', '.join(FUNCTIONS)}")
        self.take("(")
        arguments = [self.sum()]
        while self.peek() and self.peek()[1] == ",":
            self.take(",")
            arguments.append(self.sum())
        self.take(")")
        return Call(function, tuple(arguments))


def parse_expression(text: str, location: str):
    return Parser(text, location).parse()


def referenced_paths(expression) -> list[str]:
    if isinstance(expression, Path):
        return [expression.name]
    if isinstance(expression, Binary):
        return referenced_paths(expression.left) + referenced_paths(expression.right)
    if isinstance(expression, Negate):
        return referenced_paths(expression.operand)
    if isinstance(expression, Call):
        return [path for argument in expression.arguments for path in referenced_paths(argument)]
    return []


@dataclass(frozen=True)
class Scope:
    value_of: Callable[[str], object]
    list_of: Callable[[str], list | None]
    rounded: Callable[[Decimal], Decimal]
    words: Callable[[Decimal], str]


def evaluate(expression, scope: Scope):
    if isinstance(expression, Number):
        return expression.value
    if isinstance(expression, Path):
        return as_number_or_value(scope.value_of(expression.name))
    if isinstance(expression, Negate):
        operand = evaluate(expression.operand, scope)
        return None if operand is None else -operand
    if isinstance(expression, Binary):
        return arithmetic(expression.operator, evaluate(expression.left, scope), evaluate(expression.right, scope))
    return call(expression, scope)


def as_number_or_value(value: object):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str) and ISO_DATE.fullmatch(value):
        return date.fromisoformat(value)
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    return value


def arithmetic(operator: str, left, right):
    if left is None or right is None:
        return None
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    return None if right == 0 else left / right


def call(expression: Call, scope: Scope):
    function, arguments = expression.function, expression.arguments
    if function in LIST_FUNCTIONS:
        values = scope.list_of(arguments[0].name) if isinstance(arguments[0], Path) else None
        if values is None:
            return None
        if function == "count":
            return Decimal(len(values))
        numbers = [as_number_or_value(value) for value in values]
        return None if any(number is None for number in numbers) else sum(numbers, Decimal(0))
    if function == "if":
        condition = evaluate(arguments[0], scope)
        return evaluate(arguments[1] if condition else arguments[2], scope)
    value = evaluate(arguments[0], scope)
    if value is None:
        return None
    if function == "floor":
        return value.quantize(Decimal(1), rounding=ROUND_DOWN)
    if function == "round":
        digits = int(evaluate(arguments[1], scope)) if len(arguments) > 1 else 0
        return value.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    if function == "money":
        return scope.rounded(value)
    if function == "words":
        return scope.words(value)
    if function == "addDays":
        days = evaluate(arguments[1], scope)
        return None if days is None else value + timedelta(days=int(days))
    raise OfficeFailure(INVALID_VALUE.issue(f"{function}() belongs in a workbook view, where it compares cells", function))
