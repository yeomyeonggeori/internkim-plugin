from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph as DocxParagraph

from docx_blocks import PARAGRAPH_TAG, TABLE_TAG, heading_level
from docx_package import open_document
from docx_text import live_runs, run_text, visible_text
from fonts.registry import MONOSPACE, font_role
from docx_charts import RELATIONSHIP_NAMESPACE, chart_references, read_specification
from markdown_charts import Chart
from markdown_blocks import Heading, Image, ListItem, Paragraph, Quote, Table, ThematicBreak


MARKDOWN_HEADING_LEVELS = 4
QUOTE_STYLES = ("Quote", "Intense Quote")
BLIP_TAG = qn("a:blip")
DOCUMENT_PROPERTIES_TAG = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"


@dataclass
class DocumentReading:
    blocks: list = field(default_factory=list)
    media: dict = field(default_factory=dict)
    media_names: dict = field(default_factory=dict)
    dropped: dict = field(default_factory=dict)

    def drop(self, kind: str, count: int = 1) -> None:
        if count:
            self.dropped[kind] = self.dropped.get(kind, 0) + count


JUSTIFICATION_ALIGNMENTS = {"left": "left", "start": "left", "center": "center", "right": "right", "end": "right"}


def table_block(element) -> Table:
    rows = list(element.iterchildren(qn("w:tr")))
    cells = [[visible_text(cell).strip() for cell in row.iterchildren(qn("w:tc"))] for row in rows]
    alignment_row = rows[1] if len(rows) > 1 else rows[0] if rows else None
    alignments = tuple(cell_alignment(cell) for cell in alignment_row.iterchildren(qn("w:tc"))) if alignment_row is not None else ()
    return Table(cells, alignments if any(alignments) else ())


def cell_alignment(cell) -> str:
    justification = cell.find(f"{qn('w:p')}/{qn('w:pPr')}/{qn('w:jc')}")
    return JUSTIFICATION_ALIGNMENTS.get(justification.get(qn("w:val")), "") if justification is not None else ""


def read_docx_blocks(path: Path, media_directory_name: str) -> DocumentReading:
    document = open_document(str(path))
    reading = DocumentReading()
    numbering = numbering_formats(document)
    for element in document.element.body.iterchildren():
        if element.tag == TABLE_TAG:
            reading.blocks.append(table_block(element))
        elif element.tag == PARAGRAPH_TAG:
            add_paragraph(reading, DocxParagraph(element, document._body), numbering, media_directory_name)
        elif element.tag == qn("w:sdt"):
            reading.blocks.extend(Paragraph(text) for text in visible_text(element).split("\n") if text.strip())
    reading.drop("comments", sum(1 for _ in document.element.body.iter(qn("w:commentRangeStart"))))
    return reading


def add_paragraph(reading: DocumentReading, paragraph: DocxParagraph, numbering: dict, media_directory_name: str) -> None:
    for image in paragraph_images(reading, paragraph, media_directory_name):
        reading.blocks.append(image)
    reading.blocks.extend(paragraph_charts(paragraph))
    text = inline_markdown(paragraph).strip()
    if not text:
        if has_bottom_border(paragraph):
            reading.blocks.append(ThematicBreak())
        return
    level = heading_level(paragraph)
    if level is not None:
        reading.blocks.append(Heading(min(max(level, 1), MARKDOWN_HEADING_LEVELS), visible_text(paragraph._p).strip()))
        return
    list_position = list_item_position(paragraph, numbering)
    if list_position is not None:
        reading.blocks.append(ListItem(*list_position, text))
        return
    style_name = paragraph.style.name if paragraph.style is not None else ""
    reading.blocks.append(Quote(text) if style_name in QUOTE_STYLES else Paragraph(text))


def has_bottom_border(paragraph: DocxParagraph) -> bool:
    properties = paragraph._p.pPr
    border = properties.find(f"{qn('w:pBdr')}/{qn('w:bottom')}") if properties is not None else None
    return border is not None and border.get(qn("w:val")) not in ("nil", "none")


def paragraph_charts(paragraph: DocxParagraph) -> list[Chart]:
    charts = []
    for reference in chart_references(paragraph._p):
        relationship_id = reference.get(f"{{{RELATIONSHIP_NAMESPACE}}}id")
        if relationship_id in paragraph.part.rels:
            charts.append(Chart(read_specification(paragraph.part.rels[relationship_id].target_part).to_dictionary()))
    return charts


def numbering_formats(document) -> dict[tuple[str, int], str]:
    try:
        numbering = document.part.numbering_part.element
    except (KeyError, NotImplementedError):
        return {}
    abstract_formats = {}
    for abstract in numbering.iterchildren(qn("w:abstractNum")):
        for level in abstract.iterchildren(qn("w:lvl")):
            number_format = level.find(qn("w:numFmt"))
            abstract_formats[(abstract.get(qn("w:abstractNumId")), int(level.get(qn("w:ilvl"))))] = number_format.get(qn("w:val")) if number_format is not None else "decimal"
    formats = {}
    for number in numbering.iterchildren(qn("w:num")):
        abstract_id = number.find(qn("w:abstractNumId")).get(qn("w:val"))
        for (abstract, level), number_format in abstract_formats.items():
            if abstract == abstract_id:
                formats[(number.get(qn("w:numId")), level)] = number_format
    return formats


def list_item_position(paragraph: DocxParagraph, numbering: dict) -> tuple[str, int] | None:
    properties = paragraph._p.pPr
    number_properties = properties.numPr if properties is not None else None
    style_name = paragraph.style.name if paragraph.style is not None else ""
    if number_properties is None or number_properties.numId is None:
        if style_name.startswith("List Number"):
            return "1.", 0
        if style_name.startswith("List Bullet"):
            return "-", 0
        return None
    level = number_properties.ilvl.val if number_properties.ilvl is not None else 0
    number_format = numbering.get((str(number_properties.numId.val), level), "bullet")
    return ("-" if number_format == "bullet" else "1."), level


def inline_markdown(paragraph: DocxParagraph) -> str:
    groups: list[tuple[str, object, str]] = []
    for run in live_runs(paragraph._p):
        text = run_text(run).replace("\t", " ")
        if not text:
            continue
        key = (emphasis(run), run.getparent() if run.getparent().tag == qn("w:hyperlink") else None)
        if groups and groups[-1][:2] == key:
            groups[-1] = (*key, groups[-1][2] + text)
        else:
            groups.append((*key, text))
    return "".join(link_wrapped(paragraph, hyperlink, emphasized(kind, text)) for kind, hyperlink, text in groups)


def emphasis(run) -> str:
    properties = run.find(qn("w:rPr"))
    if properties is None:
        return ""
    fonts = properties.find(qn("w:rFonts"))
    if fonts is not None and font_role(fonts.get(qn("w:ascii")) or "") == MONOSPACE:
        return "`"
    if is_on(properties, "w:b"):
        return "**"
    if is_on(properties, "w:i"):
        return "*"
    return ""


def emphasized(marker: str, text: str) -> str:
    return "\n".join(emphasized_line(marker, line) for line in text.split("\n"))


def emphasized_line(marker: str, text: str) -> str:
    core = text.strip()
    if not marker or not core:
        return text
    start = text.index(core)
    return f"{text[:start]}{marker}{core}{marker}{text[start + len(core):]}"


def is_on(properties, tag: str) -> bool:
    element = properties.find(qn(tag))
    return element is not None and element.get(qn("w:val")) not in ("0", "false", "off")


def link_wrapped(paragraph: DocxParagraph, hyperlink, text: str) -> str:
    if hyperlink is None:
        return text
    target = link_target(paragraph, hyperlink)
    return f"[{text}]({target})" if target else text


def link_target(paragraph: DocxParagraph, hyperlink) -> str | None:
    relationship_id = hyperlink.get(qn("r:id"))
    if relationship_id and relationship_id in paragraph.part.rels:
        return paragraph.part.rels[relationship_id].target_ref
    anchor = hyperlink.get(qn("w:anchor"))
    return f"#{anchor}" if anchor else None


def paragraph_images(reading: DocumentReading, paragraph: DocxParagraph, media_directory_name: str) -> list[Image]:
    images = []
    for blip in paragraph._p.iter(BLIP_TAG):
        relationship_id = blip.get(qn("r:embed"))
        if not relationship_id or relationship_id not in paragraph.part.rels:
            continue
        image_part = paragraph.part.rels[relationship_id].target_part
        name = reading.media_names.setdefault(str(image_part.partname), f"image{len(reading.media_names) + 1}{Path(str(image_part.partname)).suffix}")
        reading.media[name] = image_part.blob
        images.append(Image(drawing_description(blip), f"{media_directory_name}/{name}"))
    return images


def drawing_description(blip) -> str:
    current = blip
    while current is not None and current.tag != qn("w:drawing"):
        current = current.getparent()
    properties = next(current.iter(DOCUMENT_PROPERTIES_TAG), None) if current is not None else None
    return (properties.get("descr") or "") if properties is not None else ""
