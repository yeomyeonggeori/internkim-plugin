from __future__ import annotations

import copy
from pathlib import Path

from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from doc.model.body import PARAGRAPH_TAG, heading_level, is_list_item
from doc.operations.editing import DocxEditing, placement, require_style, resolve_block
from doc.model.lists import LIST_LEVEL_COUNT, LIST_PARAGRAPH_STYLE, start_list
from doc.blocks.docx import add_block
from doc.operations.tracking import mark_block_deleted, mark_block_inserted, record_paragraph_property_change, snapshot_paragraph_properties
from doc.blocks.markdown import Heading, Image, ListItem, Table, local_image_problem, parse_markdown
from doc.blocks.charts import Chart
from core.office_operations import OPERATION_NOT_APPLICABLE, Change
from core.office_result import INPUT_NOT_FOUND, INVALID_VALUE, OfficeFailure


LIST_STYLE_PREFIX = "List"


def plan_move_blocks(editing: DocxEditing, operation: dict, location: str) -> Change:
    indexes = sorted(set(operation["blocks"]))
    if len(indexes) != len(operation["blocks"]):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.blocks: an index is listed twice", f"{location}.blocks"))
    anchor = operation.get("after", operation.get("before"))
    if anchor in indexes:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: block {anchor} cannot be moved next to itself", location, suggestion="anchor the move on a block outside blocks"))
    elements = [resolve_block(editing, index, f"{location}.blocks") for index in indexes]
    place = placement(editing, operation, location)

    def change() -> str:
        for element in elements:
            if editing.tracking is None:
                place(element)
                continue
            moved = copy.deepcopy(element)
            mark_block_deleted(element, editing.tracking)
            place(moved)
            mark_block_inserted(moved, editing.tracking)
        tracked = " as tracked deletions and insertions" if editing.tracking is not None else ""
        return f"moved blocks {', '.join(map(str, indexes))}{tracked}"
    return change


def block_range(editing: DocxEditing, operation: dict, location: str) -> list:
    last = operation.get("toBlock", operation["block"])
    if last < operation["block"]:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.toBlock: {last} comes before block {operation['block']}", f"{location}.toBlock"))
    return [resolve_block(editing, index, f"{location}.block") for index in range(operation["block"], last + 1)]


def range_paragraphs(editing: DocxEditing, operation: dict, location: str) -> list[Paragraph]:
    elements = block_range(editing, operation, location)
    if any(element.tag != PARAGRAPH_TAG for element in elements):
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: the range holds a table; lists are made of paragraphs", location))
    return [Paragraph(element, editing.document._body) for element in elements]


def plan_set_list(editing: DocxEditing, operation: dict, location: str) -> Change:
    require_style(editing, LIST_PARAGRAPH_STYLE, (WD_STYLE_TYPE.PARAGRAPH,), location)
    paragraphs = [paragraph for paragraph in range_paragraphs(editing, operation, location) if heading_level(paragraph) is None]
    if not paragraphs:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: every block in the range is a heading, and headings are not made list items", location))
    level = min(operation.get("level") or 0, LIST_LEVEL_COUNT - 1)

    def change() -> str:
        list_id = start_list(editing.document, bool(operation.get("numbered")))
        for paragraph in paragraphs:
            with_tracked_properties(editing, paragraph, lambda: make_list_item(paragraph, list_id, level))
        kind = "numbered" if operation.get("numbered") else "bulleted"
        return f"made {len(paragraphs)} paragraphs a {kind} list"
    return change


def make_list_item(paragraph: Paragraph, list_id: int, level: int) -> None:
    paragraph.style = LIST_PARAGRAPH_STYLE
    number_properties = paragraph._p.get_or_add_pPr().get_or_add_numPr()
    number_properties.get_or_add_ilvl().val = level
    number_properties.get_or_add_numId().val = list_id


def plan_clear_list(editing: DocxEditing, operation: dict, location: str) -> Change:
    paragraphs = [paragraph for paragraph in range_paragraphs(editing, operation, location) if is_list_item(paragraph)]
    if not paragraphs:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: no block in the range is a list item", location))
    require_style(editing, "Normal", (WD_STYLE_TYPE.PARAGRAPH,), location)

    def change() -> str:
        for paragraph in paragraphs:
            with_tracked_properties(editing, paragraph, lambda: make_body_paragraph(paragraph))
        return f"made {len(paragraphs)} list items body paragraphs"
    return change


def make_body_paragraph(paragraph: Paragraph) -> None:
    properties = paragraph._p.pPr
    if properties is not None and properties.numPr is not None:
        properties.remove(properties.numPr)
    if paragraph.style is not None and paragraph.style.name.startswith(LIST_STYLE_PREFIX):
        paragraph.style = "Normal"


def with_tracked_properties(editing: DocxEditing, paragraph: Paragraph, edit) -> None:
    old_properties = snapshot_paragraph_properties(paragraph._p) if editing.tracking is not None else None
    edit()
    if old_properties is not None:
        record_paragraph_property_change(paragraph._p, old_properties, editing.tracking)


def plan_insert_markdown(editing: DocxEditing, operation: dict, location: str) -> Change:
    blocks = markdown_blocks(editing, operation["markdown"], location)
    place = placement(editing, operation, location)

    def change() -> str:
        for element in written_elements(editing, blocks):
            place(element)
            if editing.tracking is not None:
                mark_block_inserted(element, editing.tracking)
        return f"inserted {len(blocks)} Markdown blocks"
    return change


def plan_replace_blocks(editing: DocxEditing, operation: dict, location: str) -> Change:
    blocks = markdown_blocks(editing, operation["markdown"], location)
    replaced = block_range(editing, operation, location)
    editing.deleted.update(id(element) for element in replaced)

    def change() -> str:
        for element in written_elements(editing, blocks):
            replaced[0].addprevious(element)
            if editing.tracking is not None:
                mark_block_inserted(element, editing.tracking)
        for element in replaced:
            if editing.tracking is not None:
                mark_block_deleted(element, editing.tracking)
            else:
                element.getparent().remove(element)
        return f"replaced blocks {operation['block']} to {operation.get('toBlock', operation['block'])} with {len(blocks)} Markdown blocks"
    return change


def markdown_blocks(editing: DocxEditing, markdown: str, location: str) -> list:
    blocks = parse_markdown(markdown)
    if not blocks:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.markdown: no block in it", f"{location}.markdown"))
    for block in blocks:
        require_markdown_block(editing, block, location)
    return blocks


def require_markdown_block(editing: DocxEditing, block, location: str) -> None:
    if isinstance(block, Chart) and block.problems:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.markdown: chart block: {block.problems[0]}", f"{location}.markdown"))
    if isinstance(block, Image):
        problem = local_image_problem(block.source, Path(block.source))
        if problem:
            raise OfficeFailure(INPUT_NOT_FOUND.issue(f"{location}.markdown: image {block.source} {problem}", f"{location}.markdown", suggestion="use a local path relative to the directory office apply runs in"))
    style = required_style(block)
    if style:
        require_style(editing, style[0], (style[1],), f"{location}.markdown")


def required_style(block) -> tuple[str, object] | None:
    if isinstance(block, Heading):
        return f"Heading {block.level}", WD_STYLE_TYPE.PARAGRAPH
    if isinstance(block, ListItem):
        return LIST_PARAGRAPH_STYLE, WD_STYLE_TYPE.PARAGRAPH
    if isinstance(block, Table):
        return "Table Grid", WD_STYLE_TYPE.TABLE
    return None


def written_elements(editing: DocxEditing, blocks: list) -> list:
    body = editing.document.element.body
    existing = set(body)
    list_ids: dict[bool, int] = {}
    for block in blocks:
        if not isinstance(block, ListItem):
            list_ids.clear()
        add_block(editing.document, block, Path("."), list_ids)
    written = [child for child in body if child not in existing and child.tag != qn("w:sectPr")]
    for element in written:
        body.remove(element)
    return written
