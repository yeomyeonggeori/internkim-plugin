from office_result import INVALID_ARGUMENTS, OfficeFailure
from pdf_definitions import PAGE_NOT_IN_DOCUMENT


def select_pages(selection: str, page_count: int) -> list[int]:
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
            raise OfficeFailure(PAGE_NOT_IN_DOCUMENT.issue(f"page {page} is outside this {page_count}-page PDF", location=part))
    if first > last:
        raise OfficeFailure(INVALID_ARGUMENTS.issue(f"page range {part!r} runs backwards", location=part))
    return range(first, last + 1)


def parse_page_number(text: str, part: str) -> int:
    if not text.strip().isdigit():
        raise OfficeFailure(INVALID_ARGUMENTS.issue(f"{part!r} is not a page number or range", location=part, suggestion="pass pages such as 1,3-5"))
    return int(text)
