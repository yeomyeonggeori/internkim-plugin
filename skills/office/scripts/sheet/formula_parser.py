from __future__ import annotations

from dataclasses import dataclass

from openpyxl.formula.tokenizer import Token, Tokenizer, TokenizerError

from sheet_semantics import BLANK, ERROR, LOGICAL, NUMBER, TEXT, ExcelError, Item


INFIX_PRECEDENCE = {
    "=": 1, "<>": 1, "<": 1, ">": 1, "<=": 1, ">=": 1,
    "&": 2,
    "+": 3, "-": 3,
    "*": 4, "/": 4,
    "^": 5,
}
EMPTY_ARGUMENT = Item(BLANK, None)


@dataclass(frozen=True)
class Literal:
    item: Item


@dataclass(frozen=True)
class Reference:
    text: str


@dataclass(frozen=True)
class Call:
    name: str
    arguments: tuple


@dataclass(frozen=True)
class Prefix:
    operator: str
    operand: object


@dataclass(frozen=True)
class Postfix:
    operator: str
    operand: object


@dataclass(frozen=True)
class Infix:
    operator: str
    left: object
    right: object


def parse_formula(formula: str):
    try:
        tokens = [token for token in Tokenizer(formula).items if token.type != Token.WSPACE]
    except TokenizerError as error:
        raise NotImplementedError(f"the formula cannot be read: {error}") from error
    parser = Parser(tokens)
    tree = parser.expression(0)
    if parser.peek() is not None:
        raise NotImplementedError(f"unexpected {parser.peek().value!r} in the formula")
    return tree


class Parser:
    def __init__(self, tokens: list):
        self.tokens = tokens
        self.position = 0

    def peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def advance(self):
        token = self.peek()
        if token is None:
            raise NotImplementedError("the formula ends early")
        self.position += 1
        return token

    def expect(self, token_type: str, subtype: str) -> None:
        token = self.advance()
        if token.type != token_type or token.subtype != subtype:
            raise NotImplementedError(f"unexpected {token.value!r} in the formula")

    def expression(self, minimum_precedence: int):
        left = self.unary()
        while self.is_infix_at_least(minimum_precedence):
            operator = self.advance().value
            left = Infix(operator, left, self.expression(INFIX_PRECEDENCE[operator] + 1))
        return left

    def is_infix_at_least(self, minimum_precedence: int) -> bool:
        token = self.peek()
        if token is None or token.type != Token.OP_IN:
            return False
        if token.value not in INFIX_PRECEDENCE:
            raise NotImplementedError(f"the {token.value!r} reference operator is not evaluated")
        return INFIX_PRECEDENCE[token.value] >= minimum_precedence

    def unary(self):
        token = self.peek()
        if token is not None and token.type == Token.OP_PRE:
            return Prefix(self.advance().value, self.unary())
        operand = self.primary()
        while self.peek() is not None and self.peek().type == Token.OP_POST:
            operand = Postfix(self.advance().value, operand)
        return operand

    def primary(self):
        token = self.advance()
        if token.type == Token.OPERAND:
            return operand(token)
        if token.type == Token.FUNC and token.subtype == Token.OPEN:
            return Call(token.value[:-1].upper(), self.arguments())
        if token.type == Token.PAREN and token.subtype == Token.OPEN:
            inner = self.expression(0)
            self.expect(Token.PAREN, Token.CLOSE)
            return inner
        raise NotImplementedError(f"{token.value!r} is not evaluated")

    def arguments(self) -> tuple:
        if self.is_function_close():
            self.advance()
            return ()
        arguments = []
        while True:
            arguments.append(Literal(EMPTY_ARGUMENT) if self.is_argument_end() else self.expression(0))
            token = self.advance()
            if token.type == Token.FUNC and token.subtype == Token.CLOSE:
                return tuple(arguments)
            if token.type != Token.SEP or token.subtype != Token.ARG:
                raise NotImplementedError(f"unexpected {token.value!r} in a function's arguments")

    def is_function_close(self) -> bool:
        token = self.peek()
        return token is not None and token.type == Token.FUNC and token.subtype == Token.CLOSE

    def is_argument_end(self) -> bool:
        token = self.peek()
        return self.is_function_close() or (token is not None and token.type == Token.SEP and token.subtype == Token.ARG)


def operand(token) -> object:
    if token.subtype == Token.TEXT:
        return Literal(Item(TEXT, token.value[1:-1].replace('""', '"')))
    if token.subtype == Token.NUMBER:
        return Literal(Item(NUMBER, float(token.value)))
    if token.subtype == Token.LOGICAL:
        return Literal(Item(LOGICAL, token.value.upper() == "TRUE"))
    if token.subtype == Token.ERROR:
        return Literal(Item(ERROR, ExcelError(token.value.upper())))
    return Reference(token.value)
