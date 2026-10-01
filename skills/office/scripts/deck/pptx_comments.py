from __future__ import annotations

from datetime import datetime

from lxml import etree
from pptx.opc.constants import CONTENT_TYPE, RELATIONSHIP_TYPE
from pptx.opc.package import Part
from pptx.opc.packuri import PackURI
from pptx.oxml.ns import qn

from office_operations import Change
from pptx_targets import PptxEditing, resolve_slide


DEFAULT_AUTHOR = "InternKim"
EMU_PER_COMMENT_UNIT = 914400 / 576
AUTHORS_PART_NAME = "/ppt/commentAuthors.xml"
PRESENTATION_NAMESPACE = "http://schemas.openxmlformats.org/presentationml/2006/main"


def related_part(part, relationship_type: str):
    return next((relationship.target_part for relationship in part.rels.values() if relationship.reltype == relationship_type and not relationship.is_external), None)


def part_element(part):
    return etree.fromstring(part.blob)


def store_element(part, element) -> None:
    part._blob = etree.tostring(element, xml_declaration=True, encoding="UTF-8", standalone=True)


def new_part(editing: PptxEditing, partname: str, content_type: str, root_tag: str) -> Part:
    element = etree.Element(qn(root_tag), nsmap={"p": PRESENTATION_NAMESPACE})
    part = Part(PackURI(partname), content_type, editing.presentation.part.package)
    store_element(part, element)
    return part


def authors_part(editing: PptxEditing) -> Part:
    presentation_part = editing.presentation.part
    existing = related_part(presentation_part, RELATIONSHIP_TYPE.COMMENT_AUTHORS)
    if existing is not None:
        return existing
    part = new_part(editing, AUTHORS_PART_NAME, CONTENT_TYPE.PML_COMMENT_AUTHORS, "p:cmAuthorLst")
    presentation_part.relate_to(part, RELATIONSHIP_TYPE.COMMENT_AUTHORS)
    return part


def comments_part(editing: PptxEditing, slide) -> Part:
    existing = related_part(slide.part, RELATIONSHIP_TYPE.COMMENTS)
    if existing is not None:
        return existing
    partname = editing.presentation.part.package.next_partname("/ppt/comments/comment%d.xml")
    part = new_part(editing, partname, CONTENT_TYPE.PML_COMMENTS, "p:cmLst")
    slide.part.relate_to(part, RELATIONSHIP_TYPE.COMMENTS)
    return part


def initials_of(name: str) -> str:
    return "".join(word[0] for word in name.split()).upper()[:4] or name[:1]


def next_comment_index(authors, name: str) -> tuple[str, int]:
    author = next((entry for entry in authors.findall(qn("p:cmAuthor")) if entry.get("name") == name), None)
    if author is None:
        identifiers = [int(entry.get("id")) for entry in authors.findall(qn("p:cmAuthor"))]
        author = etree.SubElement(authors, qn("p:cmAuthor"), id=str(max(identifiers, default=-1) + 1), name=name, initials=initials_of(name), lastIdx="0", clrIdx=str(len(identifiers)))
    index = int(author.get("lastIdx", "0")) + 1
    author.set("lastIdx", str(index))
    return author.get("id"), index


def plan_add_comment(editing: PptxEditing, operation: dict, location: str) -> Change:
    slide = resolve_slide(editing, operation["slide"], f"{location}.slide")
    author_name = operation.get("author", DEFAULT_AUTHOR)

    def change() -> str:
        authors_owner = authors_part(editing)
        authors = part_element(authors_owner)
        author_id, index = next_comment_index(authors, author_name)
        store_element(authors_owner, authors)
        comments_owner = comments_part(editing, slide)
        comments = part_element(comments_owner)
        comment = etree.SubElement(comments, qn("p:cm"), authorId=author_id, dt=datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000"), idx=str(index))
        x, y = (round(operation.get(name, 0) / EMU_PER_COMMENT_UNIT) for name in ("x", "y"))
        etree.SubElement(comment, qn("p:pos"), x=str(x), y=str(y))
        etree.SubElement(comment, qn("p:text")).text = operation["text"]
        store_element(comments_owner, comments)
        return f"added a comment by {author_name} to slide {operation['slide']}"
    return change


def slide_comments(slide) -> list[dict]:
    part = related_part(slide.part, RELATIONSHIP_TYPE.COMMENTS)
    if part is None:
        return []
    authors_owner = related_part(slide.part.package.presentation_part, RELATIONSHIP_TYPE.COMMENT_AUTHORS)
    names = {entry.get("id"): entry.get("name") for entry in part_element(authors_owner).findall(qn("p:cmAuthor"))} if authors_owner is not None else {}
    return [
        {"author": names.get(comment.get("authorId"), ""), "text": comment.findtext(qn("p:text"), default="")}
        for comment in part_element(part).findall(qn("p:cm"))
    ]


COMMENT_PLANNERS = {
    "add_comment": plan_add_comment,
}
