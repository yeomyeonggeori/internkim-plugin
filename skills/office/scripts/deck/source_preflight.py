from __future__ import annotations

import pathlib
import re

from deck_definitions import (
    DECK_BRIEF_MISSING,
    DESIGN_DOCUMENT_MISSING,
    DESIGN_SOURCE_MARKER_MISSING,
    NO_SLIDE_SECTIONS,
    REQUIRED_TEXT_LEDGER_MISSING,
    SLIDE_COUNT_MISMATCH,
    SOURCE_NOT_HTML,
)
from office_result import Issue, OfficeFailure
from slide_source import split_slide_sources


DESIGN_SOURCE_MARKER = "design-source: DESIGN.md"
REQUESTED_SLIDE_COUNT_PATTERNS = (
    r"(?im)^\s*slide\s*count\s*[:：-]\s*(\d{1,2})\b",
    r"(?im)^\s*slides?\s*[:：-]\s*(\d{1,2})\b",
    r"(?im)^\s*슬라이드\s*수\s*[:：-]\s*(\d{1,2})\b",
)


def read_checked_source(source_path: pathlib.Path) -> tuple[str, list[str]]:
    if source_path.suffix.casefold() != ".html":
        raise OfficeFailure(SOURCE_NOT_HTML.issue(f"{source_path.name} is not HTML; create slides.html or set SRC=yourfile.html", str(source_path)))
    source_text = source_path.read_text(encoding="utf-8")
    slide_sources = split_slide_sources(source_text)
    if not slide_sources:
        raise OfficeFailure(NO_SLIDE_SECTIONS.issue(f"{source_path.name} must contain at least one <section> slide", str(source_path)))
    return source_text, slide_sources


def preflight_issues(source_path: pathlib.Path, source_text: str, slide_count: int) -> list[Issue]:
    directory = source_path.parent
    issues = []
    if not (directory / "DESIGN.md").exists():
        issues.append(DESIGN_DOCUMENT_MISSING.issue("DESIGN.md missing; the build continues, but visual review may mark weak design identity"))
    if DESIGN_SOURCE_MARKER not in source_text:
        issues.append(DESIGN_SOURCE_MARKER_MISSING.issue(f"{source_path.name} should include {DESIGN_SOURCE_MARKER}", source_path.name))
    if not (directory / "required-visible-text.txt").exists():
        issues.append(REQUIRED_TEXT_LEDGER_MISSING.issue("required-visible-text.txt missing; manually verify required source facts before delivery"))
    return issues + deck_brief_issues(directory / "deck-brief.md", slide_count)


def deck_brief_issues(deck_brief_path: pathlib.Path, slide_count: int) -> list[Issue]:
    if not deck_brief_path.exists():
        return [DECK_BRIEF_MISSING.issue("deck-brief.md missing; the build continues without a slide-count cross-check")]
    requested_slide_count = extract_requested_slide_count(deck_brief_path.read_text(encoding="utf-8"))
    if requested_slide_count is None or requested_slide_count == slide_count:
        return []
    return [SLIDE_COUNT_MISMATCH.issue(f"slides.html has {slide_count} slide sections, but deck-brief.md says {requested_slide_count}")]


def extract_requested_slide_count(deck_brief_text: str) -> int | None:
    for pattern in REQUESTED_SLIDE_COUNT_PATTERNS:
        match = re.search(pattern, deck_brief_text)
        if match:
            return int(match.group(1))
    numbered_slide_items = re.findall(r"(?m)^\s*\d{1,2}\.\s+\S", deck_brief_text)
    if len(numbered_slide_items) >= 2:
        return len(numbered_slide_items)
    return None
