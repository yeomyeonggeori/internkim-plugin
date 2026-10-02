from __future__ import annotations

from openpyxl.formula.tokenizer import Token, Tokenizer, TokenizerError

from sheet.formulas.functions import with_anchor_arrays


def formula_problem(formula: str) -> str | None:
    try:
        tokens = [token for token in Tokenizer(with_anchor_arrays(formula)).items if token.type != Token.WSPACE]
    except TokenizerError as error:
        return tokenizer_problem(str(error))
    except IndexError:
        return "has a ) that closes nothing"
    return operator_problem(tokens) or nesting_problem(tokens)


def tokenizer_problem(message: str) -> str:
    if message.startswith("Reached end of formula while parsing"):
        return "opens a quote and never closes it"
    if message.startswith("Mismatched"):
        return "closes a ( with } or a { with )"
    return message.split(" in ", 1)[0].lower()


def nesting_problem(tokens: list[Token]) -> str | None:
    open_tokens = []
    for token in tokens:
        if token.subtype == Token.OPEN:
            open_tokens.append(token)
        elif token.subtype == Token.CLOSE:
            if not open_tokens:
                return "has a ) that closes nothing"
            open_tokens.pop()
    if not open_tokens:
        return None
    opening = open_tokens[0].value
    closing = "}" if opening == "{" else ")"
    return f"leaves {opening} open; it needs {len(open_tokens)} more {closing}"


def operator_problem(tokens: list[Token]) -> str | None:
    previous = None
    for token in tokens:
        if token.type == Token.OP_IN and not ends_operand(previous):
            return f"has nothing before the operator {token.value}"
        if is_infix(previous) and not starts_operand(token):
            return f"has nothing after the operator {previous.value}"
        previous = token
    if is_infix(previous) or previous is not None and previous.type == Token.OP_PRE:
        return f"ends with the operator {previous.value}"
    return None


def is_infix(token: Token | None) -> bool:
    return token is not None and token.type == Token.OP_IN


def ends_operand(token: Token | None) -> bool:
    if token is None:
        return False
    return token.type in (Token.OPERAND, Token.OP_POST) or token.subtype == Token.CLOSE


def starts_operand(token: Token) -> bool:
    return token.type in (Token.OPERAND, Token.OP_PRE) or token.subtype == Token.OPEN
