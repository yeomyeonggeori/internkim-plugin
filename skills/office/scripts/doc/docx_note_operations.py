from __future__ import annotations

from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from docx_editing import DocxEditing
from docx_parts import read_root, related_part, write_root
from docx_reference_operations import NOTE_KINDS
from docx_text import RUN_TAG
from office_operations import TARGET_NOT_FOUND, Change
from office_result import OfficeFailure


def note_part_and_element(editing: DocxEditing, operation: dict, location: str):
    kind = operation["kind"]
    part = related_part(editing.document, getattr(RELATIONSHIP_TYPE, NOTE_KINDS[kind][0].upper()))
    root = read_root(part) if part is not None else None
    notes = [] if root is None else [note for note in root.iter(qn(f"w:{kind}")) if note.get(qn("w:type")) is None]
    note = next((note for note in notes if int(note.get(qn("w:id"))) == operation["note"]), None)
    if note is None:
        listed = ", ".join(note.get(qn("w:id")) for note in notes) or "none"
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.note: the document has no {kind} {operation['note']}; it has {listed}", f"{location}.note", suggestion="doc read lists notes with their kind and id"))
    return part, root, note


def plan_edit_note(editing: DocxEditing, operation: dict, location: str) -> Change:
    note_part_and_element(editing, operation, location)

    def change() -> str:
        part, root, note = note_part_and_element(editing, operation, location)
        paragraphs = note.findall(qn("w:p"))
        for paragraph in paragraphs[1:]:
            note.remove(paragraph)
        first = paragraphs[0]
        for run in [run for run in first.iter(RUN_TAG) if not is_note_mark(run)]:
            run.getparent().remove(run)
        text_run = OxmlElement("w:r")
        text = OxmlElement("w:t", attrs={qn("xml:space"): "preserve"})
        text.text = f" {operation['text']}"
        text_run.append(text)
        first.append(text_run)
        write_root(part, root)
        return f"rewrote {operation['kind']} {operation['note']}"
    return change


def is_note_mark(run) -> bool:
    return run.find(qn("w:footnoteRef")) is not None or run.find(qn("w:endnoteRef")) is not None


def plan_delete_note(editing: DocxEditing, operation: dict, location: str) -> Change:
    note_part_and_element(editing, operation, location)
    kind = operation["kind"]

    def change() -> str:
        part, root, note = note_part_and_element(editing, operation, location)
        note.getparent().remove(note)
        write_root(part, root)
        references = [reference for reference in editing.document.element.body.iter(qn(f"w:{kind}Reference")) if int(reference.get(qn("w:id"))) == operation["note"]]
        for reference in references:
            run = reference.getparent()
            run.remove(reference)
            if all(child.tag == qn("w:rPr") for child in run):
                run.getparent().remove(run)
        return f"deleted {kind} {operation['note']} and its mark"
    return change
