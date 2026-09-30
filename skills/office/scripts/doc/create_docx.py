#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from skill_runtime import ensure_requirements


def require_text(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def optional_text(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("text fields must be strings")
    return value


ALLOWED_SPECIFICATION_KEYS = {"title", "subtitle", "fontName", "fontSize", "page", "blocks"}
SPECIFICATION_HINT = 'a --spec file must look like {"title": "...", "fontName": "...", "blocks": [{"type": "heading", "level": 2, "text": "..."}, {"type": "paragraph", "text": "..."}, {"type": "bullets", "items": ["..."]}, {"type": "table", "rows": [["..."]]}]}'


def load_specification(specification_path):
    with open(specification_path, "r", encoding="utf-8") as specification_file:
        specification = json.load(specification_file)
    if not isinstance(specification, dict):
        raise ValueError("document specification must be an object")
    unknown_keys = set(specification) - ALLOWED_SPECIFICATION_KEYS
    if unknown_keys:
        raise ValueError(f"unknown specification fields {sorted(unknown_keys)}; {SPECIFICATION_HINT}")
    blocks = specification.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError(f"specification has no content: blocks must be a non-empty array; {SPECIFICATION_HINT}")
    return specification


def create_document(specification):
    if not ensure_requirements("office"):
        raise RuntimeError("docx dependencies are unavailable after bootstrap")

    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt

    document = Document()
    page = specification.get("page", {})
    if page is not None and not isinstance(page, dict):
        raise ValueError("page must be an object")

    section = document.sections[0]
    if page.get("orientation") == "landscape":
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = section.page_height, section.page_width

    margin_inches = float(page.get("marginInches", 0.8))
    section.top_margin = Inches(margin_inches)
    section.right_margin = Inches(margin_inches)
    section.bottom_margin = Inches(margin_inches)
    section.left_margin = Inches(margin_inches)

    font_name = require_text(specification.get("fontName", "맑은 고딕"), "fontName")
    font_size = float(specification.get("fontSize", 10.5))
    set_document_font(document, font_name, font_size, Pt)

    title = optional_text(specification.get("title"))
    if title:
        heading = document.add_heading(title, level=0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for block in read_blocks(specification):
        add_block(document, block)

    return document


def set_document_font(document, font_name, font_size, point_class):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    for style_name in ["Normal", "Title", "Heading 1", "Heading 2", "Heading 3", "Heading 4"]:
        if style_name not in document.styles:
            continue
        style = document.styles[style_name]
        style.font.name = font_name
        style.font.size = point_class(font_size if style_name == "Normal" else max(font_size + 1, 11))
        style.paragraph_format.line_spacing = 1.08
        style.paragraph_format.space_after = point_class(4)
        run_properties = style.element.get_or_add_rPr()
        run_fonts = run_properties.rFonts
        if run_fonts is None:
            run_fonts = OxmlElement("w:rFonts")
            run_properties.append(run_fonts)
        run_fonts.set(qn("w:ascii"), font_name)
        run_fonts.set(qn("w:hAnsi"), font_name)
        run_fonts.set(qn("w:eastAsia"), font_name)


def read_blocks(specification):
    blocks = specification.get("blocks", [])
    if not isinstance(blocks, list):
        raise ValueError("blocks must be an array")
    return blocks


def add_block(document, block):
    if not isinstance(block, dict):
        raise ValueError("each block must be an object")
    block_type = require_text(block.get("type"), "block.type")
    if block_type == "heading":
        add_heading(document, block)
        return
    if block_type == "paragraph":
        document.add_paragraph(optional_text(block.get("text")))
        return
    if block_type == "bullets":
        add_list(document, block, "List Bullet")
        return
    if block_type == "numbered":
        add_list(document, block, "List Number")
        return
    if block_type == "table":
        add_table(document, block)
        return
    if block_type == "pageBreak":
        document.add_page_break()
        return
    raise ValueError(f"unsupported block type: {block_type}")


def add_heading(document, block):
    level = int(block.get("level", 1))
    if level < 1 or level > 4:
        raise ValueError("heading level must be between 1 and 4")
    document.add_heading(optional_text(block.get("text")), level=level)


def add_list(document, block, style_name):
    items = block.get("items", [])
    if not isinstance(items, list):
        raise ValueError("list items must be an array")
    for item in items:
        document.add_paragraph(require_text(item, "list item"), style=style_name)


def add_table(document, block):
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT

    rows = block.get("rows", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("table rows must be a non-empty array")
    width = len(rows[0])
    if width == 0:
        raise ValueError("table rows must contain at least one column")
    column_widths = read_column_widths(block, width)
    table = document.add_table(rows=0, cols=width)
    table.style = optional_text(block.get("style")) or "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for row_index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != width:
            raise ValueError("all table rows must have the same width")
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = "" if value is None else str(value)
            cells[index].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            set_cell_width(cells[index], column_widths[index])
            format_cell_text(cells[index], row_index == 0)
            if row_index == 0:
                shade_cell(cells[index], "EAF1F8")
    set_table_borders(table)


def read_column_widths(block, width):
    column_widths = block.get("columnWidthsInches")
    if isinstance(column_widths, list) and len(column_widths) == width:
        return [float(value) for value in column_widths]
    default_width = 6.6 / width
    return [default_width for _ in range(width)]


def set_cell_width(cell, width_inches):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches

    cell.width = Inches(width_inches)
    cell_width = OxmlElement("w:tcW")
    cell_width.set(qn("w:w"), str(int(width_inches * 1440)))
    cell_width.set(qn("w:type"), "dxa")
    cell._tc.get_or_add_tcPr().append(cell_width)


def format_cell_text(cell, is_header):
    from docx.shared import Pt

    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.space_after = Pt(2)
        for run in paragraph.runs:
            run.bold = is_header


def shade_cell(cell, color):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), color)
    cell._tc.get_or_add_tcPr().append(shading)


def set_table_borders(table):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    borders = OxmlElement("w:tblBorders")
    for border_name in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        border = OxmlElement(f"w:{border_name}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "6")
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), "B7C3D0")
        borders.append(border)
    table._tbl.tblPr.append(borders)


def stringify_cell(value):
    return "" if value is None else str(value)


def load_table_block(table_path):
    expanded_path = os.path.expanduser(table_path)
    with open(expanded_path, "r", encoding="utf-8") as table_file:
        table_data = json.load(table_file)
    rows, column_widths = normalize_table_data(table_data, expanded_path)
    block = {"type": "table", "rows": rows}
    if column_widths is not None:
        block["columnWidthsInches"] = column_widths
    return block


def normalize_table_data(table_data, source_path):
    if isinstance(table_data, list):
        return normalize_table_rows(table_data, source_path), None
    if isinstance(table_data, dict) and isinstance(table_data.get("rows"), list):
        return normalize_table_rows(table_data["rows"], source_path), table_data.get("columnWidthsInches")
    raise ValueError(f"table file {source_path} must be a rows array, an array of objects, or an object with a rows array")


def normalize_table_rows(rows, source_path):
    if not rows:
        raise ValueError(f"table file {source_path} must contain at least one row")
    if all(isinstance(row, dict) for row in rows):
        header = list(rows[0].keys())
        return [header] + [[stringify_cell(row.get(key)) for key in header] for row in rows]
    if all(isinstance(row, list) for row in rows):
        return [[stringify_cell(value) for value in row] for row in rows]
    raise ValueError(f"table file {source_path} rows must all be arrays or all be objects")


class AppendOrderedBlockAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        namespace.ordered_arguments.append((option_string.lstrip("-"), values))


def flush_pending_bullets(blocks, pending_bullet_items):
    if not pending_bullet_items:
        return
    blocks.append({"type": "bullets", "items": list(pending_bullet_items)})
    pending_bullet_items.clear()


def build_inline_block(kind, value):
    if kind == "heading":
        return {"type": "heading", "level": 1, "text": value}
    if kind == "paragraph":
        return {"type": "paragraph", "text": value}
    if kind == "table":
        return load_table_block(value)
    raise ValueError(f"unsupported inline block kind: {kind}")


def build_specification(arguments):
    blocks = []
    pending_bullet_items = []
    for kind, value in arguments.ordered_arguments:
        if kind == "bullet":
            pending_bullet_items.append(value)
            continue
        flush_pending_bullets(blocks, pending_bullet_items)
        blocks.append(build_inline_block(kind, value))
    flush_pending_bullets(blocks, pending_bullet_items)
    return {"title": arguments.title or "", "blocks": blocks}


def parse_arguments():
    parser = argparse.ArgumentParser(description="Create a DOCX file from arguments or a JSON spec.")
    parser.add_argument("output_path", help="Path to the output .docx file")
    parser.add_argument("--title", metavar="TEXT", default="", help="Document title")
    parser.add_argument("--heading", action=AppendOrderedBlockAction, dest="ordered_arguments", default=[], metavar="TEXT", help="Add a level-1 heading (repeatable, position-sensitive)")
    parser.add_argument("--paragraph", action=AppendOrderedBlockAction, dest="ordered_arguments", default=[], metavar="TEXT", help="Add a paragraph (repeatable, position-sensitive)")
    parser.add_argument("--bullet", action=AppendOrderedBlockAction, dest="ordered_arguments", default=[], metavar="TEXT", help="Add a bullet item (repeatable, position-sensitive; consecutive bullets merge into one list)")
    parser.add_argument("--table", action=AppendOrderedBlockAction, dest="ordered_arguments", default=[], metavar="JSON_PATH", help="Add a table from a JSON rows file (repeatable, position-sensitive)")
    parser.add_argument("--spec", metavar="JSON_PATH", help="Full {title,page,fontName,blocks} spec for rich structure (tables, fonts, margins)")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    has_inline_content = arguments.title or arguments.ordered_arguments
    if not arguments.spec and not has_inline_content:
        raise ValueError("provide at least --title, --heading, --paragraph, --bullet, or --table; or pass --spec <file>")
    specification = load_specification(arguments.spec) if arguments.spec else build_specification(arguments)
    document = create_document(specification)
    output_path = Path(os.path.expanduser(arguments.output_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    print(output_path)


if __name__ == "__main__":
    main()
