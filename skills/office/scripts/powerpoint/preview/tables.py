from __future__ import annotations

from pptx.oxml.ns import qn

from core.office_theme import OFFICE_THEME
from core.units import EMU_PER_POINT
from powerpoint.preview.paint import FILL_TAGS, element, paint_color
from powerpoint.preview.text import TextPaint, body_html, body_layout
from powerpoint.model.style import TRUE_VALUES, theme_slot_color
from powerpoint.model.table_style_properties import part_flags, style_of
from powerpoint.model.table_styles import DEFAULT_TABLE_STYLE, GRID_FAMILY, MEDIUM_FAMILY


BANDED_TINT = 0.8
PLAIN_TINT = 0.9
CELL_BORDER = "1px solid #FFFFFF"
HEADER_TEXT_COLOR = "#FFFFFF"
TRANSPARENT = "transparent"
BORDER_SIDES = (("left", "a:lnL"), ("right", "a:lnR"), ("top", "a:lnT"), ("bottom", "a:lnB"))


def table_html(context, frame_element, width: float, height: float, faces: set) -> str:
    table = frame_element.find(f"{qn('a:graphic')}/{qn('a:graphicData')}/{qn('a:tbl')}")
    columns = [int(column.get("w")) for column in table.find(qn("a:tblGrid")).findall(qn("a:gridCol"))]
    rows = table.findall(qn("a:tr"))
    heights = [int(row.get("h")) for row in rows]
    width_scale = width / (sum(columns) or 1)
    height_scale = height / (sum(heights) or 1)
    style = table_style(context, table.find(qn("a:tblPr")), len(rows), len(columns))
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
            cells.append(cell_html(context, frame_element, cell, place, style, (row_index, column_index), faces, width_scale))
    return "".join(cells)


def table_style(context, properties, row_count: int, column_count: int) -> dict:
    style = style_of(properties) or DEFAULT_TABLE_STYLE
    color = "#" + (theme_slot_color(context, style.color_slot) or OFFICE_THEME[style.color_slot]).lstrip("#")
    return {"family": style.family, "color": color, "last": (row_count - 1, column_count - 1), **part_flags(properties)}


def is_emphasized(style: dict, row_index: int, column_index: int) -> bool:
    last_row, last_column = style["last"]
    return (
        style["firstRow"] and row_index == 0
        or style["lastRow"] and row_index == last_row
        or style["firstCol"] and column_index == 0
        or style["lastCol"] and column_index == last_column
    )


def default_fill(style: dict, row_index: int, column_index: int) -> str:
    if style["family"] != MEDIUM_FAMILY:
        return TRANSPARENT
    if is_emphasized(style, row_index, column_index):
        return style["color"]
    banded_row = row_index - (1 if style["firstRow"] else 0)
    banded_column = column_index - (1 if style["firstCol"] else 0)
    banded = style["bandRow"] and banded_row % 2 == 0 or style["bandCol"] and banded_column % 2 == 0
    return mixed_with_white(style["color"], BANDED_TINT if banded else PLAIN_TINT)


def default_border(style: dict) -> str:
    if style["family"] == MEDIUM_FAMILY:
        return CELL_BORDER
    if style["family"] == GRID_FAMILY:
        return f"1px solid {style['color']}"
    return "none"


def mixed_with_white(color: str, amount: float) -> str:
    channels = [int(color.lstrip("#")[index:index + 2], 16) for index in (0, 2, 4)]
    return "#" + "".join(f"{round(channel + (255 - channel) * amount):02X}" for channel in channels)


def cell_html(context, frame_element, cell, place: tuple, style: dict, position: tuple[int, int], faces: set, pixels_per_emu: float) -> str:
    properties = cell.find(qn("a:tcPr"))
    own_fill = next((child for child in properties if child.tag in FILL_TAGS), None) if properties is not None else None
    fill = paint_color(context, own_fill) if own_fill is not None else default_fill(style, *position)
    emphasized = is_emphasized(style, *position)
    header_color = HEADER_TEXT_COLOR if emphasized and style["family"] == MEDIUM_FAMILY else None
    paint = TextPaint(context, frame_element, faces, header_color, emphasized)
    body = cell.find(qn("a:txBody"))
    content = body_html(paint, body, body_layout(context, frame_element, body, [], properties)) if body is not None else ""
    box = {
        "position": "absolute",
        "left": f"{place[0]:.2f}px",
        "top": f"{place[1]:.2f}px",
        "width": f"{place[2]:.2f}px",
        "height": f"{place[3]:.2f}px",
        "box-sizing": "border-box",
        **cell_borders(context, properties, pixels_per_emu, default_border(style)),
        "background-color": fill,
    }
    return element("div", box, content)


def cell_borders(context, properties, pixels_per_emu: float, fallback: str) -> dict:
    sides = {f"border-{side}": cell_border(context, properties.find(qn(tag)) if properties is not None else None, pixels_per_emu, fallback) for side, tag in BORDER_SIDES}
    values = set(sides.values())
    return {"border": values.pop()} if len(values) == 1 else sides


def cell_border(context, line, pixels_per_emu: float, fallback: str) -> str:
    if line is None:
        return fallback
    fill = next((child for child in line if child.tag in FILL_TAGS), None)
    if fill is None or fill.tag == qn("a:noFill"):
        return "none"
    return f"{max(1.0, int(line.get('w', EMU_PER_POINT)) * pixels_per_emu):.2f}px solid {paint_color(context, fill)}"
