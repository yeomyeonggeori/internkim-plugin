#!/usr/bin/env python3
from __future__ import annotations

import io

import pdfplumber
from pypdf import PdfReader

from core.office_arguments import route_arguments
from core.office_inputs import require_unlocked_pdf, unlocked_pdf_bytes
from pdf.ocr.pdf_ocr import OcrUnavailable, read_pages_by_ocr
from pdf.pdf_tables import line_texts, page_tables, stream_tables
from pdf.pdf_definitions import OCR_UNAVAILABLE, PAGE_READ_BY_OCR, PAGE_WITHOUT_TEXT, page_reading_suggestion
from core.office_result import Issue, Result, run_command


DEFAULT_PAGE_LIMIT = 50
TEXT_CHARACTER_LIMIT = 6000


def main() -> Result:
    arguments = parse_arguments()
    require_unlocked_pdf(arguments.file, arguments.password)
    reader = PdfReader(arguments.file, password=arguments.password)
    page_count = len(reader.pages)
    first_index = max(arguments.start - 1, 0)
    shown = reader.pages[first_index:first_index + arguments.limit]
    data = unlocked_pdf_bytes(arguments.file, arguments.password)
    with pdfplumber.open(io.BytesIO(data)) as layout:
        pages = [describe_page(page, layout.pages[first_index + offset], first_index + offset + 1) for offset, page in enumerate(shown)]
    issues: list[Issue] = []
    if arguments.ocr:
        pages, issues = pages_read_by_ocr(data, pages)
    details = {
        "pageCount": page_count,
        "start": first_index + 1,
        "truncated": first_index + len(pages) < page_count,
        "isEncrypted": bool(reader.is_encrypted),
        "pages": pages,
    }
    issues += scanned_page_issues(arguments, pages)
    return Result(summary=f"read {len(pages)} of {page_count} pages from {arguments.file}", output_path=arguments.file, issues=tuple(issues), details=details)


def pages_read_by_ocr(data: bytes, pages: list[dict]) -> tuple[list[dict], list[Issue]]:
    scanned = [page["page"] for page in pages if not page["hasText"]]
    try:
        lines = read_pages_by_ocr(data, scanned)
    except OcrUnavailable as reason:
        return pages, [OCR_UNAVAILABLE.issue(str(reason), f"pages {listed(scanned)}")]
    pages = [with_ocr_text(page, lines[page["page"]]) if page["page"] in lines else page for page in pages]
    read = [page["page"] for page in pages if page.get("readByOcr")]
    return pages, [PAGE_READ_BY_OCR.issue(f"pages {listed(read)} were read by OCR", f"pages {listed(read)}")] if read else []


def with_ocr_text(page: dict, lines: list) -> dict:
    words = [line.as_word() for line in lines]
    text = "\n".join(line_texts(words))
    if not text:
        return page
    tables = [table.rows for table in stream_tables(words, [])]
    return {**page, "readByOcr": True, "characterCount": len(text), "text": limited(text), **({"tables": tables} if tables else {})}


def scanned_page_issues(arguments, pages: list[dict]) -> list[Issue]:
    scanned = listed([page["page"] for page in pages if not page["hasText"] and not page.get("readByOcr")])
    if not scanned:
        return []
    rerun_command = None if arguments.ocr else f"office read {arguments.file}"
    return [PAGE_WITHOUT_TEXT.issue(f"pages {scanned} have no text layer", f"pages {scanned}", suggestion=page_reading_suggestion(arguments.file, scanned, rerun_command))]


def listed(numbers: list[int]) -> str:
    return ",".join(map(str, numbers))


def describe_page(page, layout_page, number: int) -> dict:
    text = (page.extract_text() or "").strip()
    description = {
        "page": number,
        "widthPoints": round(float(page.mediabox.width), 2),
        "heightPoints": round(float(page.mediabox.height), 2),
        "hasText": bool(text),
        "characterCount": len(text),
        "text": limited(text),
    }
    tables = [table.rows for table in page_tables(layout_page)] if text else []
    if tables:
        description["tables"] = tables
    return description


def limited(text: str) -> str:
    if len(text) <= TEXT_CHARACTER_LIMIT:
        return text
    return text[:TEXT_CHARACTER_LIMIT] + " …"


def parse_arguments():
    return route_arguments("read", "pdf", start=1, limit=DEFAULT_PAGE_LIMIT)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
