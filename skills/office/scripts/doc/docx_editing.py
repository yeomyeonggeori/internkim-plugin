from __future__ import annotations

from dataclasses import dataclass, field

from docx.document import Document
from docx.table import Table
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from doc.docx_blocks import PARAGRAPH_TAG, TABLE_TAG, body_block_elements
from fonts.docx_embedding import save_document
from doc.docx_package import open_document
from doc.docx_tracking import Tracking, start_tracking
from core.office_operations import OPERATION_NOT_APPLICABLE, TARGET_NOT_FOUND
from core.office_result import INVALID_VALUE, OfficeFailure
from core.office_schema import names_suggestion




@dataclass
class DocxEditing:
    document: Document
    elements: list
    cursors: dict = field(default_factory=dict)
    deleted: set = field(default_factory=set)
    touched: set = field(default_factory=set)
    tracking: Tracking | None = None


def load_editing(path: str, tracking_author: str | None = None) -> DocxEditing:
    document = open_document(path)
    tracking = start_tracking(tracking_author, document.element) if tracking_author else None
    return DocxEditing(document, body_block_elements(document), tracking=tracking)


def save_editing(editing: DocxEditing, path: str) -> None:
    save_document(editing.document, path)


def resolve_block(editing: DocxEditing, index: int, location: str):
    if index >= len(editing.elements):
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}: block {index} does not exist; the document has {len(editing.elements)} blocks", location, suggestion=index_range_suggestion("block", len(editing.elements))))
    element = editing.elements[index]
    if id(element) in editing.deleted:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: block {index} is deleted by another operation in this batch", location))
    editing.touched.add(id(element))
    return element


def resolve_paragraph(editing: DocxEditing, index: int, location: str) -> Paragraph:
    element = resolve_block(editing, index, location)
    if element.tag != PARAGRAPH_TAG:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: block {index} is not a paragraph", location))
    return Paragraph(element, editing.document._body)


def resolve_table(editing: DocxEditing, index: int, location: str) -> Table:
    element = resolve_block(editing, index, location)
    if element.tag != TABLE_TAG:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: block {index} is not a table", location))
    return Table(element, editing.document._body)


def require_style(editing: DocxEditing, style_name: str, style_types: tuple, location: str) -> None:
    style = next((style for style in editing.document.styles if style.name == style_name), None)
    if style is None:
        available = [style.name for style in editing.document.styles if style.type in style_types]
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}: the document defines no style named {style_name!r}", location, suggestion=names_suggestion(style_name, available)))
    if style.type not in style_types:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: style {style_name!r} cannot apply here", location))


def index_range_suggestion(noun: str, count: int) -> str:
    if count == 0:
        return f"the document has no {noun}s"
    return f"use a {noun} index from 0 to {count - 1}; office read lists them"


def placement(editing: DocxEditing, operation: dict, location: str):
    after, before, at = operation.get("after"), operation.get("before"), operation.get("at")
    if sum(value is not None for value in (after, before, at)) != 1:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: give exactly one of after, before and at", location, suggestion='after or before take a block index from office read; at takes "start" or "end"'))
    if before is not None:
        anchor = resolve_block(editing, before, f"{location}.before")
        return lambda element: anchor.addprevious(element)
    if at == "start":
        return start_placement(editing)
    if at == "end":
        return end_placement(editing)
    anchor = resolve_block(editing, after, f"{location}.after")
    return cursor_placement(editing, anchor)


def start_placement(editing: DocxEditing):
    def place(element):
        cursor = editing.cursors.get("start")
        if cursor is not None:
            cursor.addnext(element)
        elif editing.elements:
            editing.elements[0].addprevious(element)
        editing.cursors["start"] = element
    return place


def end_placement(editing: DocxEditing):
    body = editing.document.element.body
    section_properties = body.find(qn("w:sectPr"))

    def place(element):
        if section_properties is not None:
            section_properties.addprevious(element)
        else:
            body.append(element)
    return place


def cursor_placement(editing: DocxEditing, anchor):
    def place(element):
        editing.cursors.get(id(anchor), anchor).addnext(element)
        editing.cursors[id(anchor)] = element
    return place
