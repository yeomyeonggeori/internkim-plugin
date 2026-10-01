from __future__ import annotations

from pptx.oxml.ns import qn

from pptx_preview_paint import FILL_TAGS, element, paint_color
from pptx_preview_text import TextPaint, body_html, body_layout
from pptx_style import theme_slot_color


TRUE_VALUES = ("1", "true")
BANDED_TINT = 0.8
PLAIN_TINT = 0.9
CELL_BORDER = "1px solid #FFFFFF"
HEADER_TEXT_COLOR = "#FFFFFF"


def table_html(context, frame_element, width: float, height: float, faces: set) -> str:
    table = frame_element.find(f"{qn('a:graphic')}/{qn('a:graphicData')}/{qn('a:tbl')}")
    columns = [int(column.get("w")) for column in table.find(qn("a:tblGrid")).findall(qn("a:gridCol"))]
    rows = table.findall(qn("a:tr"))
    heights = [int(row.get("h")) for row in rows]
    width_scale = width / (sum(columns) or 1)
    height_scale = height / (sum(heights) or 1)
    style = table_style(context, table.find(qn("a:tblPr")))
    cells = []
    for row_index, row in enumerate(rows):
        for column_index, cell in enumerate(row.findall(qn("a:tc"))):
            if cell.get("hMerge") in TRUE_VALUES or cell.get("vMerge") in TRUE_VALUES:
                continue
            spans = (int(cell.get("rowSpan", "1")), int(cell.get("gridSpan", "1")))
            place = (
                sum(columns[:column_index]) * width_scale,
                sum(heights[:row_index]) * height_scale,
                sum(columns[column_index:column_index + spans[1]]) * width_scale,
                sum(heights[row_index:row_index + spans[0]]) * height_scale,
            )
            cells.append(cell_html(context, frame_element, cell, place, style, row_index, faces))
    return "".join(cells)


def table_style(context, properties) -> dict:
    accent = "#" + (theme_slot_color(context, "accent1") or "4472C4").lstrip("#")
    flags = {name: properties is not None and properties.get(name) in TRUE_VALUES for name in ("firstRow", "bandRow")}
    return {"accent": accent, **flags}


def default_fill(style: dict, row_index: int) -> str:
    if style["firstRow"] and row_index == 0:
        return style["accent"]
    banded_row = row_index - (1 if style["firstRow"] else 0)
    tint = BANDED_TINT if style["bandRow"] and banded_row % 2 == 0 else PLAIN_TINT
    return mixed_with_white(style["accent"], tint)


def mixed_with_white(color: str, amount: float) -> str:
    channels = [int(color.lstrip("#")[index:index + 2], 16) for index in (0, 2, 4)]
    return "#" + "".join(f"{round(channel + (255 - channel) * amount):02X}" for channel in channels)


def cell_html(context, frame_element, cell, place: tuple, style: dict, row_index: int, faces: set) -> str:
    properties = cell.find(qn("a:tcPr"))
    own_fill = next((child for child in properties if child.tag in FILL_TAGS), None) if properties is not None else None
    fill = paint_color(context, own_fill) if own_fill is not None else default_fill(style, row_index)
    header = style["firstRow"] and row_index == 0
    paint = TextPaint(context, frame_element, faces, HEADER_TEXT_COLOR if header else None, header)
    body = cell.find(qn("a:txBody"))
    content = body_html(paint, body, body_layout(context, frame_element, body, [], properties)) if body is not None else ""
    box = {
        "position": "absolute",
        "left": f"{place[0]:.2f}px",
        "top": f"{place[1]:.2f}px",
        "width": f"{place[2]:.2f}px",
        "height": f"{place[3]:.2f}px",
        "box-sizing": "border-box",
        "border": CELL_BORDER,
        "background-color": fill,
    }
    return element("div", box, content)
