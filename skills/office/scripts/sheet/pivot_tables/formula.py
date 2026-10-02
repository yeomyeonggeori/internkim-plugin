from __future__ import annotations

from dataclasses import dataclass

from core.office_result import INVALID_VALUE, OfficeFailure
from core.office_schema import closest_suggestion, did_you_mean


OPERATORS = "+-*/^()"
NUMBER_CHARACTERS = "0123456789."


@dataclass(frozen=True)
class PivotFormula:
    text: str
    tree: tuple
    fields: tuple[int, ...]


def formula_failure(message: str, location: str, suggestion: str | None = None) -> OfficeFailure:
    return OfficeFailure(INVALID_VALUE.issue(f"{location}: {message}", location, suggestion))


def quoted_name(text: str, start: int, location: str) -> tuple[str, int]:
    characters = []
    position = start + 1
    while position < len(text):
        if text[position] != "'":
            characters.append(text[position])
            position += 1
            continue
        if text[position:position + 2] == "''":
            characters.append("'")
            position += 2
            continue
        return "".join(characters), position + 1
    raise formula_failure(f"the name starting at character {start + 1} has no closing quote", location)


def bare_word(text: str, start: int) -> tuple[str, int]:
    position = start
    while position < len(text) and not text[position].isspace() and text[position] not in OPERATORS + "'":
        position += 1
    return text[start:position], position


def header_token(name: str, headers: list[str], location: str) -> tuple:
    if name in headers:
        return ("name", headers.index(name))
    raise formula_failure(
        f"{name!r} is not a header of the source{did_you_mean(name, headers)}; a name with spaces or symbols goes in single quotes, such as 'Unit Price'*qty",
        location,
        closest_suggestion(name, headers),
    )


def tokens_of(text: str, headers: list[str], location: str) -> list[tuple]:
    tokens = []
    position = 0
    while position < len(text):
        character = text[position]
        if character.isspace():
            position += 1
        elif character in OPERATORS:
            tokens.append(("operator", character))
            position += 1
        elif character == "'":
            name, position = quoted_name(text, position, location)
            tokens.append(header_token(name, headers, location))
        else:
            word, position = bare_word(text, position)
            tokens.append(number_token(word) or header_token(word, headers, location))
    return tokens


def number_token(word: str) -> tuple | None:
    if not word or any(character not in NUMBER_CHARACTERS for character in word) or word.count(".") > 1 or word == ".":
        return None
    return ("number", float(word))


class FormulaParser:
    def __init__(self, tokens: list[tuple], location: str):
        self.tokens = tokens
        self.position = 0
        self.location = location

    def peek(self) -> tuple | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take_operator(self, choices: str) -> str | None:
        token = self.peek()
        if token is not None and token[0] == "operator" and token[1] in choices:
            self.position += 1
            return token[1]
        return None

    def expression(self) -> tuple:
        tree = self.term()
        while operator := self.take_operator("+-"):
            tree = (operator, tree, self.term())
        return tree

    def term(self) -> tuple:
        tree = self.power()
        while operator := self.take_operator("*/"):
            tree = (operator, tree, self.power())
        return tree

    def power(self) -> tuple:
        base = self.unary()
        if self.take_operator("^"):
            return ("^", base, self.power())
        return base

    def unary(self) -> tuple:
        if self.take_operator("-"):
            return ("negate", self.unary())
        if self.take_operator("+"):
            return self.unary()
        return self.primary()

    def primary(self) -> tuple:
        token = self.peek()
        if token is None:
            raise formula_failure("the formula ends where a name, a number or ( belongs", self.location)
        if self.take_operator("("):
            tree = self.expression()
            if not self.take_operator(")"):
                raise formula_failure("a ( is never closed", self.location)
            return tree
        if token[0] == "operator":
            raise formula_failure(f"{token[1]!r} stands where a name, a number or ( belongs", self.location)
        self.position += 1
        return token


def parse_formula(text: str, headers: list[str], location: str) -> PivotFormula:
    tokens = tokens_of(text, headers, location)
    parser = FormulaParser(tokens, location)
    tree = parser.expression()
    if parser.peek() is not None:
        raise formula_failure(f"{parser.peek()[1]!r} follows a finished formula; join the parts with + - * or /", location)
    fields = tuple(dict.fromkeys(token[1] for token in tokens if token[0] == "name"))
    if not fields:
        raise formula_failure("a calculated value needs at least one header name", location)
    return PivotFormula(formula_text(tokens, headers), tree, fields)


def formula_text(tokens: list[tuple], headers: list[str]) -> str:
    parts = []
    for kind, value in tokens:
        if kind == "name":
            parts.append("'" + headers[value].replace("'", "''") + "'")
        elif kind == "number":
            parts.append(f"{value:g}")
        else:
            parts.append(value)
    return "".join(parts)


def evaluate(tree: tuple, totals: dict[int, float]) -> float | None:
    kind = tree[0]
    if kind == "number":
        return tree[1]
    if kind == "name":
        return totals.get(tree[1], 0)
    if kind == "negate":
        operand = evaluate(tree[1], totals)
        return None if operand is None else -operand
    left, right = evaluate(tree[1], totals), evaluate(tree[2], totals)
    if left is None or right is None:
        return None
    return arithmetic(kind, left, right)


def arithmetic(operator: str, left: float, right: float) -> float | None:
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
        return None if right == 0 else left / right
    try:
        return float(left ** right)
    except (OverflowError, ZeroDivisionError, TypeError):
        return None
