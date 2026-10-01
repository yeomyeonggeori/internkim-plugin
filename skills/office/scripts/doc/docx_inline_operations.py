from __future__ import annotations

import datetime

from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from doc.docx_editing import DocxEditing, placement, resolve_paragraph
from doc.docx_reference_operations import field_runs, insertion_point, place_runs
from doc.docx_settings import request_field_update
from doc.docx_text import visible_text
from doc.docx_tracking import mark_block_inserted
from doc.latex_math import OMML_NAMESPACE, LatexNotReadable, latex_omml
from core.office_operations import Change
from core.office_result import INVALID_VALUE, MISSING_FIELD, OfficeFailure


DATE_FIELDS = ("DATE", "TIME", "CREATEDATE", "SAVEDATE")
DEFAULT_PICTURES = {"TIME": "HH:mm"}
DEFAULT_DATE_PICTURE = "yyyy-MM-dd"
PICTURE_TOKENS = (("yyyy", "%Y"), ("yy", "%y"), ("MM", "%m"), ("dd", "%d"), ("HH", "%H"), ("mm", "%M"), ("ss", "%S"))


def omml_from_latex(latex: str, location: str):
    try:
        return latex_omml(latex)
    except LatexNotReadable as problem:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.latex: {problem}", f"{location}.latex", suggestion="use standard commands such as \\frac, \\sqrt, \\sum, ^ and _")) from problem


def plan_insert_equation(editing: DocxEditing, operation: dict, location: str) -> Change:
    equation = omml_from_latex(operation["latex"], location)
    if operation.get("block") is not None:
        return inline_equation(editing, operation, equation, location)
    place = placement(editing, operation, location)

    def change() -> str:
        paragraph = parse_xml(f'<w:p {nsdecls("w")} xmlns:m="{OMML_NAMESPACE}"><w:pPr><w:jc w:val="center"/></w:pPr><m:oMathPara/></w:p>')
        paragraph.find(f"{{{OMML_NAMESPACE}}}oMathPara").append(equation)
        place(paragraph)
        if editing.tracking is not None:
            mark_block_inserted(paragraph, editing.tracking)
        return "inserted a display equation"
    return change


def inline_equation(editing: DocxEditing, operation: dict, equation, location: str) -> Change:
    if any(operation.get(name) is not None for name in ("after", "before", "at")):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: give block for an equation inside a paragraph, or one of after, before and at for one on its own line", location))
    paragraph = resolve_paragraph(editing, operation["block"], f"{location}.block")
    anchor = insertion_point(paragraph._p, operation.get("afterText"), operation, location)

    def change() -> str:
        place_runs(paragraph._p, anchor, [equation])
        return f"inserted an equation in block {operation['block']}"
    return change


def plan_insert_field(editing: DocxEditing, operation: dict, location: str) -> Change:
    kind = operation["field"]
    if kind == "SEQ" and not operation.get("sequence"):
        raise OfficeFailure(MISSING_FIELD.issue(f"{location}.sequence: a SEQ field numbers a named sequence, such as 그림 or 표", f"{location}.sequence"))
    paragraph = resolve_paragraph(editing, operation["block"], f"{location}.block")
    anchor = insertion_point(paragraph._p, operation.get("afterText"), operation, location)

    def change() -> str:
        place_runs(paragraph._p, anchor, field_runs(field_instruction(operation), cached_result(editing, operation)))
        request_field_update(editing.document)
        return f"inserted a {kind} field in block {operation['block']}; Word updates it when the file opens"
    return change


def field_instruction(operation: dict) -> str:
    kind = operation["field"]
    if kind == "SEQ":
        return f"SEQ {operation['sequence']} \\* ARABIC"
    if kind in DATE_FIELDS:
        return f'{kind} \\@ "{date_picture(operation)}"'
    return kind


def date_picture(operation: dict) -> str:
    return operation.get("format") or DEFAULT_PICTURES.get(operation["field"], DEFAULT_DATE_PICTURE)


def cached_result(editing: DocxEditing, operation: dict) -> str:
    kind = operation["field"]
    if kind in DATE_FIELDS:
        return formatted_now(date_picture(operation))
    properties = editing.document.core_properties
    known = {"AUTHOR": properties.author, "TITLE": properties.title, "SUBJECT": properties.subject, "PAGE": "1", "SECTIONPAGES": "1", "NUMPAGES": "1", "SEQ": "1"}
    if kind == "NUMWORDS":
        return str(len(visible_text(editing.document.element.body).split()))
    return known.get(kind) or ""


def formatted_now(picture: str) -> str:
    pattern = picture
    for token, directive in PICTURE_TOKENS:
        pattern = pattern.replace(token, directive)
    return datetime.datetime.now().strftime(pattern)
