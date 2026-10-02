#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from core.office_arguments import route_arguments
from core.office_result import Result, read_json_file, run_command
from core.office_schema import require_valid
from core.page_sizes import DEFAULT_PAPER, PAPER_BY_NAME
from core.units import millimetres_to_pixels
from doc.document_pdf import DocumentFonts, PageLayout, render_document_pdf
from doc.markdown_blocks import Heading, ListItem, Paragraph, Table
from pdf.pdf_definitions import PDF_SPECIFICATION


def read_specification(specification_path: str) -> dict:
    specification = read_json_file(specification_path)
    require_valid(PDF_SPECIFICATION, specification, "spec")
    return specification


def optional_text(value):
    return (value or "").strip()


def specification_blocks(specification: dict) -> list:
    blocks = []
    title = optional_text(specification.get("title"))
    if title:
        blocks.append(Heading(1, title))
    subtitle = optional_text(specification.get("subtitle"))
    if subtitle:
        blocks.append(Paragraph(subtitle))
    for section in specification.get("sections") or []:
        blocks.extend(section_blocks(section))
    return blocks


def section_blocks(section: dict) -> list:
    title = optional_text(section.get("title"))
    blocks = [Heading(2, title)] if title else []
    blocks.extend(Paragraph(paragraph.strip()) for paragraph in section.get("paragraphs") or [])
    blocks.extend(ListItem("-", 0, bullet.strip()) for bullet in section.get("bullets") or [])
    table = section.get("table")
    if table:
        blocks.append(table_block(table))
    return blocks


def table_block(table: dict) -> Table:
    headers = [cell_text(header) for header in table["headers"]]
    rows = [[cell_text(row[index]) if index < len(row) else "" for index in range(len(headers))] for row in table.get("rows") or []]
    return Table([headers, *rows])


def cell_text(value) -> str:
    return "" if value is None else str(value)


def page_layout(specification: dict) -> PageLayout:
    paper = PAPER_BY_NAME[specification.get("format") or DEFAULT_PAPER.name]
    margin_millimeters = specification.get("marginMillimeters")
    margin = PageLayout().margin if margin_millimeters is None else dict.fromkeys(("top", "right", "bottom", "left"), millimetres_to_pixels(margin_millimeters))
    return PageLayout(paper, margin, specification.get("pageNumbers") is not False)


def document_fonts(specification: dict) -> DocumentFonts:
    font_path = optional_text(specification.get("fontPath"))
    return DocumentFonts(Path(font_path) if font_path else None, optional_text(specification.get("fontName")) or None)


def write_pdf(specification: dict, output_path: Path) -> list:
    blocks = specification_blocks(specification)
    title = optional_text(specification.get("title")) or output_path.stem
    return render_document_pdf(blocks, output_path, Path.cwd(), title, document_fonts(specification), page_layout(specification))



def main():
    arguments = route_arguments("create", "pdf")
    specification = read_specification(arguments.source)
    output_path = Path(os.path.expanduser(arguments.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    issues = write_pdf(specification, output_path)
    return Result(summary=f"created {output_path}", output_path=str(output_path), issues=tuple(issues))


if __name__ == "__main__":
    raise SystemExit(run_command(main))
