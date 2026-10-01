#!/usr/bin/env python3
from __future__ import annotations

from pypdf import PdfReader

from office_inputs import add_password_argument, office_file, require_unlocked_pdf
from office_result import OfficeArgumentParser, Result, run_command


DEFAULT_PAGE_LIMIT = 50
TEXT_CHARACTER_LIMIT = 6000


def main() -> Result:
    arguments = parse_arguments()
    require_unlocked_pdf(arguments.pdf_path, arguments.password)
    reader = PdfReader(arguments.pdf_path, password=arguments.password)
    page_count = len(reader.pages)
    first_index = max(arguments.start - 1, 0)
    shown = reader.pages[first_index:first_index + arguments.limit]
    pages = [describe_page(page, first_index + offset + 1) for offset, page in enumerate(shown)]
    details = {
        "pageCount": page_count,
        "start": first_index + 1,
        "truncated": first_index + len(pages) < page_count,
        "isEncrypted": bool(reader.is_encrypted),
        "pages": pages,
    }
    return Result(summary=f"read {len(pages)} of {page_count} pages from {arguments.pdf_path}", output_path=arguments.pdf_path, details=details)


def describe_page(page, number: int) -> dict:
    text = (page.extract_text() or "").strip()
    return {
        "page": number,
        "widthPoints": round(float(page.mediabox.width), 2),
        "heightPoints": round(float(page.mediabox.height), 2),
        "hasText": bool(text),
        "characterCount": len(text),
        "text": limited(text),
    }


def limited(text: str) -> str:
    if len(text) <= TEXT_CHARACTER_LIMIT:
        return text
    return text[:TEXT_CHARACTER_LIMIT] + " …"


def parse_arguments():
    parser = OfficeArgumentParser(description="Read a PDF's text page by page, with page sizes and whether each page has extractable text.")
    parser.add_argument("pdf_path", type=office_file("pdf"))
    parser.add_argument("--start", type=int, default=1, help="first page number to show, counting from 1")
    parser.add_argument("--limit", type=int, default=DEFAULT_PAGE_LIMIT, help=f"most pages to show, default {DEFAULT_PAGE_LIMIT}")
    add_password_argument(parser)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
