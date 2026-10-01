from __future__ import annotations

from dataclasses import dataclass, field
import difflib

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from docx_blocks import PARAGRAPH_TAG, TABLE_TAG, body_block_elements
from docx_tracking import Tracking, start_tracking
from office_operations import OPERATION_NOT_APPLICABLE, TARGET_NOT_FOUND
from office_result import INVALID_VALUE, OfficeFailure


@dataclass
class DocxEditing:
    document: Document
    elements: list
    cursors: dict = field(default_factory=dict)
    deleted: set = field(default_factory=set)
    touched: set = field(default_factory=set)
    tracking: Tracking | None = None


def load_editing(path: str, tracking_author: str | None = None) -> DocxEditing:
    document = Document(path)
    tracking = start_tracking(tracking_author, document.element) if tracking_author else None
    return DocxEditing(document, body_block_elements(document), tracking=tracking)


def save_editing(editing: DocxEditing, path: str) -> None:
    editing.document.save(path)


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
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}: the document defines no style named {style_name!r}", location, suggestion=closest_suggestion(style_name, available)))
    if style.type not in style_types:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: style {style_name!r} cannot apply here", location))


def index_range_suggestion(noun: str, count: int) -> str:
    if count == 0:
        return f"the document has no {noun}s"
    return f"use a {noun} index from 0 to {count - 1}; doc read lists them"


def closest_suggestion(given: str, available: list[str]) -> str:
    closest = difflib.get_close_matches(given, available, n=3, cutoff=0.5)
    listed = ", ".join(repr(name) for name in available[:40])
    if closest:
        return f"did you mean {', '.join(repr(name) for name in closest)}? available: {listed}"
    return f"available: {listed}"


def placement(editing: DocxEditing, operation: dict, location: str):
    after, before = operation.get("after"), operation.get("before")
    if (after is None) == (before is None):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: give exactly one of after and before", location))
    if before is not None:
        anchor = resolve_block(editing, before, f"{location}.before")
        return lambda element: anchor.addprevious(element)
    if after == -1:
        return start_placement(editing)
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


def cursor_placement(editing: DocxEditing, anchor):
    def place(element):
        editing.cursors.get(id(anchor), anchor).addnext(element)
        editing.cursors[id(anchor)] = element
    return place
