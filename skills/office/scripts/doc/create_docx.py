#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from doc_definitions import DOCUMENT_SPECIFICATION, TABLE_FILE
from docx_defaults import DOCUMENT_FONT, apply_korean_defaults, set_page, usable_width_inches
from fonts.docx_embedding import save_document
from docx_tables import add_space_after_table, format_table
from docx_lists import add_list_paragraph, start_list
from office_result import INVALID_ARGUMENTS, INVALID_VALUE, Issue, OfficeArgumentParser, OfficeFailure, Result, read_json_file, run_command
from office_schema import require_valid
from fonts.registry import BODY_SIZE_POINTS


DEFAULT_FONT_NAME = DOCUMENT_FONT
SIZED_STYLE_NAMES = ["Normal", "Title", "Heading 1", "Heading 2", "Heading 3", "Heading 4"]
LIST_BLOCK_TYPES = ("bullets", "numbered")


def main() -> Result:
    arguments = parse_arguments()
    specification = read_specification(arguments)
    document = create_document(specification)
    output_path = Path(os.path.expanduser(arguments.output_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_document(document, output_path)
    return Result(summary=f"created {output_path}", output_path=str(output_path))


def read_specification(arguments: argparse.Namespace) -> dict:
    if arguments.spec:
        specification = read_json_file(arguments.spec)
        location = "spec"
    elif arguments.title or arguments.ordered_arguments:
        specification = build_specification(arguments)
        location = "arguments"
    else:
        raise OfficeFailure(INVALID_ARGUMENTS.issue("provide at least --title, --heading, --paragraph, --bullet, or --table; or pass --spec <file>"))
    require_valid(DOCUMENT_SPECIFICATION, specification, location)
    require_rectangular_tables(specification["blocks"], f"{location}.blocks")
    return specification


def require_rectangular_tables(blocks: list[dict], location: str) -> None:
    problems = [
        problem
        for index, block in enumerate(blocks)
        if block["type"] == "table"
        for problem in table_width_problems(block["rows"], f"{location}[{index}].rows")
    ]
    if problems:
        raise OfficeFailure(*problems)


def table_width_problems(rows: list[list], location: str) -> list[Issue]:
    width = len(rows[0])
    if width == 0:
        return [INVALID_VALUE.issue(f"{location}[0]: table rows must contain at least one column", f"{location}[0]")]
    return [
        INVALID_VALUE.issue(f"{location}[{index}]: has {len(row)} cells but the header row has {width}", f"{location}[{index}]")
        for index, row in enumerate(rows)
        if len(row) != width
    ]


def create_document(specification: dict) -> Document:
    document = Document()
    set_document_page(document.sections[0], specification.get("page") or {})
    font_name = (specification.get("fontName") or DEFAULT_FONT_NAME).strip()
    set_text_sizes(document, float(specification.get("fontSize") or BODY_SIZE_POINTS))
    apply_korean_defaults(document, font_name)
    add_title(document, specification.get("title") or "")
    for block in specification["blocks"]:
        add_block(document, block)
    return document


def set_document_page(section, page: dict) -> None:
    margin_inches = page.get("marginInches")
    set_page(section, None if margin_inches is None else float(margin_inches), page.get("orientation") == "landscape")


def set_text_sizes(document: Document, font_size: float) -> None:
    for style_name in SIZED_STYLE_NAMES:
        if style_name not in document.styles:
            continue
        style = document.styles[style_name]
        style.font.size = Pt(font_size if style_name == "Normal" else max(font_size + 1, 11))
        style.paragraph_format.line_spacing = 1.08
        style.paragraph_format.space_after = Pt(4)


def add_title(document: Document, title: str) -> None:
    if not title:
        return
    heading = document.add_heading(title, level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER


def add_block(document: Document, block: dict) -> None:
    block_type = block["type"]
    if block_type == "heading":
        document.add_heading(block.get("text") or "", level=int(block.get("level") or 1))
    elif block_type == "paragraph":
        document.add_paragraph(block.get("text") or "")
    elif block_type in LIST_BLOCK_TYPES:
        add_list(document, block_type == "numbered", block.get("items") or [])
    elif block_type == "table":
        add_table(document, block)
    elif block_type == "pageBreak":
        document.add_page_break()


def add_list(document: Document, is_numbered: bool, items: list[str]) -> None:
    list_id = start_list(document, is_numbered)
    for item in items:
        add_list_paragraph(document, list_id, 0).add_run(item.strip())


def add_table(document: Document, block: dict) -> None:
    rows = block["rows"]
    width = len(rows[0])
    column_widths = read_column_widths(block, width, usable_width_inches(document.sections[-1]))
    table = document.add_table(rows=0, cols=width)
    table.style = block.get("style") or "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            fill_cell(cells[index], value, column_widths[index])
    format_table(table)
    add_space_after_table(document)


def fill_cell(cell, value: object, width_inches: float) -> None:
    cell.text = "" if value is None else str(value)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    cell.width = Inches(width_inches)
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.space_after = Pt(2)


def read_column_widths(block: dict, width: int, table_width: float) -> list[float]:
    column_widths = block.get("columnWidthsInches")
    if isinstance(column_widths, list) and len(column_widths) == width:
        return [float(value) for value in column_widths]
    return [table_width / width for _ in range(width)]


def load_table_block(table_path: str) -> dict:
    table_data = read_json_file(table_path)
    require_valid(TABLE_FILE, table_data, table_path)
    if isinstance(table_data, list):
        return {"type": "table", "rows": normalize_table_rows(table_data)}
    block = {"type": "table", "rows": normalize_table_rows(table_data["rows"])}
    if table_data.get("columnWidthsInches") is not None:
        block["columnWidthsInches"] = table_data["columnWidthsInches"]
    return block


def normalize_table_rows(rows: list) -> list[list[str]]:
    if isinstance(rows[0], dict):
        header = list(rows[0].keys())
        return [header] + [[stringify_cell(row.get(key)) for key in header] for row in rows]
    return [[stringify_cell(value) for value in row] for row in rows]


def stringify_cell(value: object) -> str:
    return "" if value is None else str(value)


class AppendOrderedBlockAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        namespace.ordered_arguments.append((option_string.lstrip("-"), values))


def build_specification(arguments: argparse.Namespace) -> dict:
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


def flush_pending_bullets(blocks: list[dict], pending_bullet_items: list[str]) -> None:
    if not pending_bullet_items:
        return
    blocks.append({"type": "bullets", "items": list(pending_bullet_items)})
    pending_bullet_items.clear()


def build_inline_block(kind: str, value: str) -> dict:
    if kind == "heading":
        return {"type": "heading", "level": 1, "text": value}
    if kind == "paragraph":
        return {"type": "paragraph", "text": value}
    return load_table_block(value)


def parse_arguments() -> argparse.Namespace:
    parser = OfficeArgumentParser(description="Create a DOCX file from arguments or a JSON spec; office guide doc describes the spec.")
    parser.add_argument("output_path", help="Path to the output .docx file")
    parser.add_argument("--title", metavar="TEXT", default="", help="Document title")
    parser.add_argument("--heading", action=AppendOrderedBlockAction, dest="ordered_arguments", default=[], metavar="TEXT", help="Add a level-1 heading (repeatable, position-sensitive)")
    parser.add_argument("--paragraph", action=AppendOrderedBlockAction, dest="ordered_arguments", default=[], metavar="TEXT", help="Add a paragraph (repeatable, position-sensitive)")
    parser.add_argument("--bullet", action=AppendOrderedBlockAction, dest="ordered_arguments", default=[], metavar="TEXT", help="Add a bullet item (repeatable, position-sensitive; consecutive bullets merge into one list)")
    parser.add_argument("--table", action=AppendOrderedBlockAction, dest="ordered_arguments", default=[], metavar="JSON_PATH", help="Add a table from a JSON rows file (repeatable, position-sensitive)")
    parser.add_argument("--spec", metavar="JSON_PATH", help="Full {title,page,fontName,fontSize,blocks} spec for rich structure")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
