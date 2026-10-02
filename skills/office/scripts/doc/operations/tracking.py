from __future__ import annotations

import copy
from dataclasses import dataclass, field
import datetime
import difflib
import re

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from doc.model.text import PARAGRAPH_TAG, live_runs, run_text


DEFAULT_TRACKING_AUTHOR = "AI Assistant"
TOKEN_PATTERN = re.compile(r"\s+|\w+|[^\w\s]", re.UNICODE)
PARAGRAPH_PROPERTIES_AFTER_RUN_PROPERTIES = (qn("w:sectPr"), qn("w:pPrChange"))
PARAGRAPH_PROPERTY_CHANGE_EXCLUDED = (qn("w:rPr"), qn("w:sectPr"), qn("w:pPrChange"))


@dataclass
class Tracking:
    author: str
    date: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    next_identifier: int = 1

    def mark(self, tag: str):
        element = OxmlElement(tag)
        element.set(qn("w:id"), str(self.next_identifier))
        element.set(qn("w:author"), self.author)
        element.set(qn("w:date"), self.date)
        self.next_identifier += 1
        return element


def start_tracking(author: str, document_element) -> Tracking:
    identifiers = [int(value) for value in document_element.xpath("//@w:id") if str(value).lstrip("-").isdigit()]
    return Tracking(author=author, next_identifier=max(identifiers, default=0) + 1)


def tracked_replace(paragraph, start: int, end: int, replacement: str, tracking: Tracking) -> None:
    split_runs_at(paragraph, (start, end))
    covered = runs_between(paragraph, start, end)
    style_source = covered[0] if covered else neighbouring_run(paragraph, start)
    deletion = mark_runs_deleted(covered, tracking)
    if not replacement:
        return
    insertion = inserted_run(style_source, replacement, tracking)
    place_insertion(paragraph, insertion, deletion, start)


def tracked_set_text(paragraph, new_text: str, tracking: Tracking) -> None:
    old_tokens = TOKEN_PATTERN.findall(paragraph_live_text(paragraph))
    new_tokens = TOKEN_PATTERN.findall(new_text)
    matcher = difflib.SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
    old_offsets = token_offsets(old_tokens)
    edits = [
        (old_offsets[first_old], old_offsets[last_old], "".join(new_tokens[first_new:last_new]))
        for tag, first_old, last_old, first_new, last_new in matcher.get_opcodes()
        if tag != "equal"
    ]
    for start, end, replacement in reversed(edits):
        tracked_replace(paragraph, start, end, replacement, tracking)


def token_offsets(tokens: list[str]) -> list[int]:
    offsets = [0]
    for token in tokens:
        offsets.append(offsets[-1] + len(token))
    return offsets


def paragraph_live_text(paragraph) -> str:
    return "".join(run_text(run) for run in live_runs(paragraph))


def split_runs_at(paragraph, positions: tuple[int, ...]) -> None:
    for position in positions:
        offset = 0
        for run in live_runs(paragraph):
            text = run_text(run)
            if offset < position < offset + len(text):
                split_run(run, position - offset)
                break
            offset += len(text)


def split_run(run, at: int) -> None:
    text = run_text(run)
    second = copy.deepcopy(run)
    run.text = text[:at]
    second.text = text[at:]
    run.addnext(second)


def runs_between(paragraph, start: int, end: int) -> list:
    covered = []
    offset = 0
    for run in live_runs(paragraph):
        length = len(run_text(run))
        if start <= offset and offset + length <= end and length > 0 and start < end:
            covered.append(run)
        offset += length
    return covered


def neighbouring_run(paragraph, position: int):
    offset = 0
    previous = None
    for run in live_runs(paragraph):
        if offset >= position and previous is not None:
            return previous
        if offset >= position:
            return run
        previous = run
        offset += len(run_text(run))
    return previous


def mark_runs_deleted(runs: list, tracking: Tracking):
    last_container = None
    for run in runs:
        if run.getparent().tag == qn("w:ins"):
            container = run.getparent()
            container.remove(run)
            if len(container) == 0:
                container.getparent().remove(container)
            continue
        last_container = wrap_deleted(run, last_container, tracking)
    return last_container


def wrap_deleted(run, previous_container, tracking: Tracking):
    for text in run.iter(qn("w:t")):
        text.tag = qn("w:delText")
    for instruction in run.iter(qn("w:instrText")):
        instruction.tag = qn("w:delInstrText")
    if previous_container is not None and run.getprevious() is previous_container:
        previous_container.append(run)
        return previous_container
    container = tracking.mark("w:del")
    run.addprevious(container)
    container.append(run)
    return container


def inserted_run(style_source, text: str, tracking: Tracking):
    run = OxmlElement("w:r")
    properties = style_source.find(qn("w:rPr")) if style_source is not None else None
    if properties is not None:
        run.append(without_property_change(properties))
    run.text = text
    container = tracking.mark("w:ins")
    container.append(run)
    return container


def without_property_change(properties):
    duplicate = copy.deepcopy(properties)
    for change in duplicate.findall(qn("w:rPrChange")):
        duplicate.remove(change)
    return duplicate


def place_insertion(paragraph, insertion, deletion, position: int) -> None:
    if deletion is not None:
        deletion.addnext(insertion)
        return
    offset = 0
    for run in live_runs(paragraph):
        if offset == position:
            outermost_inline(run, paragraph).addprevious(insertion)
            return
        offset += len(run_text(run))
    paragraph.append(insertion)


def outermost_inline(run, paragraph):
    current = run
    while current.getparent() is not paragraph and current.getparent().tag == qn("w:ins"):
        current = current.getparent()
    return current


def mark_paragraph_inserted(paragraph, tracking: Tracking) -> None:
    wrap_live_runs(paragraph, tracking, "w:ins")
    paragraph_mark_properties(paragraph).insert(0, tracking.mark("w:ins"))


def mark_paragraph_deleted(paragraph, tracking: Tracking) -> None:
    mark_runs_deleted(live_runs(paragraph), tracking)
    paragraph_mark_properties(paragraph).insert(0, tracking.mark("w:del"))


def wrap_live_runs(paragraph, tracking: Tracking, tag: str) -> None:
    for run in live_runs(paragraph):
        if run.getparent().tag == qn("w:ins"):
            continue
        container = tracking.mark(tag)
        run.addprevious(container)
        container.append(run)


def paragraph_mark_properties(paragraph):
    paragraph_properties = paragraph.find(qn("w:pPr"))
    if paragraph_properties is None:
        paragraph_properties = OxmlElement("w:pPr")
        paragraph.insert(0, paragraph_properties)
    run_properties = paragraph_properties.find(qn("w:rPr"))
    if run_properties is not None:
        return run_properties
    run_properties = OxmlElement("w:rPr")
    successor = next((child for child in paragraph_properties if child.tag in PARAGRAPH_PROPERTIES_AFTER_RUN_PROPERTIES), None)
    if successor is None:
        paragraph_properties.append(run_properties)
    else:
        successor.addprevious(run_properties)
    return run_properties


def mark_row(row, tracking: Tracking, inserted: bool) -> None:
    row_properties = row.find(qn("w:trPr"))
    if row_properties is None:
        row_properties = OxmlElement("w:trPr")
        table_row_exceptions = row.find(qn("w:tblPrEx"))
        if table_row_exceptions is None:
            row.insert(0, row_properties)
        else:
            table_row_exceptions.addnext(row_properties)
    row_properties.append(tracking.mark("w:ins" if inserted else "w:del"))
    for paragraph in row.iter(PARAGRAPH_TAG):
        if inserted:
            wrap_live_runs(paragraph, tracking, "w:ins")
        else:
            mark_runs_deleted(live_runs(paragraph), tracking)


def mark_block_deleted(element, tracking: Tracking) -> None:
    if element.tag == PARAGRAPH_TAG:
        mark_paragraph_deleted(element, tracking)
        return
    rows = list(element.iter(qn("w:tr")))
    for row in rows:
        mark_row(row, tracking, inserted=False)
    if not rows:
        for paragraph in element.iter(PARAGRAPH_TAG):
            mark_paragraph_deleted(paragraph, tracking)


def mark_block_inserted(element, tracking: Tracking) -> None:
    if element.tag == PARAGRAPH_TAG:
        mark_paragraph_inserted(element, tracking)
        return
    for row in element.iter(qn("w:tr")):
        mark_row(row, tracking, inserted=True)


def snapshot_run_properties(run):
    properties = run.find(qn("w:rPr"))
    return copy.deepcopy(properties) if properties is not None else OxmlElement("w:rPr")


def record_run_property_change(run, old_properties, tracking: Tracking) -> None:
    properties = run.find(qn("w:rPr"))
    if properties is None or properties.find(qn("w:rPrChange")) is not None:
        return
    change = tracking.mark("w:rPrChange")
    change.append(without_property_change(old_properties))
    properties.append(change)


def snapshot_paragraph_properties(paragraph):
    old = OxmlElement("w:pPr")
    properties = paragraph.find(qn("w:pPr"))
    for child in properties if properties is not None else []:
        if child.tag not in PARAGRAPH_PROPERTY_CHANGE_EXCLUDED:
            old.append(copy.deepcopy(child))
    return old


def record_paragraph_property_change(paragraph, old_properties, tracking: Tracking) -> None:
    properties = paragraph.find(qn("w:pPr"))
    if properties is None or properties.find(qn("w:pPrChange")) is not None:
        return
    change = tracking.mark("w:pPrChange")
    change.append(old_properties)
    properties.append(change)
