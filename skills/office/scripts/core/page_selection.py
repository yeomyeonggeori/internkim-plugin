from __future__ import annotations

from core.office_result import ERROR, INVALID_ARGUMENTS, IssueKind, OfficeFailure


PAGE_NOT_IN_DOCUMENT = IssueKind("PAGE_NOT_IN_DOCUMENT", ERROR, "--pages names a page the file does not have", "read the file to see its page count, then pass pages inside it")


def select_pages(selection: str | None, page_count: int, default_limit: int | None = None) -> list[int]:
    if not (selection or "").strip():
        return list(range(1, min(page_count, default_limit or page_count) + 1))
    pages = []
    for part in selection.split(","):
        pages.extend(expand_range(part.strip(), page_count))
    return sorted(set(pages))


def expand_range(part: str, page_count: int) -> range:
    first_text, separator, last_text = part.partition("-")
    first = parse_page_number(first_text, part)
    last = parse_page_number(last_text, part) if separator else first
    for page in (first, last):
        if not 1 <= page <= page_count:
            raise OfficeFailure(PAGE_NOT_IN_DOCUMENT.issue(f"--pages: page {page} is outside this {page_count}-page file", location="--pages", suggestion=f"pass pages from 1 to {page_count}"))
    if first > last:
        raise OfficeFailure(INVALID_ARGUMENTS.issue(f"--pages: the range {part!r} runs backwards", location="--pages"))
    return range(first, last + 1)


def parse_page_number(text: str, part: str) -> int:
    if not text.strip().isdigit():
        raise OfficeFailure(INVALID_ARGUMENTS.issue(f"--pages: {part!r} is not a page number or range", location="--pages", suggestion="pass pages such as 1,3-5"))
    return int(text)
