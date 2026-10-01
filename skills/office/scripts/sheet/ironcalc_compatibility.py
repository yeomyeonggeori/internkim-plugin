from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re

from excel_functions import EXCEL_FUNCTIONS, FUTURE_FUNCTIONS, WORKSHEET_ONLY_FUNCTIONS, stored_function_name
from formula_references import REFERENCE_ERROR, rewrite_formula
from formula_tree import Call, calls_in, parse_formula, render, text_literal


ROUNDING_FUNCTIONS = frozenset(("ROUND", "ROUNDUP", "ROUNDDOWN"))
# IronCalc 0.8.3 ROUND/ROUNDUP/ROUNDDOWN scale by 10^digits after their 15-digit cleanup, so ROUND(1.005,2) gives 1
# (base/src/functions/math_and_trigonometry/mathematical.rs fn_round); its own digits=0 path cleans the scaled value.
SCALED_ROUNDING = (
    "_xlfn.LET(_xlpm.internkimvalue,{value},_xlpm.internkimdigits,TRUNC({digits}),"
    "IF(_xlpm.internkimdigits>=0,"
    "{function}(_xlpm.internkimvalue*10^_xlpm.internkimdigits,0)/10^_xlpm.internkimdigits,"
    "{function}(_xlpm.internkimvalue/10^-_xlpm.internkimdigits,0)*10^-_xlpm.internkimdigits))"
)
SINGLE_CRITERIA_FUNCTIONS = frozenset(("COUNTIF", "SUMIF", "AVERAGEIF"))
FIRST_CRITERIA_RANGE = {"COUNTIF": 0, "SUMIF": 0, "AVERAGEIF": 0, "COUNTIFS": 0, "SUMIFS": 1, "AVERAGEIFS": 1, "MAXIFS": 1, "MINIFS": 1}
UNSUPPORTED_ERRORS = frozenset(("#NAME?", "#N/IMPL!"))
NAME_ERROR_FORMULA = "=INTERNKIMNAMEERROR()"
QUOTED = re.compile(r'"[^"]*"|\\.|\[[^\]]*\]')
DATE_TOKENS = re.compile(r"[yYmMdDhHsS]|AM/PM|A/P", re.IGNORECASE)
NUMBER_TEXT = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


@dataclass(frozen=True)
class CriteriaPair:
    range_text: str
    criteria_text: str
    criteria_literal: str | None


@dataclass(frozen=True)
class Preparation:
    formula: str
    is_computable: bool
    fixed_error: str | None
    criteria: tuple[CriteriaPair, ...]


@lru_cache(maxsize=1)
def unsupported_functions() -> frozenset:
    import ironcalc

    names = sorted(EXCEL_FUNCTIONS)
    model = ironcalc.create("probe", "en", "UTC")
    for row, name in enumerate(names, 1):
        model.set_user_input(0, row, 1, f"={stored_function_name(name)}()")
    model.evaluate()
    return frozenset(name for row, name in enumerate(names, 1) if model.get_cell_value(0, row, 1) in UNSUPPORTED_ERRORS)


def prepare(formula: str, allows_user_functions: bool) -> Preparation:
    nodes = parse_formula(without_sheet_on_reference_errors(formula))
    if nodes is None:
        return Preparation(formula, False, None, ())
    calls = list(calls_in(nodes))
    if any(is_unprefixed_future_call(call) for call in calls):
        return Preparation(NAME_ERROR_FORMULA, True, "#NAME?", ())
    if allows_user_functions and any(call.function not in EXCEL_FUNCTIONS for call in calls):
        return Preparation(formula, False, None, ())
    if any(call.function in unsupported_functions() for call in calls) or not all(map(is_text_computable, calls)):
        return Preparation(formula, False, None, ())
    criteria = tuple(pair for call in calls for pair in criteria_pairs(call))
    return Preparation("=" + render(nodes, evaluation_call), True, None, criteria)


def without_sheet_on_reference_errors(formula: str) -> str:
    # IronCalc 0.8.3 cannot parse Sheet!#REF!, the form Excel writes for a deleted reference into another sheet
    return rewrite_formula(formula, lambda reference: REFERENCE_ERROR if reference.endswith(REFERENCE_ERROR) else reference)


def is_unprefixed_future_call(call: Call) -> bool:
    if call.function not in FUTURE_FUNCTIONS and call.function not in WORKSHEET_ONLY_FUNCTIONS:
        return False
    return not call.name.upper().startswith("_XLFN.")


def evaluation_call(call: Call) -> str | None:
    if call.function in ROUNDING_FUNCTIONS and len(call.arguments) == 2:
        value, digits = (render(argument, evaluation_call) for argument in call.arguments)
        return scaled_rounding(call.function, value, digits)
    if call.function == "TEXT" and len(call.arguments) == 2:
        return rounded_text_call(call)
    return None


def scaled_rounding(function: str, value: str, digits: str) -> str:
    return SCALED_ROUNDING.format(function=function, value=value, digits=digits)


def rounded_text_call(call: Call) -> str | None:
    number_format = text_literal(call.arguments[1])
    decimals = text_format_decimals(number_format)
    if decimals is None:
        return None
    value = render(call.arguments[0], evaluation_call)
    format_argument = render(call.arguments[1], evaluation_call)
    if len(format_sections(number_format)) > 1:
        return f"{call.name}({scaled_rounding('ROUND', value, str(decimals))},{format_argument})"
    # IronCalc 0.8.3 TEXT drops the minus sign of -1 under a format without decimals
    # (base/src/formatter/format.rs is_negative), so a one-section format is applied to the magnitude
    rounded = scaled_rounding("ROUND", "_xlpm.internkimtext", str(decimals))
    return (
        f"_xlfn.LET(_xlpm.internkimtext,{value},IF(_xlpm.internkimtext<0,"
        f'"-"&{call.name}(-{rounded},{format_argument}),{call.name}({rounded},{format_argument})))'
    )


def is_text_computable(call: Call) -> bool:
    if call.function != "TEXT" or len(call.arguments) != 2:
        return True
    number_format = text_literal(call.arguments[1])
    return number_format is not None and not has_unsupported_format(number_format) and ironcalc_reads_format(number_format)


@lru_cache(maxsize=256)
def ironcalc_reads_format(number_format: str) -> bool:
    import ironcalc

    model = ironcalc.create("probe", "en", "UTC")
    escaped = number_format.replace('"', '""')
    samples = ("1234.5", "46085.75")
    for row, sample in enumerate(samples, 1):
        model.set_user_input(0, row, 1, f'=TEXT({sample},"{escaped}")')
    model.evaluate()
    return all(model.get_cell_type(0, row, 1) == ironcalc.CellType.Text for row in range(1, len(samples) + 1))


def format_sections(number_format: str) -> list[str]:
    return QUOTED.sub("", number_format).split(";")


def has_unsupported_format(number_format: str) -> bool:
    if re.search(r"\[[<>=]", number_format):
        return True
    sections = format_sections(number_format)
    if any("/" in section and "?" in section for section in sections):
        return True
    numeric = [section for section in sections if not DATE_TOKENS.search(section) and section.strip() not in ("", "@") and section.lower() != "general"]
    return len({section_decimals(section) for section in numeric}) > 1


def text_format_decimals(number_format: str | None) -> int | None:
    if number_format is None or has_unsupported_format(number_format):
        return None
    first = format_sections(number_format)[0]
    if DATE_TOKENS.search(first) or first.strip() in ("", "@") or first.lower() == "general" or re.search(r"[eE][+-]", first):
        return None
    return section_decimals(first)


def section_decimals(section: str) -> int:
    decimals = len(re.findall(r"[0#?]", section.split(".", 1)[1])) if "." in section else 0
    scaling = re.search(r"[0#?](,+)(?![0#?,])", section)
    return decimals + 2 * section.count("%") - (3 * len(scaling.group(1)) if scaling else 0)


def criteria_pairs(call: Call) -> list[CriteriaPair]:
    first = FIRST_CRITERIA_RANGE.get(call.function)
    if first is None or len(call.arguments) < first + 2:
        return []
    indexes = [first] if call.function in SINGLE_CRITERIA_FUNCTIONS else range(first, len(call.arguments) - 1, 2)
    return [criteria_pair(call.arguments[index], call.arguments[index + 1]) for index in indexes]


def criteria_pair(range_nodes: list, criteria_nodes: list) -> CriteriaPair:
    return CriteriaPair(render(range_nodes), render(criteria_nodes), text_literal(criteria_nodes))


def is_divergent_criteria(criteria: object) -> bool:
    # IronCalc 0.8.3 matches a "<>text" criterion without wildcards against text cells only; Excel also counts
    # numbers, logical values and blank cells as not equal
    if not isinstance(criteria, str) or not criteria.startswith("<>"):
        return False
    operand = criteria[2:]
    return bool(operand) and "*" not in operand and "?" not in operand and not NUMBER_TEXT.match(operand.strip())


def needs_criteria_probe(pair: CriteriaPair) -> bool:
    if pair.criteria_literal is not None:
        return is_divergent_criteria(pair.criteria_literal)
    return not NUMBER_TEXT.match(pair.criteria_text.strip())
