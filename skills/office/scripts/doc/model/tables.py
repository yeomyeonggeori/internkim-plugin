from __future__ import annotations

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt


HEADER_FILL_COLOR = "EAF1F8"
BORDER_COLOR = "B7C3D0"
BORDER_NAMES = ("top", "left", "bottom", "right", "insideH", "insideV")
CELL_MARGIN_TWIPS = {"top": 60, "left": 100, "bottom": 60, "right": 100}
SPACE_AFTER_TABLE = Pt(8)
TABLE_PROPERTIES_AFTER_BORDERS = ("w:shd", "w:tblLayout", "w:tblCellMar", "w:tblLook")
TABLE_PROPERTIES_AFTER_MARGINS = ("w:tblLook", "w:tblCaption", "w:tblDescription")
CELL_PROPERTIES_AFTER_SHADING = ("w:noWrap", "w:tcMar", "w:textDirection", "w:tcFitText", "w:vAlign", "w:hideMark")


def format_table(table) -> None:
    properties = table._tbl.tblPr
    properties.insert_element_before(table_borders(), *TABLE_PROPERTIES_AFTER_BORDERS)
    properties.insert_element_before(cell_margins(), *TABLE_PROPERTIES_AFTER_MARGINS)
    format_header_row(table.rows[0])


def format_header_row(row) -> None:
    row._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for cell in row.cells:
        shade_cell(cell, HEADER_FILL_COLOR)
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True


def table_borders():
    borders = OxmlElement("w:tblBorders")
    for border_name in BORDER_NAMES:
        border = OxmlElement(f"w:{border_name}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "6")
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), BORDER_COLOR)
        borders.append(border)
    return borders


def cell_margins():
    margins = OxmlElement("w:tblCellMar")
    for side, twips in CELL_MARGIN_TWIPS.items():
        margin = OxmlElement(f"w:{side}")
        margin.set(qn("w:w"), str(twips))
        margin.set(qn("w:type"), "dxa")
        margins.append(margin)
    return margins


def shade_cell(cell, color: str) -> None:
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), color)
    cell._tc.get_or_add_tcPr().insert_element_before(shading, *CELL_PROPERTIES_AFTER_SHADING)


def add_space_after_table(document: Document) -> None:
    spacer = document.add_paragraph()
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = SPACE_AFTER_TABLE
    spacer.paragraph_format.line_spacing = Pt(1)
