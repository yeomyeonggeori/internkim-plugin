from __future__ import annotations

from docx.oxml.ns import qn


PARAGRAPH_TAG = qn("w:p")
RUN_TAG = qn("w:r")
TEXT_BOX_CONTENT_TAG = qn("w:txbxContent")
REMOVED_RUN_CONTAINER_TAGS = frozenset({qn("w:del"), qn("w:moveFrom")})
PAGINATION_BREAK_TYPES = ("page", "column")
RUN_CHARACTERS = {
    qn("w:tab"): "\t",
    qn("w:br"): "\n",
    qn("w:cr"): "\n",
    qn("w:noBreakHyphen"): "-",
}


def live_runs(paragraph_element) -> list:
    return [run for run in paragraph_element.iter(RUN_TAG) if run_is_live(run, paragraph_element)]


def removed_runs(paragraph_element) -> list:
    return [run for run in paragraph_element.iter(RUN_TAG) if belongs_to(run, paragraph_element) and is_removed(run, paragraph_element)]


def run_is_live(run, paragraph_element) -> bool:
    return belongs_to(run, paragraph_element) and not is_removed(run, paragraph_element)


def belongs_to(run, paragraph_element) -> bool:
    ancestor = run.getparent()
    while ancestor is not None and ancestor is not paragraph_element:
        if ancestor.tag in (PARAGRAPH_TAG, TEXT_BOX_CONTENT_TAG):
            return False
        ancestor = ancestor.getparent()
    return ancestor is paragraph_element


def is_removed(run, paragraph_element) -> bool:
    ancestor = run.getparent()
    while ancestor is not paragraph_element:
        if ancestor.tag in REMOVED_RUN_CONTAINER_TAGS:
            return True
        ancestor = ancestor.getparent()
    return False


def run_text(run) -> str:
    return "".join(run_child_text(child) for child in run.iterchildren())


def run_child_text(child) -> str:
    if child.tag in (qn("w:t"), qn("w:delText")):
        return child.text or ""
    if child.tag == qn("w:br") and child.get(qn("w:type")) in PAGINATION_BREAK_TYPES:
        return ""
    return RUN_CHARACTERS.get(child.tag, "")


def paragraph_text(paragraph_element) -> str:
    return "".join(run_text(run) for run in live_runs(paragraph_element))


def removed_text(paragraph_element) -> str:
    return "".join(run_text(run) for run in removed_runs(paragraph_element))


def visible_text(element) -> str:
    if element.tag == RUN_TAG:
        return run_text(element)
    if element.tag == PARAGRAPH_TAG:
        return paragraph_text(element)
    return "\n".join(paragraph_text(paragraph) for paragraph in element.iter(PARAGRAPH_TAG) if not inside_text_box(paragraph, element))


def inside_text_box(paragraph_element, container) -> bool:
    ancestor = paragraph_element.getparent()
    while ancestor is not None and ancestor is not container:
        if ancestor.tag == TEXT_BOX_CONTENT_TAG:
            return True
        ancestor = ancestor.getparent()
    return False
