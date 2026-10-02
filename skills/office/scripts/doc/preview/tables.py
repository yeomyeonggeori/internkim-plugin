from __future__ import annotations

from dataclasses import dataclass, field

from docx.oxml.ns import qn

from doc.preview.css import hex_color
from doc.preview.model import CellBlock, RowBlock, TableBlock
from doc.preview.styles import attribute, border_set, merged, number, paragraph_properties, run_properties
from core.units import twips_to_pixels


DEFAULT_CELL_MARGINS_TWIPS = {"top": 0, "left": 108, "bottom": 0, "right": 108}
DEFAULT_LOOK = {"firstRow": True, "lastRow": False, "firstColumn": True, "lastColumn": False, "noHBand": False, "noVBand": True}
LOOK_BITS = {"firstRow": 0x0020, "lastRow": 0x0040, "firstColumn": 0x0080, "lastColumn": 0x0100, "noHBand": 0x0200, "noVBand": 0x0400}
VERTICAL_ALIGNMENTS = ("top", "center", "bottom")
DEFAULT_COLUMN_TWIPS = 1440


@dataclass
class TableLayers:
    paragraph: dict = field(default_factory=dict)
    run: dict = field(default_factory=dict)


@dataclass
class Condition:
    paragraph: dict = field(default_factory=dict)
    run: dict = field(default_factory=dict)
    shading: str | None = None
    borders: dict = field(default_factory=dict)


@dataclass
class TableStyle:
    whole: Condition
    conditions: dict
    borders: dict
    margins: dict


def table_style(chain: list) -> TableStyle:
    whole = Condition()
    conditions: dict[str, Condition] = {}
    borders: dict = {}
    margins = dict(DEFAULT_CELL_MARGINS_TWIPS)
    for style in chain:
        whole.paragraph = merged(whole.paragraph, paragraph_properties(style.find(qn("w:pPr"))))
        whole.run = merged(whole.run, run_properties(style.find(qn("w:rPr"))))
        properties = style.find(qn("w:tblPr"))
        borders = merged(borders, border_set(properties.find(qn("w:tblBorders"))) or {}) if properties is not None else borders
        margins.update(cell_margins(properties.find(qn("w:tblCellMar")) if properties is not None else None))
        shading = attribute(style.find(qn("w:tcPr")), "w:shd", "w:fill")
        whole.shading = hex_color(shading) or whole.shading
        for conditional in style.findall(qn("w:tblStylePr")):
            conditions[conditional.get(qn("w:type"))] = merged_condition(conditions.get(conditional.get(qn("w:type"))), conditional)
    return TableStyle(whole, conditions, borders, margins)


def merged_condition(previous: Condition | None, element) -> Condition:
    base = previous or Condition()
    cell_properties = element.find(qn("w:tcPr"))
    return Condition(
        merged(base.paragraph, paragraph_properties(element.find(qn("w:pPr")))),
        merged(base.run, run_properties(element.find(qn("w:rPr")))),
        hex_color(attribute(cell_properties, "w:shd", "w:fill")) or base.shading,
        merged(base.borders, border_set(cell_properties.find(qn("w:tcBorders"))) or {}) if cell_properties is not None else base.borders,
    )


def cell_margins(element) -> dict:
    if element is None:
        return {}
    margins = {}
    for side, aliases in (("top", ("top",)), ("bottom", ("bottom",)), ("left", ("left", "start")), ("right", ("right", "end"))):
        value = next((number(element.find(qn(f"w:{alias}")).get(qn("w:w"))) for alias in aliases if element.find(qn(f"w:{alias}")) is not None), None)
        if value is not None:
            margins[side] = value
    return margins


def table_look(properties) -> dict:
    look = properties.find(qn("w:tblLook")) if properties is not None else None
    if look is None:
        return dict(DEFAULT_LOOK)
    if look.get(qn("w:val")) and not look.get(qn("w:firstRow")):
        bits = int(look.get(qn("w:val")), 16)
        return {name: bool(bits & bit) for name, bit in LOOK_BITS.items()}
    return {name: look.get(qn(f"w:{name}"), "0") in ("1", "true") for name in LOOK_BITS}


def grid_columns(table) -> list[float]:
    declared = [number(column.get(qn("w:w"))) or None for column in table.findall(f"{qn('w:tblGrid')}/{qn('w:gridCol')}")]
    spans = [row_spans(row) for row in table.findall(qn("w:tr"))]
    count = max([len(declared), *(sum(span for span, _width in row) for row in spans)])
    widths = declared + [None] * (count - len(declared))
    if None in widths:
        fill_from_cell_widths(widths, spans)
        fill_unknown_widths(widths, preferred_table_width(table))
    return [twips_to_pixels(width) for width in widths]


def row_spans(row) -> list[tuple[int, float | None]]:
    properties = row.find(qn("w:trPr"))
    before = int(attribute(properties, "w:gridBefore", "w:val") or 0)
    after = int(attribute(properties, "w:gridAfter", "w:val") or 0)
    cells = [(int(attribute(cell.find(qn("w:tcPr")), "w:gridSpan", "w:val") or 1), fixed_width(cell.find(qn("w:tcPr")), "w:tcW")) for cell in row_cells(row)]
    return [(1, None)] * before + cells + [(1, None)] * after


def fixed_width(properties, tag: str) -> float | None:
    if attribute(properties, tag, "w:type") not in (None, "dxa"):
        return None
    return number(attribute(properties, tag, "w:w")) or None


def fill_from_cell_widths(widths: list, spans: list) -> None:
    for wanted_span in sorted({span for row in spans for span, _width in row}):
        for row in spans:
            column = 0
            for span, width in row:
                unknown = [index for index in range(column, column + span) if widths[index] is None]
                if span == wanted_span and width and unknown:
                    known = sum(widths[index] for index in range(column, column + span) if widths[index] is not None)
                    for index in unknown:
                        widths[index] = max(width - known, 0) / len(unknown) or None
                column += span


def preferred_table_width(table) -> float | None:
    return fixed_width(table.find(qn("w:tblPr")), "w:tblW")


def fill_unknown_widths(widths: list, table_width: float | None) -> None:
    unknown = [index for index, width in enumerate(widths) if width is None]
    known = [width for width in widths if width is not None]
    remaining = (table_width or 0) - sum(known)
    share = remaining / len(unknown) if remaining > 0 else (sum(known) / len(known) if known else DEFAULT_COLUMN_TWIPS)
    for index in unknown:
        widths[index] = share


def table_block(table, part, builder, layers: TableLayers) -> TableBlock:
    properties = table.find(qn("w:tblPr"))
    style = table_style(builder.styles.table_layers(attribute(properties, "w:tblStyle", "w:val")))
    borders = merged(style.borders, border_set(properties.find(qn("w:tblBorders"))) or {}) if properties is not None else style.borders
    margins = {**style.margins, **cell_margins(properties.find(qn("w:tblCellMar")) if properties is not None else None)}
    look = table_look(properties)
    columns = grid_columns(table)
    rows, placements = table_rows(table)
    cells = [
        cell_block(placement, len(rows), len(columns), part, builder, layers, style, look, borders, margins)
        for placement in placements
    ]
    return TableBlock(
        columns=columns,
        rows=rows,
        cells=cells,
        indent=twips_to_pixels(number(attribute(properties, "w:tblInd", "w:w")) or 0),
        align={"center": "center", "right": "right", "end": "right"}.get(attribute(properties, "w:jc", "w:val") or "", "left"),
    )


@dataclass
class Placement:
    row: int
    column: int
    span: int
    element: object
    row_span: int = 1


def table_rows(table) -> tuple[list[RowBlock], list[Placement]]:
    rows, placements, open_merges = [], [], {}
    for row_index, row in enumerate(table.findall(qn("w:tr"))):
        row_properties = row.find(qn("w:trPr"))
        rows.append(row_block(row_properties))
        column = int(attribute(row_properties, "w:gridBefore", "w:val") or 0)
        for cell in row_cells(row):
            cell_properties = cell.find(qn("w:tcPr"))
            span = int(attribute(cell_properties, "w:gridSpan", "w:val") or 1)
            vertical_merge = cell_properties.find(qn("w:vMerge")) if cell_properties is not None else None
            if vertical_merge is not None and vertical_merge.get(qn("w:val"), "continue") != "restart" and column in open_merges:
                open_merges[column].row_span += 1
                column += span
                continue
            placement = Placement(row_index, column, span, cell)
            if vertical_merge is not None:
                open_merges[column] = placement
            else:
                open_merges.pop(column, None)
            placements.append(placement)
            column += span
    return rows, placements


def row_cells(row) -> list:
    cells = []
    for child in row:
        if child.tag == qn("w:tc"):
            cells.append(child)
        elif child.tag in (qn("w:sdt"), qn("w:customXml")):
            content = child.find(qn("w:sdtContent"))
            cells.extend(row_cells(content if content is not None else child))
    return cells


def row_block(properties) -> RowBlock:
    height = number(attribute(properties, "w:trHeight", "w:val"))
    rule = attribute(properties, "w:trHeight", "w:hRule")
    is_header = properties is not None and properties.find(qn("w:tblHeader")) is not None
    return RowBlock(twips_to_pixels(height) if height else 0, rule == "exact", is_header)


def conditions_for(placement: Placement, row_count: int, column_count: int, look: dict) -> list[str]:
    names = []
    body_row = placement.row - (1 if look["firstRow"] else 0)
    if not look["noHBand"] and body_row >= 0:
        names.append("band1Horz" if body_row % 2 == 0 else "band2Horz")
    if look["firstColumn"] and placement.column == 0:
        names.append("firstCol")
    if look["lastColumn"] and placement.column + placement.span == column_count:
        names.append("lastCol")
    if look["firstRow"] and placement.row == 0:
        names.append("firstRow")
    if look["lastRow"] and placement.row + placement.row_span == row_count:
        names.append("lastRow")
    return names


def cell_block(placement: Placement, row_count: int, column_count: int, part, builder, layers: TableLayers, style: TableStyle, look: dict, borders: dict, margins: dict) -> CellBlock:
    applied = [style.conditions[name] for name in conditions_for(placement, row_count, column_count, look) if name in style.conditions]
    cell_layers = TableLayers(
        merged(layers.paragraph, style.whole.paragraph, *(condition.paragraph for condition in applied)),
        merged(layers.run, style.whole.run, *(condition.run for condition in applied)),
    )
    properties = placement.element.find(qn("w:tcPr"))
    shading = hex_color(attribute(properties, "w:shd", "w:fill"))
    conditional_shading = next((condition.shading for condition in reversed(applied) if condition.shading), None)
    own_margins = {**margins, **cell_margins(properties.find(qn("w:tcMar")) if properties is not None else None)}
    edges = cell_edges(placement, row_count, column_count, borders, applied, properties)
    vertical = attribute(properties, "w:vAlign", "w:val") or "top"
    return CellBlock(
        row=placement.row,
        column=placement.column,
        span=placement.span,
        row_span=placement.row_span,
        blocks=builder.blocks(list(placement.element), part, cell_layers),
        padding=tuple(twips_to_pixels(own_margins[side]) for side in ("top", "right", "bottom", "left")),
        background=shading or conditional_shading or style.whole.shading,
        borders=edges,
        vertical_align=vertical if vertical in VERTICAL_ALIGNMENTS else "top",
        continuation_top=borders.get("insideH") or borders.get("top"),
    )


def cell_edges(placement: Placement, row_count: int, column_count: int, borders: dict, applied: list, properties) -> dict:
    own = border_set(properties.find(qn("w:tcBorders"))) or {} if properties is not None else {}
    conditional = merged(*(condition.borders for condition in applied)) if applied else {}
    at_top, at_left = placement.row == 0, placement.column == 0
    at_bottom = placement.row + placement.row_span == row_count
    at_right = placement.column + placement.span == column_count
    chosen = {
        "bottom": edge(own, conditional, "bottom", borders.get("bottom") if at_bottom else borders.get("insideH")),
        "right": edge(own, conditional, "right", borders.get("right") if at_right else borders.get("insideV")),
    }
    if at_top:
        chosen["top"] = edge(own, conditional, "top", borders.get("top"))
    if at_left:
        chosen["left"] = edge(own, conditional, "left", borders.get("left") or borders.get("start"))
    return {side: value for side, value in chosen.items() if value}


def edge(own: dict, conditional: dict, side: str, fallback: dict | None) -> dict | None:
    aliases = {"left": ("left", "start"), "right": ("right", "end")}.get(side, (side,))
    for source in (own, conditional):
        found = next((source[alias] for alias in aliases if alias in source), None)
        if found is not None:
            return found
    return fallback
