from __future__ import annotations

import html
import re
from xml.etree import ElementTree

import latex2mathml.converter
from latex2mathml.exceptions import (
    DenominatorNotFoundError,
    DoubleSubscriptsError,
    DoubleSuperscriptsError,
    ExtraLeftOrMissingRightError,
    InvalidAlignmentError,
    InvalidStyleForGenfracError,
    InvalidWidthError,
    LimitsMustFollowMathOperatorError,
    MissingEndError,
    MissingSuperScriptOrSubscriptError,
    NoAvailableTokensError,
    NumeratorNotFoundError,
)
import mathml2omml
from docx.oxml import parse_xml
from lxml import etree

from doc.doc_definitions import MATH_NOT_CONVERTED
from doc.markdown_blocks import Equation, Table, inline_segments, math_latex
from core.office_result import Issue


OMML_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/math"
UNKNOWN_COMMAND = re.compile(r"\\[A-Za-z]")
TOKEN_ELEMENTS = ("mi", "mn", "mo", "mtext", "ms")
STACKED_ELEMENTS = {"munder": ("under",), "mover": ("over",), "munderover": ("under", "over")}
OVERBARS = frozenset("¯‾―")
ARGUMENT_COUNTS = {"mfrac": 2, "msup": 2, "msub": 2, "msubsup": 3, "mroot": 2, "munder": 2, "mover": 2, "munderover": 3}
LATEX_ERROR_REASONS = {
    NoAvailableTokensError: "a command or a brace ends before what it needs",
    MissingSuperScriptOrSubscriptError: "a ^ or _ has nothing after it",
    NumeratorNotFoundError: "a \\frac has no numerator",
    DenominatorNotFoundError: "a \\frac has no denominator",
    DoubleSubscriptsError: "two _ apply to one symbol; group them with braces",
    DoubleSuperscriptsError: "two ^ apply to one symbol; group them with braces",
    ExtraLeftOrMissingRightError: "a \\left has no matching \\right",
    MissingEndError: "a \\begin has no matching \\end",
    LimitsMustFollowMathOperatorError: "\\limits follows something other than an operator such as \\sum",
    InvalidAlignmentError: "a matrix column alignment is not l, c or r",
    InvalidStyleForGenfracError: "a \\genfrac style is not 0 to 3",
    InvalidWidthError: "a width is not a TeX length such as 2em",
}
RULE = "1px solid #1f2328"
ROW = "display:inline-flex;align-items:center;white-space:nowrap"
FRACTION = "display:inline-flex;flex-direction:column;align-items:center;margin:0 .12em"
SCRIPT = "display:inline-block;font-size:70%"
RAISED = f"{SCRIPT};transform:translateY(-0.45em)"
LOWERED = f"{SCRIPT};transform:translateY(0.3em)"
SCRIPT_PAIR = "display:inline-flex;flex-direction:column;font-size:70%;line-height:1.05;transform:translateY(-0.2em)"
LIMITS = "display:inline-flex;flex-direction:column;align-items:center;line-height:1.1;margin:0 .1em"
MATRIX = "display:inline-flex;flex-direction:column;margin:0 .15em"
MATRIX_ROW = "display:flex;gap:.8em;justify-content:space-between"


class LatexNotReadable(Exception):
    pass


def latex_error_reason(error: Exception) -> str:
    return LATEX_ERROR_REASONS.get(type(error)) or str(error) or type(error).__name__


def latex_mathml(latex: str, display: bool) -> str:
    try:
        mathml = latex2mathml.converter.convert(latex, display="block" if display else "inline")
    except (*LATEX_ERROR_REASONS, RuntimeError, ValueError, IndexError, KeyError) as error:
        raise LatexNotReadable(f"{latex!r} is not LaTeX this converter reads: {latex_error_reason(error)}") from error
    tree = ElementTree.fromstring(mathml)
    if any(UNKNOWN_COMMAND.search(text) for text in tree.itertext()):
        raise LatexNotReadable(f"{latex!r} uses a command the converter does not know")
    if any(len(element) != ARGUMENT_COUNTS[local_name(element)] for element in tree.iter() if local_name(element) in ARGUMENT_COUNTS):
        raise LatexNotReadable(f"{latex!r} is not LaTeX this converter reads: a command is missing an argument or a closing brace")
    return mathml


def math_issues(blocks: list, target: str) -> list[Issue]:
    convert = latex_omml if target == "docx" else latex_html
    formulas = [(block.latex, True) for block in blocks if isinstance(block, Equation)]
    formulas += [(latex, False) for text in block_texts(blocks) for latex in map(math_latex, inline_segments(text)) if latex is not None]
    return [MATH_NOT_CONVERTED.issue(str(problem), latex) for latex, display in formulas for problem in latex_problems(convert, latex, display)]


def block_texts(blocks: list) -> list[str]:
    return [text for block in blocks for text in texts_of(block)]


def texts_of(block) -> list[str]:
    if isinstance(block, Table):
        return [cell for row in block.rows for cell in row]
    if isinstance(block, Equation):
        return []
    return [getattr(block, "text", "")]


def latex_problems(convert, latex: str, display: bool) -> list[LatexNotReadable]:
    try:
        convert(latex, display)
    except LatexNotReadable as problem:
        return [problem]
    return []


def text_with_math_drawn(text: str) -> str:
    return "".join(segment if math_latex(segment) is None else math_text(math_latex(segment)) for segment in inline_segments(text))


def math_text(latex: str, display: bool = False) -> str:
    try:
        return "".join(ElementTree.fromstring(latex_html(latex, display)).itertext())
    except LatexNotReadable:
        return latex


def latex_omml(latex: str, display: bool = False):
    mathml = latex_mathml(latex, display)
    try:
        omml = mathml2omml.convert(mathml)
        return parse_xml(f'<m:oMath xmlns:m="{OMML_NAMESPACE}">{omml.removeprefix("<m:oMath>").removesuffix("</m:oMath>")}</m:oMath>')
    except (ValueError, IndexError, KeyError, AttributeError, TypeError, etree.XMLSyntaxError) as error:
        raise LatexNotReadable(f"{latex!r} has no Word equation form: mathml2omml wrote {str(error) or type(error).__name__}") from error


def latex_html(latex: str, display: bool = False) -> str:
    return f'<span class="math" style="{ROW}">{element_html(ElementTree.fromstring(latex_mathml(latex, display)))}</span>'


def local_name(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def element_html(element) -> str:
    name = local_name(element)
    parts = [element_html(child) for child in element]
    if name in TOKEN_ELEMENTS:
        return html.escape(element.text or "")
    if name == "mspace":
        return " "
    if name == "mfrac":
        return f'<span style="{FRACTION}"><span style="{ROW};border-bottom:{RULE};padding:0 .1em">{parts[0]}</span><span style="{ROW};padding:0 .1em">{parts[1]}</span></span>'
    if name == "msup":
        return f'{parts[0]}<span style="{RAISED}">{parts[1]}</span>'
    if name == "msub":
        return f'{parts[0]}<span style="{LOWERED}">{parts[1]}</span>'
    if name == "msubsup":
        return f'{parts[0]}<span style="{SCRIPT_PAIR}"><span>{parts[2]}</span><span>{parts[1]}</span></span>'
    if name == "msqrt":
        return radical("", "".join(parts))
    if name == "mroot":
        return radical(parts[1], parts[0])
    if name == "mover" and (element[1].text or "").strip() in OVERBARS:
        return f'<span style="{ROW};border-top:{RULE}">{parts[0]}</span>'
    if name in STACKED_ELEMENTS:
        return limits(parts, STACKED_ELEMENTS[name])
    if name == "mtable":
        return f'<span style="{MATRIX}">{"".join(parts)}</span>'
    if name == "mtr":
        return f'<span style="{MATRIX_ROW}">{"".join(f"<span>{part}</span>" for part in parts)}</span>'
    return "".join(parts)


def radical(index: str, radicand: str) -> str:
    degree = f'<span style="{RAISED}">{index}</span>' if index else ""
    return f'{degree}√<span style="{ROW};border-top:{RULE};padding-top:.05em">{radicand}</span>'


def limits(parts: list[str], positions: tuple[str, ...]) -> str:
    under = parts[1] if "under" in positions else ""
    over = parts[-1] if "over" in positions else ""
    return f'<span style="{LIMITS}"><span style="font-size:70%">{over}</span><span>{parts[0]}</span><span style="font-size:70%">{under}</span></span>'
