from __future__ import annotations

from core.css_color import parse_css_color
from deck.pptx_export.text import TextContext, color_xml, paragraph_xml


TABLE_URI = "http://schemas.openxmlformats.org/drawingml/2006/table"
BORDER_TAGS = (("left", "a:lnL"), ("right", "a:lnR"), ("top", "a:lnT"), ("bottom", "a:lnB"))


def table_count(slides: list[dict]) -> int:
    return sum(len(slide.get("tables", [])) for slide in slides)


def cell_blocks(blocks: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for block in blocks:
        if block.get("cell"):
            grouped.setdefault(block["cell"], []).append(block)
    return grouped


def table_frames_xml(tables: list[dict], blocks: dict[str, list[dict]], first_shape_id: int, context: TextContext) -> str:
    return "".join(table_frame_xml(shape_id, table, blocks, context) for shape_id, table in enumerate(tables, start=first_shape_id))


def table_frame_xml(shape_id: int, table: dict, blocks: dict[str, list[dict]], context: TextContext) -> str:
    scale, box = context.scale, table["box"]
    grid = "".join(f'<a:gridCol w="{scale.x(width)}"/>' for width in table["columnWidthsPx"])
    rows = "".join(row_xml(row, blocks, context) for row in table["rows"])
    return (
        f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="Table {shape_id}"/>'
        '<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
        f'<p:xfrm><a:off x="{scale.x(box["left"])}" y="{scale.y(box["top"])}"/><a:ext cx="{scale.x(box["right"] - box["left"])}" cy="{scale.y(box["bottom"] - box["top"])}"/></p:xfrm>'
        f'<a:graphic><a:graphicData uri="{TABLE_URI}"><a:tbl><a:tblPr firstRow="0" bandRow="0"/><a:tblGrid>{grid}</a:tblGrid>{rows}</a:tbl></a:graphicData></a:graphic>'
        "</p:graphicFrame>"
    )


def row_xml(row: dict, blocks: dict[str, list[dict]], context: TextContext) -> str:
    cells = "".join(cell_xml(cell, blocks.get(cell["address"], []), context) for cell in row["cells"])
    return f'<a:tr h="{context.scale.y(row["heightPx"])}">{cells}</a:tr>'


def cell_xml(cell: dict, blocks: list[dict], context: TextContext) -> str:
    paragraphs = "".join(paragraph_xml(paragraph, block, context) for block in blocks for paragraph in block["paragraphs"])
    body = paragraphs or f'<a:p><a:endParaRPr lang="{context.language}"/></a:p>'
    return f"<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{body}</a:txBody>{cell_properties_xml(cell, context)}</a:tc>"


def cell_properties_xml(cell: dict, context: TextContext) -> str:
    scale, insets = context.scale, cell["insets"]
    margins = f'marL="{scale.x(insets["left"])}" marR="{scale.x(insets["right"])}" marT="{scale.y(insets["top"])}" marB="{scale.y(insets["bottom"])}"'
    borders = "".join(border_xml(tag, cell["borders"][side], context) for side, tag in BORDER_TAGS)
    fill = f'<a:solidFill>{color_xml(parse_css_color(cell["fill"]), 1.0)}</a:solidFill>' if cell["fill"] else "<a:noFill/>"
    return f'<a:tcPr {margins} anchor="{cell["anchor"]}">{borders}{fill}</a:tcPr>'


def border_xml(tag: str, border: dict | None, context: TextContext) -> str:
    if border is None:
        return f'<{tag} w="0"><a:noFill/></{tag}>'
    width = context.scale.x(border["widthPx"])
    return f'<{tag} w="{width}" cap="flat" cmpd="sng" algn="ctr"><a:solidFill>{color_xml(parse_css_color(border["color"]), 1.0)}</a:solidFill><a:prstDash val="solid"/></{tag}>'
