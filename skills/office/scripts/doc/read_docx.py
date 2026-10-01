#!/usr/bin/env python3
from __future__ import annotations

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn

from docx_blocks import block_kind, body_block_elements, element_text, has_page_break, heading_level, table_cell_texts, wrap_block
from docx_comments import describe_comment_threads
from docx_reference_operations import bookmark_names, describe_notes
from docx_revisions import collect_revisions
from docx_text import visible_text
from office_result import OfficeArgumentParser, Result, run_command


DEFAULT_BLOCK_LIMIT = 300
TABLE_ROW_LIMIT = 60
TEXT_CHARACTER_LIMIT = 4000


def main() -> Result:
    arguments = parse_arguments()
    document = Document(arguments.document_path)
    elements = body_block_elements(document)
    shown = elements[arguments.start:arguments.start + arguments.limit]
    blocks = [describe_block(element, document, arguments.start + offset) for offset, element in enumerate(shown)]
    details = {
        "blockCount": len(elements),
        "start": arguments.start,
        "truncated": arguments.start + len(shown) < len(elements),
        "blocks": blocks,
        "sections": [describe_section(section, index) for index, section in enumerate(document.sections)],
        "paragraphStyles": style_names(document, WD_STYLE_TYPE.PARAGRAPH),
        "tableStyles": style_names(document, WD_STYLE_TYPE.TABLE),
        "comments": describe_comment_threads(document, elements),
    }
    bookmarks = sorted(bookmark_names(document) - {"_GoBack"})
    if bookmarks:
        details["bookmarks"] = bookmarks
    notes = describe_notes(document)
    if notes:
        details["notes"] = notes
    revisions = collect_revisions(document.element.body, elements)
    details["revisionCount"] = len(revisions)
    if arguments.revisions:
        details["revisions"] = [revision.to_json() for revision in revisions]
    return Result(summary=f"read {len(blocks)} of {len(elements)} blocks from {arguments.document_path}", output_path=arguments.document_path, details=details)


def style_names(document, style_type) -> list[str]:
    return sorted(style.name for style in document.styles if style.type == style_type)


def describe_block(element, document, index: int) -> dict:
    kind = block_kind(element, document)
    block = wrap_block(element, document)
    if kind == "table":
        return describe_table(block, index)
    if kind == "contentControl":
        return {"index": index, "kind": kind, "text": limited(element_text(element))}
    description = {"index": index, "kind": kind, "style": block.style.name if block.style is not None else "", "text": limited(element_text(element))}
    if kind == "heading":
        description["level"] = heading_level(block)
    if has_page_break(block):
        description["pageBreak"] = True
    if next(element.iter(qn("w:drawing")), None) is not None:
        description["picture"] = True
    return description


def describe_table(table, index: int) -> dict:
    cells = table_cell_texts(table)
    return {
        "index": index,
        "kind": "table",
        "style": table.style.name if table.style is not None else "",
        "rows": len(cells),
        "columns": len(table.columns),
        "cells": [[limited(text) for text in row] for row in cells[:TABLE_ROW_LIMIT]],
        "truncatedRows": len(cells) > TABLE_ROW_LIMIT,
        "mergedCells": has_merged_cells(table),
    }


def has_merged_cells(table) -> bool:
    spans = [int(span.get(qn("w:val"), "1")) for span in table._tbl.iter(qn("w:gridSpan"))]
    return any(span > 1 for span in spans) or next(table._tbl.iter(qn("w:vMerge")), None) is not None


def describe_section(section, index: int) -> dict:
    return {
        "index": index,
        "orientation": "landscape" if section.page_width and section.page_height and section.page_width > section.page_height else "portrait",
        "pageInches": [inches(section.page_width), inches(section.page_height)],
        "marginsInches": [inches(section.top_margin), inches(section.right_margin), inches(section.bottom_margin), inches(section.left_margin)],
        "header": limited(part_text(section.header)),
        "footer": limited(part_text(section.footer)),
        "headerLinkedToPrevious": section.header.is_linked_to_previous,
        "footerLinkedToPrevious": section.footer.is_linked_to_previous,
    }


def inches(length) -> float | None:
    return round(length.inches, 2) if length is not None else None


def part_text(header_or_footer) -> str:
    return "\n".join(line for line in visible_text(header_or_footer._element).split("\n") if line.strip())


def limited(text: str) -> str:
    if len(text) <= TEXT_CHARACTER_LIMIT:
        return text
    return text[:TEXT_CHARACTER_LIMIT] + " …"


def parse_arguments():
    parser = OfficeArgumentParser(description="Read a .docx as indexed blocks, section headers and footers, comment threads, and tracked changes. Block indexes, comment ids and revision ids are what doc apply takes. Block text is the text as if every tracked change were accepted.")
    parser.add_argument("document_path")
    parser.add_argument("--start", type=int, default=0, help="first block index to show")
    parser.add_argument("--revisions", action="store_true", help="list every tracked change with its id, type, author, date, block and text")
    parser.add_argument("--limit", type=int, default=DEFAULT_BLOCK_LIMIT, help=f"most blocks to show, default {DEFAULT_BLOCK_LIMIT}")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
