from __future__ import annotations

import re

from openpyxl.formula.tokenizer import Token
from openpyxl.utils.formulas import FORMULAE

from formula_tree import Call, calls_in, parse_formula, render, tokens_in


# [MS-XLSX] 2.2.2 Formulas, future-function-list, plus the functions Excel added after it under the same prefix
FUTURE_FUNCTIONS = frozenset((
    'ACOT', 'ACOTH', 'AGGREGATE', 'ARABIC', 'ARRAYTOTEXT', 'BASE', 'BETA.DIST', 'BETA.INV', 'BINOM.DIST',
    'BINOM.DIST.RANGE', 'BINOM.INV', 'BITAND', 'BITLSHIFT', 'BITOR', 'BITRSHIFT', 'BITXOR', 'BYCOL', 'BYROW',
    'CEILING.MATH', 'CEILING.PRECISE', 'CHISQ.DIST', 'CHISQ.DIST.RT', 'CHISQ.INV', 'CHISQ.INV.RT', 'CHISQ.TEST',
    'CHOOSECOLS', 'CHOOSEROWS', 'COMBINA', 'CONCAT', 'CONFIDENCE.NORM', 'CONFIDENCE.T', 'COPILOT', 'COT', 'COTH',
    'COVARIANCE.P', 'COVARIANCE.S', 'CSC', 'CSCH', 'DAYS', 'DECIMAL', 'DROP', 'ECMA.CEILING', 'ERF.PRECISE',
    'ERFC.PRECISE', 'EXPAND', 'EXPON.DIST', 'F.DIST', 'F.DIST.RT', 'F.INV', 'F.INV.RT', 'F.TEST', 'FIELDVALUE',
    'FILTERXML', 'FLOOR.MATH', 'FLOOR.PRECISE', 'FORECAST.ETS', 'FORECAST.ETS.CONFINT', 'FORECAST.ETS.SEASONALITY',
    'FORECAST.ETS.STAT', 'FORECAST.LINEAR', 'FORMULATEXT', 'GAMMA', 'GAMMA.DIST', 'GAMMA.INV', 'GAMMALN.PRECISE',
    'GAUSS', 'GROUPBY', 'HSTACK', 'HYPGEOM.DIST', 'IFNA', 'IFS', 'IMAGE', 'IMCOSH', 'IMCOT', 'IMCSC', 'IMCSCH',
    'IMSEC', 'IMSECH', 'IMSINH', 'IMTAN', 'ISFORMULA', 'ISO.CEILING', 'ISOMITTED', 'ISOWEEKNUM', 'LAMBDA', 'LET',
    'LOGNORM.DIST', 'LOGNORM.INV', 'LONGTEXT', 'MAKEARRAY', 'MAP', 'MAXIFS', 'MINIFS', 'MODE.MULT', 'MODE.SNGL',
    'MUNIT', 'NEGBINOM.DIST', 'NETWORKDAYS.INTL', 'NORM.DIST', 'NORM.INV', 'NORM.S.DIST', 'NORM.S.INV',
    'NUMBERVALUE', 'PDURATION', 'PERCENTILE.EXC', 'PERCENTILE.INC', 'PERCENTOF', 'PERCENTRANK.EXC',
    'PERCENTRANK.INC', 'PERMUTATIONA', 'PHI', 'PIVOTBY', 'POISSON.DIST', 'PQSOURCE', 'PYTHON_STR', 'PYTHON_TYPE',
    'PYTHON_TYPENAME', 'QUARTILE.EXC', 'QUARTILE.INC', 'QUERYSTRING', 'RANDARRAY', 'RANK.AVG', 'RANK.EQ', 'REDUCE',
    'REGEXEXTRACT', 'REGEXREPLACE', 'REGEXTEST', 'RRI', 'SCAN', 'SEC', 'SECH', 'SEQUENCE', 'SHEET', 'SHEETS',
    'SKEW.P', 'SORTBY', 'STDEV.P', 'STDEV.S', 'STOCKHISTORY', 'SWITCH', 'T.DIST', 'T.DIST.2T', 'T.DIST.RT', 'T.INV',
    'T.INV.2T', 'T.TEST', 'TAKE', 'TEXTAFTER', 'TEXTBEFORE', 'TEXTJOIN', 'TEXTSPLIT', 'TOCOL', 'TOROW', 'TRIMRANGE',
    'UNICHAR', 'UNICODE', 'UNIQUE', 'VALUETOTEXT', 'VAR.P', 'VAR.S', 'VSTACK', 'WEBSERVICE', 'WEIBULL.DIST',
    'WORKDAY.INTL', 'WRAPCOLS', 'WRAPROWS', 'XLOOKUP', 'XMATCH', 'XOR', 'Z.TEST',
))
# [MS-XLSX] 2.2.2 Formulas, worksheet-only-function-list
WORKSHEET_ONLY_FUNCTIONS = frozenset(("FILTER", "PY", "SORT"))
SPILL_REFERENCE_FUNCTION = "ANCHORARRAY"
IMPLICIT_INTERSECTION_FUNCTION = "SINGLE"
DYNAMIC_ARRAY_FUNCTIONS = frozenset((
    "BYCOL", "BYROW", "CHOOSECOLS", "CHOOSEROWS", "DROP", "EXPAND", "FILTER", "FREQUENCY", "GROUPBY", "HSTACK",
    "MAKEARRAY", "MAP", "MINVERSE", "MMULT", "MUNIT", "PIVOTBY", "RANDARRAY", "SCAN", "SEQUENCE", "SORT", "SORTBY",
    "TAKE", "TEXTSPLIT", "TOCOL", "TOROW", "TRANSPOSE", "UNIQUE", "VSTACK", "WRAPCOLS", "WRAPROWS",
    SPILL_REFERENCE_FUNCTION,
))
PARAMETER_FUNCTIONS = frozenset(("LET", "LAMBDA"))
EXCEL_FUNCTIONS = frozenset(FORMULAE) | FUTURE_FUNCTIONS | WORKSHEET_ONLY_FUNCTIONS | {SPILL_REFERENCE_FUNCTION, IMPLICIT_INTERSECTION_FUNCTION}
PARAMETER_PREFIX = "_xlpm."
SPILL_REFERENCE = re.compile(r"((?:'(?:[^']|'')+'|[A-Za-z0-9_.\u0080-￿]+)!)?\$?[A-Za-z]{1,3}\$?[0-9]+$")


def stored_function_name(function: str) -> str:
    if function in WORKSHEET_ONLY_FUNCTIONS:
        return f"_xlfn._xlws.{function}"
    if function in FUTURE_FUNCTIONS or function in (SPILL_REFERENCE_FUNCTION, IMPLICIT_INTERSECTION_FUNCTION):
        return f"_xlfn.{function}"
    return function


def is_dynamic_array_formula(formula: str) -> bool:
    nodes = parse_formula(formula)
    return nodes is not None and any(call.function in DYNAMIC_ARRAY_FUNCTIONS for call in calls_in(nodes))


def stored_formula(formula: str) -> str:
    nodes = parse_formula(with_anchor_arrays(formula))
    if nodes is None:
        return formula
    for call in calls_in(nodes):
        if call.function in PARAMETER_FUNCTIONS:
            prefix_parameters(call)
    return "=" + render(nodes, stored_call)


def stored_call(call: Call) -> str | None:
    stored = stored_function_name(call.function)
    if stored == call.name:
        return None
    return f"{stored}(" + ",".join(render(argument, stored_call) for argument in call.arguments) + ")"


def prefix_parameters(call: Call) -> None:
    names = parameter_names(call)
    for token in tokens_in([call]):
        if token.type == Token.OPERAND and token.subtype == Token.RANGE and token.value.casefold() in names:
            token.value = PARAMETER_PREFIX + token.value


def parameter_names(call: Call) -> set[str]:
    positions = range(0, len(call.arguments) - 1, 2) if call.function == "LET" else range(len(call.arguments) - 1)
    names = set()
    for position in positions:
        tokens = [token for token in tokens_in(call.arguments[position]) if token.type != Token.WSPACE]
        if len(tokens) == 1 and tokens[0].subtype == Token.RANGE and not tokens[0].value.lower().startswith(PARAMETER_PREFIX):
            names.add(tokens[0].value.casefold())
    return names


def with_anchor_arrays(formula: str) -> str:
    if "#" not in formula:
        return formula
    output = []
    quote = None
    bracket_depth = 0
    for character in formula:
        if quote:
            quote = None if character == quote else quote
        elif character in "\"'":
            quote = character
        elif character == "[":
            bracket_depth += 1
        elif character == "]":
            bracket_depth -= 1
        elif character == "#" and bracket_depth == 0 and wrap_spill_reference(output):
            continue
        output.append(character)
    return "".join(output)


def wrap_spill_reference(output: list[str]) -> bool:
    text = "".join(output)
    match = SPILL_REFERENCE.search(text)
    if match is None or match.start() > 0 and text[match.start() - 1] not in "=(,+-*/^&<>: ":
        return False
    del output[match.start():]
    output.extend(f"_xlfn.{SPILL_REFERENCE_FUNCTION}({match.group(0)})")
    return True


def written_value(value: object) -> object:
    if isinstance(value, str) and value.startswith("=") and len(value) > 1:
        return stored_formula(value)
    return value
