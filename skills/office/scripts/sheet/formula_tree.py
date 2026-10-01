from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator, Union

from openpyxl.formula.tokenizer import Token, Tokenizer, TokenizerError


FUNCTION_PREFIXES = ("_XLFN.", "_XLWS.")


@dataclass
class Call:
    name: str
    arguments: list[list["Node"]] = field(default_factory=list)

    @property
    def function(self) -> str:
        return function_name(self.name)


@dataclass
class Group:
    opening: str
    nodes: list["Node"]
    closing: str


Node = Union[Call, Group, Token]
Transform = Callable[[Call], "str | None"]


def function_name(written: str) -> str:
    name = written.upper()
    while name.startswith(FUNCTION_PREFIXES):
        name = name.split(".", 1)[1]
    return name


def parse_formula(formula: str) -> list[Node] | None:
    if not formula.startswith("="):
        return None
    try:
        tokens = Tokenizer(formula).items
    except TokenizerError:
        return None
    nodes, _ = parse_nodes(tokens, 0, inside_call=False)
    return nodes


def parse_nodes(tokens: list[Token], index: int, inside_call: bool) -> tuple[list[Node], int]:
    nodes = []
    while index < len(tokens):
        token = tokens[index]
        if token.subtype == Token.CLOSE or inside_call and token.type == Token.SEP and token.subtype == Token.ARG:
            return nodes, index
        if token.type == Token.FUNC and token.subtype == Token.OPEN:
            call, index = parse_call(tokens, index)
            nodes.append(call)
            continue
        if token.subtype == Token.OPEN:
            inner, index = parse_nodes(tokens, index + 1, inside_call=False)
            closing = tokens[index].value if index < len(tokens) else ""
            nodes.append(Group(token.value, inner, closing))
            index += 1
            continue
        nodes.append(token)
        index += 1
    return nodes, index


def parse_call(tokens: list[Token], index: int) -> tuple[Call, int]:
    call = Call(tokens[index].value[:-1])
    index += 1
    while index < len(tokens):
        argument, index = parse_nodes(tokens, index, inside_call=True)
        call.arguments.append(argument)
        if index >= len(tokens) or tokens[index].subtype == Token.CLOSE:
            break
        index += 1
    if call.arguments == [[]]:
        call.arguments = []
    return call, index + 1


def render(nodes: list[Node], transform: Transform | None = None) -> str:
    return "".join(render_node(node, transform) for node in nodes)


def render_node(node: Node, transform: Transform | None) -> str:
    if isinstance(node, Call):
        replaced = transform(node) if transform else None
        if replaced is not None:
            return replaced
        return f"{node.name}(" + ",".join(render(argument, transform) for argument in node.arguments) + ")"
    if isinstance(node, Group):
        return node.opening + render(node.nodes, transform) + node.closing
    return node.value


def rewrite_calls(formula: str, transform: Transform) -> str:
    nodes = parse_formula(formula)
    if nodes is None:
        return formula
    return "=" + render(nodes, transform)


def calls_in(nodes: list[Node]) -> Iterator[Call]:
    for node in nodes:
        if isinstance(node, Call):
            yield node
            for argument in node.arguments:
                yield from calls_in(argument)
        elif isinstance(node, Group):
            yield from calls_in(node.nodes)


def tokens_in(nodes: list[Node]) -> Iterator[Token]:
    for node in nodes:
        if isinstance(node, Call):
            for argument in node.arguments:
                yield from tokens_in(argument)
        elif isinstance(node, Group):
            yield from tokens_in(node.nodes)
        else:
            yield node


def meaningful(nodes: list[Node]) -> list[Node]:
    return [node for node in nodes if not (isinstance(node, Token) and node.type == Token.WSPACE)]


def text_literal(nodes: list[Node]) -> str | None:
    significant = meaningful(nodes)
    if len(significant) != 1 or not isinstance(significant[0], Token):
        return None
    token = significant[0]
    if token.type != Token.OPERAND or token.subtype != Token.TEXT:
        return None
    return token.value[1:-1].replace('""', '"')
