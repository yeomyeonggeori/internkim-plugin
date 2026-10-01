from __future__ import annotations

from pathlib import Path

from core.office_result import Issue
from doc.doc_definitions import HEADING_STRANDED
from doc.docx_blocks import body_block_elements, element_text
from doc.docx_layout import Layout
from doc.docx_pagination import Paginator, stranded_headings
from doc.docx_preview import DocxModelBuilder
from fonts.preview import FontRegistry


def stranded_heading_issues(document_path: str) -> list[Issue]:
    builder = DocxModelBuilder(Path(document_path))
    pages = Paginator(Layout(FontRegistry())).paginate(builder.sections())
    body = body_block_elements(builder.document)
    return [stranded_heading_issue(page_number, layout.block.source, body) for page_number, layout in stranded_headings(pages)]


def stranded_heading_issue(page_number: int, heading, body: list) -> Issue:
    message = f"heading {element_text(heading)!r} is the last line of page {page_number}, and the text under it starts page {page_number + 1}"
    index = next((index for index, element in enumerate(body) if element is heading), None)
    if index is None:
        return HEADING_STRANDED.issue(message, f"page {page_number}", "the heading sits inside a content control no block operation reaches; turn on keep with next for it in Word")
    return HEADING_STRANDED.issue(message, f"block {index}", fix=[{"op": "set_paragraph_format", "block": index, "keepWithNext": True}])
