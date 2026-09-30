import re

from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run


PARAGRAPH_TAG = qn("w:p")
TABLE_TAG = qn("w:tbl")
CONTENT_CONTROL_TAG = qn("w:sdt")
HEADING_STYLE_PATTERN = re.compile(r"^Heading (\d)$")


def body_block_elements(document) -> list:
    return [child for child in document.element.body.iterchildren() if child.tag in (PARAGRAPH_TAG, TABLE_TAG, CONTENT_CONTROL_TAG)]


def wrap_block(element, document):
    if element.tag == PARAGRAPH_TAG:
        return Paragraph(element, document._body)
    if element.tag == TABLE_TAG:
        return Table(element, document._body)
    return element


def block_kind(element, document) -> str:
    if element.tag == TABLE_TAG:
        return "table"
    if element.tag == CONTENT_CONTROL_TAG:
        return "contentControl"
    paragraph = Paragraph(element, document._body)
    if heading_level(paragraph) is not None:
        return "heading"
    if is_list_item(paragraph):
        return "listItem"
    return "paragraph"


def heading_level(paragraph: Paragraph) -> int | None:
    style_name = paragraph.style.name if paragraph.style is not None else ""
    if style_name == "Title":
        return 0
    match = HEADING_STYLE_PATTERN.match(style_name)
    return int(match.group(1)) if match else None


def is_list_item(paragraph: Paragraph) -> bool:
    style_name = paragraph.style.name if paragraph.style is not None else ""
    return style_name.startswith("List") or paragraph._p.pPr is not None and paragraph._p.pPr.numPr is not None


def element_text(element) -> str:
    return "".join(node.text or "" for node in element.iter(qn("w:t")))


def paragraph_runs(paragraph: Paragraph) -> list[Run]:
    return [Run(run_element, paragraph) for run_element in paragraph._p.xpath("./w:r | ./w:hyperlink/w:r")]


def table_cell_texts(table: Table) -> list[list[str]]:
    return [[cell.text for cell in row.cells] for row in table.rows]


def has_page_break(paragraph: Paragraph) -> bool:
    return any(node.get(qn("w:type")) == "page" for node in paragraph._p.iter(qn("w:br")))
