from __future__ import annotations

from dataclasses import dataclass

from docx.opc.constants import RELATIONSHIP_TYPE
from docx.opc.part import Part
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.run import Run
from lxml import etree

from doc.docx_parts import create_part, read_root, related_part, write_root
from doc.docx_editing import DocxEditing, resolve_paragraph
from doc.docx_text import REMOVED_RUN_CONTAINER_TAGS, RUN_TAG, live_runs, run_text, visible_text
from doc.docx_tracking import runs_between, split_runs_at
from core.office_operations import OPERATION_NOT_APPLICABLE, TARGET_NOT_FOUND, Change
from core.office_result import MISSING_FIELD, OfficeFailure


WORD_2010_NAMESPACE = "http://schemas.microsoft.com/office/word/2010/wordml"
WORD_2012_NAMESPACE = "http://schemas.microsoft.com/office/word/2012/wordml"
PARAGRAPH_IDENTIFIER = f"{{{WORD_2010_NAMESPACE}}}paraId"
COMMENT_EXTENDED_TAG = f"{{{WORD_2012_NAMESPACE}}}commentEx"
EXTENDED_PARAGRAPH_IDENTIFIER = f"{{{WORD_2012_NAMESPACE}}}paraId"
EXTENDED_PARENT_IDENTIFIER = f"{{{WORD_2012_NAMESPACE}}}paraIdParent"
EXTENDED_DONE = f"{{{WORD_2012_NAMESPACE}}}done"
COMMENTS_EXTENDED_RELATIONSHIP = "http://schemas.microsoft.com/office/2011/relationships/commentsExtended"
COMMENTS_EXTENDED_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml"
COMMENTS_EXTENDED_PART_NAME = "/word/commentsExtended.xml"
FIRST_PARAGRAPH_IDENTIFIER = 0x1C000000
COMMENT_MARKER_TAGS = (qn("w:commentRangeStart"), qn("w:commentRangeEnd"), qn("w:commentReference"))


@dataclass(frozen=True)
class CommentThreadInfo:
    parent: str | None
    done: bool


def comments_element(document):
    try:
        return document.part.part_related_by(RELATIONSHIP_TYPE.COMMENTS).element
    except KeyError:
        return None


def extended_part(document, create: bool) -> Part | None:
    part = related_part(document, COMMENTS_EXTENDED_RELATIONSHIP)
    if part is not None or not create:
        return part
    root = etree.Element(f"{{{WORD_2012_NAMESPACE}}}commentsEx", nsmap={"w15": WORD_2012_NAMESPACE})
    return create_part(document, COMMENTS_EXTENDED_RELATIONSHIP, COMMENTS_EXTENDED_PART_NAME, COMMENTS_EXTENDED_CONTENT_TYPE, root)


def thread_infos(document) -> dict[str, CommentThreadInfo]:
    part = extended_part(document, create=False)
    if part is None:
        return {}
    return {
        entry.get(EXTENDED_PARAGRAPH_IDENTIFIER): CommentThreadInfo(entry.get(EXTENDED_PARENT_IDENTIFIER), entry.get(EXTENDED_DONE) in ("1", "true"))
        for entry in read_root(part).iter(COMMENT_EXTENDED_TAG)
    }


def comment_paragraph_identifier(comment) -> str | None:
    paragraphs = comment.findall(qn("w:p"))
    return paragraphs[-1].get(PARAGRAPH_IDENTIFIER) if paragraphs else None


def describe_comment_threads(document, block_elements: list) -> list[dict]:
    comments = comments_element(document)
    if comments is None:
        return []
    anchors = comment_anchors(document.element.body, block_elements)
    infos = thread_infos(document)
    entries = [comment_entry(comment, anchors, infos) for comment in comments.iterchildren(qn("w:comment"))]
    by_paragraph = {entry["paragraphId"]: entry for entry in entries if entry["paragraphId"]}
    threads = []
    for entry in entries:
        parent = by_paragraph.get(entry.pop("parentParagraphId"))
        if parent is not None and parent is not entry:
            parent["replies"].append(entry)
        else:
            threads.append(entry)
    for entry in entries:
        entry.pop("paragraphId")
        if not entry["replies"]:
            entry.pop("replies")
    return threads


def comment_entry(comment, anchors: dict, infos: dict) -> dict:
    identifier = comment.get(qn("w:id"))
    paragraph_identifier = comment_paragraph_identifier(comment)
    info = infos.get(paragraph_identifier, CommentThreadInfo(None, False))
    block, anchor_text = anchors.get(identifier, (None, ""))
    return {
        "id": int(identifier),
        "author": comment.get(qn("w:author")) or "",
        "date": comment.get(qn("w:date")),
        "text": visible_text(comment),
        "block": block,
        "anchorText": anchor_text,
        "resolved": info.done,
        "replies": [],
        "paragraphId": paragraph_identifier,
        "parentParagraphId": info.parent,
    }


def comment_anchors(body, block_elements: list) -> dict[str, tuple]:
    block_indexes = {id(element): index for index, element in enumerate(block_elements)}
    open_ranges: dict[str, list[str]] = {}
    anchors: dict[str, tuple] = {}
    for block in body.iterchildren():
        for element in block.iter(qn("w:commentRangeStart"), qn("w:commentRangeEnd"), RUN_TAG, qn("w:p")):
            record_anchor_event(element, open_ranges, anchors, block_indexes.get(id(block)))
    return {identifier: (block, "".join(text).strip()) for identifier, (block, text) in anchors.items()}


def record_anchor_event(element, open_ranges: dict, anchors: dict, block: int | None) -> None:
    identifier = element.get(qn("w:id"))
    if element.tag == qn("w:commentRangeStart"):
        open_ranges[identifier] = []
        anchors[identifier] = (block, open_ranges[identifier])
    elif element.tag == qn("w:commentRangeEnd"):
        open_ranges.pop(identifier, None)
    elif element.tag == qn("w:p"):
        for text in open_ranges.values():
            if text:
                text.append("\n")
    elif not is_removed_run(element):
        for text in open_ranges.values():
            text.append(run_text(element))


def is_removed_run(run) -> bool:
    ancestor = run.getparent()
    while ancestor is not None:
        if ancestor.tag in REMOVED_RUN_CONTAINER_TAGS:
            return True
        ancestor = ancestor.getparent()
    return False


def comment_author(editing: DocxEditing, operation: dict, location: str) -> str:
    if operation.get("author"):
        return operation["author"]
    if editing.tracking is not None and editing.tracking.author:
        return editing.tracking.author
    raise OfficeFailure(MISSING_FIELD.issue(f"{location}.author: a comment needs the name of the person it is from", f"{location}.author", suggestion="give author, or run doc apply with --track --author"))


def plan_add_comment(editing: DocxEditing, operation: dict, location: str) -> Change:
    paragraph = resolve_paragraph(editing, operation["block"], f"{location}.block")
    if not live_runs(paragraph._p):
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: block {operation['block']} has no text to comment on", location))
    runs = anchor_runs(paragraph, anchor_span(paragraph._p, operation, location))
    comment = editing.document.add_comment(runs, text=operation["text"], author=comment_author(editing, operation, location))
    ensure_paragraph_identifier(editing.document, comment._comment_elm)

    def change() -> str:
        anchored = f" on {operation['find']!r}" if operation.get("find") else ""
        return f"added comment {comment.comment_id} to block {operation['block']}{anchored}"
    return change


def anchor_span(paragraph_element, operation: dict, location: str) -> tuple[int, int] | None:
    find = operation.get("find")
    if not find:
        return None
    text = "".join(run_text(run) for run in live_runs(paragraph_element))
    starts = occurrence_starts(text, find)
    occurrence = operation.get("occurrence") or 1
    if occurrence > len(starts):
        found = f"occurs {len(starts)} times" if starts else "does not occur"
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.find: {find!r} {found} in block {operation['block']}", f"{location}.find", suggestion=f"copy the exact text from doc read: {text[:120]!r}"))
    start = starts[occurrence - 1]
    return start, start + len(find)


def occurrence_starts(text: str, find: str) -> list[int]:
    starts = []
    position = text.find(find)
    while position >= 0:
        starts.append(position)
        position = text.find(find, position + len(find))
    return starts


def anchor_runs(paragraph, span: tuple[int, int] | None) -> list[Run]:
    if span is None:
        return [Run(run, paragraph) for run in live_runs(paragraph._p)]
    split_runs_at(paragraph._p, span)
    return [Run(run, paragraph) for run in runs_between(paragraph._p, *span)]


def ensure_paragraph_identifier(document, comment) -> str:
    paragraph = comment.findall(qn("w:p"))[-1]
    existing = paragraph.get(PARAGRAPH_IDENTIFIER)
    if existing:
        return existing
    used = {element.get(PARAGRAPH_IDENTIFIER) for element in document.element.iter(qn("w:p"))}
    used |= {element.get(PARAGRAPH_IDENTIFIER) for element in comments_element(document).iter(qn("w:p"))}
    candidate = FIRST_PARAGRAPH_IDENTIFIER + int(comment.get(qn("w:id")))
    while f"{candidate:08X}" in used:
        candidate += 1
    paragraph.set(PARAGRAPH_IDENTIFIER, f"{candidate:08X}")
    return f"{candidate:08X}"


def find_comment(editing: DocxEditing, identifier: int, location: str):
    comments = comments_element(editing.document)
    found = None if comments is None else next((comment for comment in comments.iterchildren(qn("w:comment")) if comment.get(qn("w:id")) == str(identifier)), None)
    if found is None:
        available = [] if comments is None else [comment.get(qn("w:id")) for comment in comments.iterchildren(qn("w:comment"))]
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.comment: comment {identifier} does not exist", f"{location}.comment", suggestion=f"use a comment id doc read lists: {', '.join(available) or 'the document has no comments'}"))
    return found


def thread_root(editing: DocxEditing, comment):
    infos = thread_infos(editing.document)
    info = infos.get(comment_paragraph_identifier(comment))
    if info is None or info.parent is None:
        return comment
    comments = comments_element(editing.document)
    return next((candidate for candidate in comments.iterchildren(qn("w:comment")) if comment_paragraph_identifier(candidate) == info.parent), comment)


def set_extended_entry(editing: DocxEditing, comment, parent_identifier: str | None = None, done: bool | None = None) -> None:
    paragraph_identifier = ensure_paragraph_identifier(editing.document, comment)
    part = extended_part(editing.document, create=True)
    root = read_root(part)
    entry = next((entry for entry in root.iter(COMMENT_EXTENDED_TAG) if entry.get(EXTENDED_PARAGRAPH_IDENTIFIER) == paragraph_identifier), None)
    if entry is None:
        entry = etree.SubElement(root, COMMENT_EXTENDED_TAG)
        entry.set(EXTENDED_PARAGRAPH_IDENTIFIER, paragraph_identifier)
        entry.set(EXTENDED_DONE, "0")
    if parent_identifier is not None:
        entry.set(EXTENDED_PARENT_IDENTIFIER, parent_identifier)
    if done is not None:
        entry.set(EXTENDED_DONE, "1" if done else "0")
    write_root(part, root)


def plan_reply_comment(editing: DocxEditing, operation: dict, location: str) -> Change:
    parent = find_comment(editing, operation["comment"], location)
    author = comment_author(editing, operation, location)

    def change() -> str:
        root = thread_root(editing, parent)
        reply = editing.document.comments.add_comment(text=operation["text"], author=author)
        reply_element = reply._comment_elm
        set_extended_entry(editing, root)
        set_extended_entry(editing, reply_element, parent_identifier=ensure_paragraph_identifier(editing.document, root))
        mark_reply_range(editing.document.element.body, root.get(qn("w:id")), reply_element.get(qn("w:id")))
        return f"replied to comment {root.get(qn('w:id'))} with comment {reply_element.get(qn('w:id'))}"
    return change


def mark_reply_range(body, root_identifier: str, reply_identifier: str) -> None:
    start = next((marker for marker in body.iter(qn("w:commentRangeStart")) if marker.get(qn("w:id")) == root_identifier), None)
    end = next((marker for marker in body.iter(qn("w:commentRangeEnd")) if marker.get(qn("w:id")) == root_identifier), None)
    if start is None or end is None:
        return
    start.addnext(OxmlElement("w:commentRangeStart", attrs={qn("w:id"): reply_identifier}))
    reference_run = end.getnext() if end.getnext() is not None and end.getnext().find(qn("w:commentReference")) is not None else end
    reference_run.addnext(reference_run_for(reply_identifier))
    reference_run.addnext(OxmlElement("w:commentRangeEnd", attrs={qn("w:id"): reply_identifier}))


def reference_run_for(identifier: str):
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    properties.append(OxmlElement("w:rStyle", attrs={qn("w:val"): "CommentReference"}))
    run.append(properties)
    run.append(OxmlElement("w:commentReference", attrs={qn("w:id"): identifier}))
    return run


def plan_resolve_comment(editing: DocxEditing, operation: dict, location: str) -> Change:
    comment = find_comment(editing, operation["comment"], location)
    resolved = operation.get("resolved", True)

    def change() -> str:
        root = thread_root(editing, comment)
        set_extended_entry(editing, root, done=resolved)
        state = "resolved" if resolved else "reopened"
        return f"{state} the thread of comment {root.get(qn('w:id'))}"
    return change


def plan_delete_comment(editing: DocxEditing, operation: dict, location: str) -> Change:
    comment = find_comment(editing, operation["comment"], location)

    def change() -> str:
        doomed = [comment] + replies_of(editing, comment)
        for target in doomed:
            delete_one_comment(editing, target)
        return f"deleted comment {operation['comment']}" + (f" and {len(doomed) - 1} replies" if len(doomed) > 1 else "")
    return change


def replies_of(editing: DocxEditing, comment) -> list:
    paragraph_identifier = comment_paragraph_identifier(comment)
    if paragraph_identifier is None:
        return []
    infos = thread_infos(editing.document)
    comments = comments_element(editing.document)
    return [candidate for candidate in comments.iterchildren(qn("w:comment")) if infos.get(comment_paragraph_identifier(candidate), CommentThreadInfo(None, False)).parent == paragraph_identifier]


def delete_one_comment(editing: DocxEditing, comment) -> None:
    identifier = comment.get(qn("w:id"))
    for marker in list(editing.document.element.body.iter(*COMMENT_MARKER_TAGS)):
        if marker.get(qn("w:id")) == identifier:
            remove_marker(marker)
    remove_extended_entry(editing, comment_paragraph_identifier(comment))
    comment.getparent().remove(comment)


def remove_marker(marker) -> None:
    parent = marker.getparent()
    parent.remove(marker)
    if parent.tag == RUN_TAG and all(child.tag == qn("w:rPr") for child in parent):
        parent.getparent().remove(parent)


def remove_extended_entry(editing: DocxEditing, paragraph_identifier: str | None) -> None:
    part = extended_part(editing.document, create=False)
    if part is None or paragraph_identifier is None:
        return
    root = read_root(part)
    for entry in list(root.iter(COMMENT_EXTENDED_TAG)):
        if entry.get(EXTENDED_PARAGRAPH_IDENTIFIER) == paragraph_identifier:
            root.remove(entry)
    write_root(part, root)
