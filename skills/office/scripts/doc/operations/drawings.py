from __future__ import annotations

import copy
from xml.sax.saxutils import escape, quoteattr

from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches
from docx.text.paragraph import Paragraph

from doc.model.charts import next_drawing_id
from doc.operations.editing import DocxEditing, placement, resolve_paragraph
from doc.operations.formats import ALIGNMENTS, require_any
from doc.operations.tracking import mark_block_inserted
from core.office_operations import TARGET_NOT_FOUND, Change
from core.office_result import OfficeFailure
from core.units import END_TEXT_INSET_EMU, SIDE_TEXT_INSET_EMU


WRAP_ELEMENTS = {"square": '<wp:wrapSquare {namespaces} wrapText="bothSides"/>', "topAndBottom": "<wp:wrapTopAndBottom {namespaces}/>", "behindText": "<wp:wrapNone {namespaces}/>", "inFrontOfText": "<wp:wrapNone {namespaces}/>"}
WRAP_TAGS = tuple(qn(f"wp:{name}") for name in ("wrapSquare", "wrapTopAndBottom", "wrapNone", "wrapTight", "wrapThrough"))
PICTURE_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/picture"
SHAPE_NAMESPACE = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
FLOAT_SIDE_DISTANCE_EMU = 114300
FIRST_RELATIVE_HEIGHT = 251658240
IMAGE_PROPERTIES = ("widthInches", "heightInches", "description", "wrap", "align")
TEXT_BOX_LINE_INCHES = 0.28
TEXT_BOX_PADDING_INCHES = 0.2
TEXT_BOX_BORDER_COLOR = "7F7F7F"


def drawing_placement(drawing):
    return drawing.find(qn("wp:inline")) if drawing.find(qn("wp:inline")) is not None else drawing.find(qn("wp:anchor"))


def set_wrap(document, drawing, wrap: str) -> None:
    current = drawing_placement(drawing)
    if wrap == "inline":
        if current.tag == qn("wp:anchor"):
            current.addprevious(inline_from(current))
            drawing.remove(current)
        return
    if current.tag == qn("wp:inline"):
        anchor = anchor_from(current, relative_height(document))
        current.addprevious(anchor)
        drawing.remove(current)
        current = anchor
    replace_wrap(current, wrap)


def inline_from(anchor):
    inline = parse_xml(f'<wp:inline {nsdecls("wp")} distT="0" distB="0" distL="0" distR="0"/>')
    for name in ("extent", "effectExtent", "docPr", "cNvGraphicFramePr"):
        child = anchor.find(qn(f"wp:{name}"))
        if child is not None:
            inline.append(copy.deepcopy(child))
    inline.append(copy.deepcopy(anchor.find(qn("a:graphic"))))
    return inline


def anchor_from(inline, height: int):
    anchor = parse_xml(
        f'<wp:anchor {nsdecls("wp")} distT="0" distB="0" distL="{FLOAT_SIDE_DISTANCE_EMU}" distR="{FLOAT_SIDE_DISTANCE_EMU}" simplePos="0" '
        f'relativeHeight="{height}" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">'
        '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="margin"><wp:align>left</wp:align></wp:positionH>'
        '<wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV></wp:anchor>'
    )
    anchor.append(copy.deepcopy(inline.find(qn("wp:extent"))))
    effect = inline.find(qn("wp:effectExtent"))
    anchor.append(copy.deepcopy(effect) if effect is not None else parse_xml(f'<wp:effectExtent {nsdecls("wp")} l="0" t="0" r="0" b="0"/>'))
    anchor.append(parse_xml(WRAP_ELEMENTS["topAndBottom"].format(namespaces=nsdecls("wp"))))
    for name in ("docPr", "cNvGraphicFramePr"):
        child = inline.find(qn(f"wp:{name}"))
        anchor.append(copy.deepcopy(child) if child is not None else parse_xml(f'<wp:cNvGraphicFramePr {nsdecls("wp")}/>'))
    anchor.append(copy.deepcopy(inline.find(qn("a:graphic"))))
    return anchor


def relative_height(document) -> int:
    return FIRST_RELATIVE_HEIGHT + 1024 * len(document.element.body.findall(f".//{qn('wp:anchor')}"))


def replace_wrap(anchor, wrap: str) -> None:
    old = next(child for child in anchor if child.tag in WRAP_TAGS)
    old.addprevious(parse_xml(WRAP_ELEMENTS[wrap].format(namespaces=nsdecls("wp"))))
    anchor.remove(old)
    anchor.set("behindDoc", "1" if wrap == "behindText" else "0")


def horizontal_align(align: str):
    return parse_xml(f'<wp:align {nsdecls("wp")}>{"left" if align == "justify" else align}</wp:align>')


def block_pictures(paragraph_element) -> list:
    return [drawing for drawing in paragraph_element.iter(qn("w:drawing")) if drawing.find(f".//{{{PICTURE_NAMESPACE}}}pic") is not None]


def plan_set_image_properties(editing: DocxEditing, operation: dict, location: str) -> Change:
    require_any(operation, IMAGE_PROPERTIES, location)
    paragraph = resolve_paragraph(editing, operation["block"], f"{location}.block")
    pictures = block_pictures(paragraph._p)
    picture_index = operation.get("picture") or 0
    if picture_index >= len(pictures):
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.picture: block {operation['block']} holds {len(pictures)} pictures", f"{location}.picture", suggestion="office read marks the blocks that hold pictures"))
    drawing = pictures[picture_index]

    def change() -> str:
        if operation.get("widthInches") or operation.get("heightInches"):
            resize(drawing, operation.get("widthInches"), operation.get("heightInches"))
        if operation.get("description") is not None:
            drawing_placement(drawing).find(qn("wp:docPr")).set("descr", operation["description"])
        if operation.get("wrap"):
            set_wrap(editing.document, drawing, operation["wrap"])
        if operation.get("align"):
            align_drawing(paragraph, drawing, operation["align"])
        return f"changed picture {picture_index} of block {operation['block']}"
    return change


def resize(drawing, width_inches: float | None, height_inches: float | None) -> None:
    extent = drawing_placement(drawing).find(qn("wp:extent"))
    old_width, old_height = int(extent.get("cx")), int(extent.get("cy"))
    width = int(Inches(width_inches)) if width_inches else int(old_width * Inches(height_inches) / old_height)
    height = int(Inches(height_inches)) if height_inches else int(old_height * width / old_width)
    for element in (extent, *drawing.iter(qn("a:ext"))):
        element.set("cx", str(width))
        element.set("cy", str(height))


def align_drawing(paragraph: Paragraph, drawing, align: str) -> None:
    current = drawing_placement(drawing)
    if current.tag == qn("wp:inline"):
        paragraph.alignment = ALIGNMENTS[align]
        return
    position = current.find(qn("wp:positionH"))
    position.replace(position[0], horizontal_align(align))


def plan_insert_text_box(editing: DocxEditing, operation: dict, location: str) -> Change:
    place = placement(editing, operation, location)
    lines = operation["text"].split("\n")

    def change() -> str:
        width = Inches(operation.get("widthInches") or text_width_inches(editing) / 2)
        height = Inches(operation.get("heightInches") or TEXT_BOX_LINE_INCHES * len(lines) + TEXT_BOX_PADDING_INCHES)
        paragraph = parse_xml(f'<w:p {nsdecls("w")}><w:r><w:drawing/></w:r></w:p>')
        drawing = paragraph.find(f".//{qn('w:drawing')}")
        drawing.append(text_box_inline(lines, int(width), int(height), next_drawing_id(editing.document), operation))
        set_wrap(editing.document, drawing, operation.get("wrap") or "square")
        align_drawing(Paragraph(paragraph, None), drawing, operation.get("align") or "left")
        place(paragraph)
        if editing.tracking is not None:
            mark_block_inserted(paragraph, editing.tracking)
        return f"inserted a text box of {len(lines)} lines"
    return change


def text_width_inches(editing: DocxEditing) -> float:
    section = editing.document.sections[-1]
    return (section.page_width - section.left_margin - section.right_margin) / Inches(1)


def text_box_inline(lines: list[str], width: int, height: int, drawing_id: int, operation: dict):
    fill = f'<a:solidFill><a:srgbClr val="{operation["fill"].lstrip("#")}"/></a:solidFill>' if operation.get("fill") else "<a:noFill/>"
    line = f'<a:ln w="6350"><a:solidFill><a:srgbClr val="{TEXT_BOX_BORDER_COLOR}"/></a:solidFill></a:ln>' if operation.get("border", True) else "<a:ln><a:noFill/></a:ln>"
    paragraphs = "".join(f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>' for text in lines)
    return parse_xml(
        f'<wp:inline {nsdecls("wp", "a", "w")} xmlns:wps="{SHAPE_NAMESPACE}" distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{width}" cy="{height}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{drawing_id}" name={quoteattr(f"Text Box {drawing_id}")}/><wp:cNvGraphicFramePr/>'
        f'<a:graphic><a:graphicData uri="{SHAPE_NAMESPACE}"><wps:wsp><wps:cNvSpPr txBox="1"/>'
        f'<wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{width}" cy="{height}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>{fill}{line}</wps:spPr>'
        f'<wps:txbx><w:txbxContent>{paragraphs}</w:txbxContent></wps:txbx>'
        f'<wps:bodyPr rot="0" vert="horz" wrap="square" lIns="{SIDE_TEXT_INSET_EMU}" tIns="{END_TEXT_INSET_EMU}" rIns="{SIDE_TEXT_INSET_EMU}" bIns="{END_TEXT_INSET_EMU}" anchor="t"><a:spAutoFit/></wps:bodyPr>'
        "</wps:wsp></a:graphicData></a:graphic></wp:inline>"
    )
