from __future__ import annotations

import html
from pathlib import Path
import re

import pypdfium2

from block_writers import inline_html
from markdown_blocks import Heading


MAXIMUM_PAGINATION_PASSES = 12
MARKUP_TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")


def stranded_heading(pdf_path: Path, blocks: list, headings_on_new_page: frozenset[int]) -> int | None:
    headings = [(index, compact(plain_text(block.text))) for index, block in enumerate(blocks) if isinstance(block, Heading)]
    headings = [(index, text) for index, text in headings if text]
    cursor = 0
    for page_text in page_texts(pdf_path)[:-1]:
        last_on_page, cursor, position = headings_on_page(page_text, headings, cursor)
        if last_on_page is None or position != len(page_text):
            continue
        start = heading_run_start(blocks, last_on_page)
        if start not in headings_on_new_page:
            return start
    return None


def headings_on_page(page_text: str, headings: list[tuple[int, str]], cursor: int) -> tuple[int | None, int, int]:
    last_on_page, position = None, 0
    while cursor < len(headings):
        found = page_text.find(headings[cursor][1], position)
        if found < 0:
            break
        last_on_page, position = headings[cursor][0], found + len(headings[cursor][1])
        cursor += 1
    return last_on_page, cursor, position


def heading_run_start(blocks: list, index: int) -> int:
    while index > 0 and isinstance(blocks[index - 1], Heading):
        index -= 1
    return index


def page_texts(pdf_path: Path) -> list[str]:
    document = pypdfium2.PdfDocument(str(pdf_path))
    try:
        return [without_suffix(compact(page.get_textpage().get_text_range()), f"{number}/{len(document)}") for number, page in enumerate(document, start=1)]
    finally:
        document.close()


def without_suffix(text: str, suffix: str) -> str:
    return text[:-len(suffix)] if text.endswith(suffix) else text


def plain_text(markdown_text: str) -> str:
    return html.unescape(MARKUP_TAG.sub("", inline_html(markdown_text)))


def compact(text: str) -> str:
    return WHITESPACE.sub("", text)
