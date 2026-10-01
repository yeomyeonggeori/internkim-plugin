from __future__ import annotations

from dataclasses import replace

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches

from docx_charts import ROUND_KINDS, ChartSpecification, add_chart_part, document_charts, drawing_run, next_drawing_id, read_specification, rewrite_chart_part, specification
from docx_editing import DocxEditing, placement
from docx_tracking import mark_block_inserted
from office_operations import TARGET_NOT_FOUND, Change
from office_result import INVALID_VALUE, OfficeFailure


DEFAULT_HEIGHT_RATIO = 0.56
ALIGNMENT_VALUES = {"left": "left", "center": "center", "right": "right", "justify": "both"}


def require_consistent(spec: ChartSpecification, location: str) -> None:
    for index, (name, values, _) in enumerate(spec.series):
        if len(values) != len(spec.categories):
            raise OfficeFailure(INVALID_VALUE.issue(f"{location}.series[{index}]: {name!r} has {len(values)} values for {len(spec.categories)} categories", f"{location}.series[{index}].values", suggestion="give one number per category"))
    if spec.kind in ROUND_KINDS and len(spec.series) != 1:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.series: a {spec.kind} chart shows one series, not {len(spec.series)}", f"{location}.series", suggestion="give one series, or use column or bar"))
    if spec.kind in ROUND_KINDS and (any(value < 0 for value in spec.series[0][1]) or sum(spec.series[0][1]) <= 0):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.series: a {spec.kind} chart needs positive shares", f"{location}.series"))
    lines = sum(1 for _, _, is_line in spec.series if is_line)
    if spec.kind == "combo" and not 0 < lines < len(spec.series):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.series: a combo chart needs columns and at least one series with line: true", f"{location}.series", suggestion="mark the series to draw as a line with line: true"))


def text_width_inches(editing: DocxEditing) -> float:
    section = editing.document.sections[-1]
    return (section.page_width - section.left_margin - section.right_margin) / Inches(1)


def plan_insert_chart(editing: DocxEditing, operation: dict, location: str) -> Change:
    spec = specification(operation)
    require_consistent(spec, location)
    place = placement(editing, operation, location)

    def change() -> str:
        width = operation.get("widthInches") or text_width_inches(editing)
        height = operation.get("heightInches") or width * DEFAULT_HEIGHT_RATIO
        relationship_id = add_chart_part(editing.document, spec)
        paragraph = OxmlElement("w:p")
        if operation.get("align"):
            properties = paragraph.get_or_add_pPr()
            justification = OxmlElement("w:jc")
            justification.set(qn("w:val"), ALIGNMENT_VALUES[operation["align"]])
            properties.append(justification)
        drawing_id = next_drawing_id(editing.document)
        paragraph.append(drawing_run(relationship_id, int(Inches(width)), int(Inches(height)), drawing_id, f"Chart {drawing_id}"))
        place(paragraph)
        if editing.tracking is not None:
            mark_block_inserted(paragraph, editing.tracking)
        return f"inserted a {spec.kind} chart of {len(spec.series)} series over {len(spec.categories)} categories"
    return change


def resolve_chart(editing: DocxEditing, index: int, location: str):
    charts = document_charts(editing.document, editing.elements)
    if index >= len(charts):
        available = f"charts run 0-{len(charts) - 1}" if charts else "the document has no charts"
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.chart: chart {index} does not exist; {available}", f"{location}.chart", suggestion="doc read lists each chart's index"))
    return charts[index]


def plan_edit_chart(editing: DocxEditing, operation: dict, location: str) -> Change:
    chart = resolve_chart(editing, operation["chart"], location)
    current = read_specification(chart.part)
    updated = merged_specification(current, operation)
    require_consistent(updated, location)

    def change() -> str:
        rewrite_chart_part(chart.part, updated)
        changed = ", ".join(name for name in ("type", "categories", "series", "title", "legend", "secondaryAxis") if name in operation)
        return f"changed the {changed} of chart {operation['chart']}"
    return change


def merged_specification(current: ChartSpecification, operation: dict) -> ChartSpecification:
    given = specification({
        "type": operation.get("type", current.kind),
        "categories": operation.get("categories", list(current.categories)),
        "series": operation.get("series") or [{"name": name, "values": list(values), "line": is_line} for name, values, is_line in current.series],
        "title": operation.get("title", current.title),
        "legend": operation.get("legend", current.legend),
        "secondaryAxis": operation.get("secondaryAxis", current.secondary_axis),
    })
    return replace(given, legend=operation.get("legend", current.legend))


def plan_delete_chart(editing: DocxEditing, operation: dict, location: str) -> Change:
    chart = resolve_chart(editing, operation["chart"], location)

    def change() -> str:
        run = chart.drawing.getparent()
        paragraph = next(run.iterancestors(qn("w:p")), None)
        run.getparent().remove(run)
        if paragraph is not None and not paragraph_has_content(paragraph) and paragraph.getparent() is not None:
            paragraph.getparent().remove(paragraph)
            editing.deleted.add(id(paragraph))
        return f"deleted chart {operation['chart']}"
    return change


def paragraph_has_content(paragraph) -> bool:
    return any(text.text for text in paragraph.iter(qn("w:t"))) or paragraph.find(f".//{qn('w:drawing')}") is not None
