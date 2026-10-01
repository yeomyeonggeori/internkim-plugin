from __future__ import annotations

from dataclasses import dataclass

from docx.oxml.ns import qn

from doc.doc_definitions import REVISION_TYPES
from doc.docx_text import PARAGRAPH_TAG, RUN_TAG, run_text, visible_text


INSERTION, DELETION, MOVE, FORMATTING = REVISION_TYPES

RUN_CONTAINER_TYPES = {qn("w:ins"): INSERTION, qn("w:del"): DELETION, qn("w:moveTo"): MOVE, qn("w:moveFrom"): MOVE}
MARKER_TYPES = {qn("w:ins"): INSERTION, qn("w:del"): DELETION}
CELL_MARKER_TYPES = {qn("w:cellIns"): INSERTION, qn("w:cellDel"): DELETION}
PROPERTY_CHANGE_TAGS = frozenset(qn(f"w:{name}") for name in (
    "rPrChange", "pPrChange", "tblPrChange", "trPrChange", "tcPrChange", "sectPrChange", "tblGridChange", "tblPrExChange",
))
KEPT_ON_RESTORE = {
    qn("w:pPr"): frozenset({qn("w:rPr"), qn("w:sectPr")}),
    qn("w:sectPr"): frozenset({qn("w:headerReference"), qn("w:footerReference")}),
    qn("w:trPr"): frozenset({qn("w:ins"), qn("w:del")}),
    qn("w:tcPr"): frozenset({qn("w:cellIns"), qn("w:cellDel"), qn("w:cellMerge")}),
    qn("w:rPr"): frozenset({qn("w:ins"), qn("w:del"), qn("w:moveFrom"), qn("w:moveTo")}),
}
PROPERTY_NAMES = {
    "b": "bold", "i": "italic", "u": "underline", "strike": "strike", "sz": "size", "color": "color",
    "rFonts": "font", "highlight": "highlight", "jc": "alignment", "ind": "indent", "spacing": "spacing",
    "pStyle": "style", "rStyle": "style", "numPr": "list", "shd": "shading", "vertAlign": "superscript or subscript",
}
MOVE_RANGE_TAGS = tuple(qn(f"w:{name}") for name in ("moveFromRangeStart", "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd"))


@dataclass(frozen=True)
class Revision:
    identifier: str
    revision_type: str
    target: str
    element: object
    block: int | None
    text: str
    changed: tuple[str, ...] = ()

    @property
    def author(self) -> str:
        return self.element.get(qn("w:author")) or "unknown"

    @property
    def date(self) -> str | None:
        return self.element.get(qn("w:date"))

    def to_json(self) -> dict:
        description = {
            "id": self.identifier,
            "type": self.revision_type,
            "on": self.target,
            "author": self.author,
            "date": self.date,
            "block": self.block,
            "text": self.text,
        }
        if self.changed:
            description["changed"] = list(self.changed)
        return description


def collect_revisions(body, block_elements: list) -> list[Revision]:
    block_indexes = {id(element): index for index, element in enumerate(block_elements)}
    found = [revision_parts(element) for element in body.iter() if is_revision(element)]
    return [
        Revision(f"r{number}", revision_type, target, element, block_index(element, body, block_indexes), text, changed)
        for number, (element, revision_type, target, text, changed) in enumerate(found, start=1)
    ]


def is_revision(element) -> bool:
    return element.tag in PROPERTY_CHANGE_TAGS or element.tag in CELL_MARKER_TYPES or element.tag in RUN_CONTAINER_TYPES


def revision_parts(element) -> tuple:
    tag, parent_tag = element.tag, element.getparent().tag
    if tag in PROPERTY_CHANGE_TAGS:
        return element, FORMATTING, "properties", owner_text(element), changed_properties(element)
    if tag in CELL_MARKER_TYPES:
        return element, CELL_MARKER_TYPES[tag], "tableCell", visible_text(element.getparent().getparent()), ()
    if parent_tag == qn("w:rPr"):
        return element, MARKER_TYPES.get(tag, MOVE), "paragraphMark", "", ()
    if parent_tag == qn("w:trPr"):
        return element, MARKER_TYPES[tag], "tableRow", row_text(element.getparent().getparent()), ()
    return element, RUN_CONTAINER_TYPES[tag], "text", "".join(run_text(run) for run in element.iter(RUN_TAG)), ()


def row_text(row) -> str:
    return " | ".join(visible_text(cell) for cell in row.iterchildren(qn("w:tc")))


def owner_text(change) -> str:
    owner = change.getparent().getparent()
    if owner.tag == RUN_TAG:
        return run_text(owner)
    if owner.tag == PARAGRAPH_TAG:
        return visible_text(owner)
    return ""


def changed_properties(change) -> tuple[str, ...]:
    current = change.getparent()
    old = next(iter(change), None)
    old_children = {child.tag: child for child in old} if old is not None else {}
    current_children = {child.tag: child for child in current if child is not change and child.tag not in KEPT_ON_RESTORE.get(current.tag, ())}
    differing = [
        tag for tag in sorted(set(old_children) | set(current_children))
        if tag not in old_children or tag not in current_children or dict(old_children[tag].attrib) != dict(current_children[tag].attrib)
    ]
    names = [PROPERTY_NAMES.get(local_name(tag), local_name(tag)) for tag in differing]
    return tuple(dict.fromkeys(names))


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def block_index(element, body, block_indexes: dict) -> int | None:
    current = element
    while current is not None and current.getparent() is not body:
        current = current.getparent()
    return block_indexes.get(id(current)) if current is not None else None


def settle(revisions: list[Revision], accept: bool, body) -> int:
    settled = 0
    for revision in reversed(revisions):
        if not is_attached(revision.element, body):
            continue
        settle_one(revision, accept)
        settled += 1
    if not any(True for _ in body.iter(qn("w:moveFrom"), qn("w:moveTo"))):
        for marker in list(body.iter(*MOVE_RANGE_TAGS)):
            marker.getparent().remove(marker)
    return settled


def is_attached(element, body) -> bool:
    current = element
    while current is not None:
        if current is body:
            return True
        current = current.getparent()
    return False


def settle_one(revision: Revision, accept: bool) -> None:
    element = revision.element
    if revision.revision_type == FORMATTING:
        settle_property_change(element, accept)
    elif revision.target == "text":
        settle_run_container(element, keeps_content(element, accept))
    elif revision.target == "paragraphMark":
        settle_paragraph_mark(element, keeps_content(element, accept))
    else:
        settle_container_marker(element, element.getparent().getparent(), keeps_content(element, accept))


def keeps_content(element, accept: bool) -> bool:
    is_addition = element.tag in (qn("w:ins"), qn("w:moveTo"), qn("w:cellIns"))
    return accept == is_addition


def settle_run_container(container, keep: bool) -> None:
    parent = container.getparent()
    if not keep:
        parent.remove(container)
        return
    for deleted_text in list(container.iter(qn("w:delText"), qn("w:delInstrText"))):
        deleted_text.tag = qn("w:t") if deleted_text.tag == qn("w:delText") else qn("w:instrText")
    for child in list(container):
        container.addprevious(child)
    parent.remove(container)


def settle_paragraph_mark(marker, keep: bool) -> None:
    run_properties = marker.getparent()
    paragraph_properties = run_properties.getparent()
    paragraph = paragraph_properties.getparent()
    run_properties.remove(marker)
    if len(run_properties) == 0:
        paragraph_properties.remove(run_properties)
    if not keep:
        merge_with_next_paragraph(paragraph)


def settle_container_marker(marker, container, keep: bool) -> None:
    marker.getparent().remove(marker)
    if keep:
        return
    parent = container.getparent()
    parent.remove(container)
    if parent.tag == qn("w:tbl") and next(parent.iterchildren(qn("w:tr")), None) is None:
        parent.getparent().remove(parent)


def merge_with_next_paragraph(paragraph) -> None:
    following = paragraph.getnext()
    if following is None or following.tag != PARAGRAPH_TAG:
        remove_if_empty(paragraph, following)
        return
    content = [child for child in paragraph if child.tag != qn("w:pPr")]
    anchor = following.find(qn("w:pPr"))
    for child in reversed(content):
        if anchor is None:
            following.insert(0, child)
        else:
            anchor.addnext(child)
    paragraph.getparent().remove(paragraph)


def remove_if_empty(paragraph, following) -> None:
    if next(paragraph.iter(RUN_TAG), None) is not None:
        return
    is_last_after_table = (following is None or following.tag == qn("w:sectPr")) and (paragraph.getprevious() is None or paragraph.getprevious().tag != PARAGRAPH_TAG)
    if not is_last_after_table:
        paragraph.getparent().remove(paragraph)


def settle_property_change(change, accept: bool) -> None:
    properties = change.getparent()
    properties.remove(change)
    if accept:
        return
    old = next(iter(change), None)
    kept = KEPT_ON_RESTORE.get(properties.tag, frozenset())
    for child in list(properties):
        if child.tag not in kept:
            properties.remove(child)
    leading = sum(1 for child in properties if child.tag in kept and properties.tag == qn("w:rPr"))
    for offset, child in enumerate(list(old) if old is not None else []):
        properties.insert(leading + offset, child)


def describe_pending(revisions: list[Revision]) -> str:
    if not revisions:
        return "the document has no tracked changes"
    authors = tally(revision.author for revision in revisions)
    types = tally(revision.revision_type for revision in revisions)
    return f"{len(revisions)} pending: authors {authors}; types {types}; ids r1-r{len(revisions)}"


def tally(values) -> str:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return ", ".join(f"{value} ({count})" for value, count in counts.items())
