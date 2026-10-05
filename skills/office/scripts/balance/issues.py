from __future__ import annotations

from pathlib import Path

from balance.measure import PageMeasure
from balance.tokens import (
    EARLY_PAGE_END_FILL,
    LARGE_EMPTY_BAND_RATIO,
    NEARLY_EMPTY_LAST_PAGE_FILL,
    ORPHAN_LAST_PAGE_FILL,
    ORPHAN_LAST_PAGE_LINES,
    SPARSE_PAGE_FILL,
)
from core.office_result import WARNING, Issue, IssueKind
from core.source_snapshot import read_source

PAGE_SPARSE = IssueKind("PAGE_SPARSE", WARNING, "the only page of the document ends in its upper part and leaves the rest empty", "make the document again from its schema, which sets short content in the page; or add the content the request gives and the page lacks")
LAST_PAGE_SPARSE = IssueKind("LAST_PAGE_SPARSE", WARNING, "the last page holds only a few lines after a full page", "shorten the text before it so it ends on the page before, or move the lines up; merge a schema document again, which tightens the spacing within its bound")
PAGE_ENDS_EARLY = IssueKind("PAGE_ENDS_EARLY", WARNING, "a page that is followed by another stops with a wide empty band at its foot, usually because the next block was kept whole", "split the block that starts the next page, or move something short in front of it")
LARGE_EMPTY_BAND = IssueKind("LARGE_EMPTY_BAND", WARNING, "a wide empty band separates two blocks of one page", "remove the space, or place the two blocks next to each other")
BALANCE_ISSUE_KINDS = (PAGE_SPARSE, LAST_PAGE_SPARSE, PAGE_ENDS_EARLY, LARGE_EMPTY_BAND)


def balance_issues(pages: list[PageMeasure]) -> list[Issue]:
    issues = []
    if len(pages) == 1 and pages[0].fill < SPARSE_PAGE_FILL:
        issues.append(PAGE_SPARSE.issue(f"the page is filled {pages[0].fill:.0%}; content ends above {SPARSE_PAGE_FILL:.0%} of the body", "page 1"))
    if len(pages) > 1:
        issues.extend(multi_page_issues(pages))
    issues.extend(LARGE_EMPTY_BAND.issue(f"page {page.number} has an empty band of {page.gap_ratio:.0%} of the body between two blocks", f"page {page.number}") for page in pages if page.gap_ratio > LARGE_EMPTY_BAND_RATIO)
    return issues


def multi_page_issues(pages: list[PageMeasure]) -> list[Issue]:
    last = pages[-1]
    issues = [PAGE_ENDS_EARLY.issue(f"page {page.number} ends at {page.fill:.0%} of the body and another page follows", f"page {page.number}") for page in pages[:-1] if page.fill < EARLY_PAGE_END_FILL]
    if is_sparse_last_page(last):
        issues.append(LAST_PAGE_SPARSE.issue(f"the last page is filled {last.fill:.0%}", f"page {last.number}"))
    return issues


def is_sparse_last_page(page: PageMeasure) -> bool:
    return page.fill < NEARLY_EMPTY_LAST_PAGE_FILL or (page.fill < ORPHAN_LAST_PAGE_FILL and page.text_lines is not None and page.text_lines <= ORPHAN_LAST_PAGE_LINES)


def balance_details(pages: list[PageMeasure]) -> dict:
    return {
        "pageFill": [round(page.fill, 2) for page in pages],
        "lastPageFill": round(pages[-1].fill, 2) if pages else None,
        "largestEmptyBand": round(max((page.gap_ratio for page in pages), default=0.0), 2),
    }


def is_schema_document(path: Path | str) -> bool:
    return bool(read_source(path).get("schema"))
