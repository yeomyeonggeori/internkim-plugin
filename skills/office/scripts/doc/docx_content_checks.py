from __future__ import annotations

from dataclasses import dataclass, field

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from lxml import etree

from doc_definitions import CHART_EMPTY, EMPTY_HEADING, FIELD_NOT_EVALUATED, HEADING_SKIP, MISSING_IMAGE, UNRESOLVED_COMMENTS
from docx_blocks import PARAGRAPH_TAG, element_text, heading_level
from docx_charts import CHART_NAMESPACE, cached_points, document_charts, is_number, read_specification
from docx_comments import describe_comment_threads
from office_result import Issue


DRAWING_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/main"
BLIP_TAG = f"{{{DRAWING_NAMESPACE}}}blip"
EMBED_ATTRIBUTE = qn("r:embed")
LINK_ATTRIBUTE = qn("r:link")
FIELDS_WITHOUT_A_SHOWN_RESULT = frozenset({"TOC", "XE", "TA", "INDEX", "TC", "PRIVATE", "RD", "MERGEFIELD"})


@dataclass
class OpenField:
    instruction: list[str] = field(default_factory=list)
    result: list[str] = field(default_factory=list)
    has_result: bool = False


def missing_image_issues(document, elements: list) -> list[Issue]:
    issues = []
    for index, element in enumerate(elements):
        broken = [blip for blip in element.iter(BLIP_TAG) if not shows_a_picture(blip, document.part)]
        if broken:
            issues.append(MISSING_IMAGE.issue(f"block {index} has {len(broken)} pictures whose image part is missing, so they show nothing", f"block {index}", suggestion=missing_image_suggestion(element, index)))
    return issues


def shows_a_picture(blip, part) -> bool:
    if blip.get(LINK_ATTRIBUTE):
        return True
    relationship = part.rels.get(blip.get(EMBED_ATTRIBUTE) or "")
    if relationship is None or relationship.is_external:
        return False
    return relationship.target_part.content_type.startswith("image/")


def missing_image_suggestion(element, index: int) -> dict | str:
    if element.tag == PARAGRAPH_TAG and not element_text(element).strip():
        return {"op": "delete_block", "block": index}
    return f"insert_image after block {index} with the picture file, then remove the broken one"


def chart_empty_issues(document, elements: list) -> list[Issue]:
    return [
        CHART_EMPTY.issue(f"chart {chart.index} has no number in any series, so it draws nothing", f"block {chart.block}", suggestion=chart_data_suggestion(chart))
        for chart in document_charts(document, elements)
        if not has_numbers(chart.part)
    ]


def has_numbers(chart_part) -> bool:
    root = etree.fromstring(chart_part.blob)
    return any(is_number(value) for series in root.iter(f"{{{CHART_NAMESPACE}}}ser") for value in cached_points(series, "val"))


def chart_data_suggestion(chart) -> dict:
    specification = read_specification(chart.part)
    categories = list(specification.categories) or ["<label>"]
    names = [name for name, _values, _is_line in specification.series if name] or ["<series name>"]
    return {"op": "edit_chart", "chart": chart.index, "categories": categories, "series": [{"name": name, "values": ["<number>"] * len(categories)} for name in names]}


def heading_issues(document, elements: list) -> list[Issue]:
    issues = []
    previous_level = 0
    for index, element in enumerate(elements):
        level = paragraph_heading_level(element, document)
        if level is None:
            continue
        if not element_text(element).strip():
            if element.find(f".//{qn('w:drawing')}") is None:
                issues.append(EMPTY_HEADING.issue(f"block {index} is a level {level} heading with no text", f"block {index}", suggestion={"op": "delete_block", "block": index}))
            continue
        if level == 0:
            continue
        if previous_level and level > previous_level + 1:
            issues.append(HEADING_SKIP.issue(f"block {index} jumps from heading level {previous_level} to {level}", f"block {index}", suggestion={"op": "set_style", "block": index, "style": f"Heading {previous_level + 1}"}))
        previous_level = level
    return issues


def paragraph_heading_level(element, document) -> int | None:
    if element.tag != PARAGRAPH_TAG:
        return None
    return heading_level(Paragraph(element, document._body))


def unresolved_comment_issues(document, elements: list) -> list[Issue]:
    open_threads = [thread for thread in describe_comment_threads(document, elements) if not thread["resolved"]]
    if not open_threads:
        return []
    first = open_threads[0]
    location = f"block {first['block']}" if first["block"] is not None else "comments"
    return [UNRESOLVED_COMMENTS.issue(f"{len(open_threads)} comment threads are unresolved; doc read lists them under comments", location, suggestion={"op": "resolve_comment", "comment": first["id"]})]


def field_result_issues(elements: list, fields_update_on_open: bool) -> list[Issue]:
    if fields_update_on_open:
        return []
    empty = [(index, keyword) for index, element in enumerate(elements) for keyword in fields_without_result(element)]
    if not empty:
        return []
    index, keyword = empty[0]
    return [FIELD_NOT_EVALUATED.issue(f"{len(empty)} fields show no result until Word updates them, such as {keyword or 'a field'} in block {index}", f"block {index}", suggestion={"op": "update_fields_on_open"})]


def fields_without_result(element) -> list[str]:
    results = simple_field_results(element) + complex_field_results(element)
    return [keyword for keyword, result in results if keyword not in FIELDS_WITHOUT_A_SHOWN_RESULT and not result.strip()]


def simple_field_results(element) -> list[tuple[str, str]]:
    return [(field_keyword(simple.get(qn("w:instr")) or ""), "".join(text.text or "" for text in simple.iter(qn("w:t")))) for simple in element.iter(qn("w:fldSimple"))]


def complex_field_results(element) -> list[tuple[str, str]]:
    results, open_fields = [], []
    for node in element.iter(qn("w:fldChar"), qn("w:instrText"), qn("w:t")):
        if node.tag == qn("w:instrText"):
            if open_fields and not open_fields[-1].has_result:
                open_fields[-1].instruction.append(node.text or "")
        elif node.tag == qn("w:t"):
            for open_field in open_fields:
                if open_field.has_result:
                    open_field.result.append(node.text or "")
        else:
            record_field_character(node.get(qn("w:fldCharType")), open_fields, results)
    return results


def record_field_character(character_type: str | None, open_fields: list[OpenField], results: list) -> None:
    if character_type == "begin":
        open_fields.append(OpenField())
    elif character_type == "separate" and open_fields:
        open_fields[-1].has_result = True
    elif character_type == "end" and open_fields:
        closed = open_fields.pop()
        results.append((field_keyword("".join(closed.instruction)), "".join(closed.result)))


def field_keyword(instruction: str) -> str:
    words = instruction.replace("\\", " ").split()
    return words[0].upper() if words else ""
