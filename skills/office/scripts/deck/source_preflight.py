from __future__ import annotations

import pathlib

from deck_definitions import NO_SLIDE_SECTIONS, SOURCE_NOT_HTML
from office_result import OfficeFailure
from slide_source import split_slide_sources


def read_checked_source(source_path: pathlib.Path) -> tuple[str, list[str]]:
    if source_path.suffix.casefold() != ".html":
        raise OfficeFailure(SOURCE_NOT_HTML.issue(f"{source_path.name} is not HTML; write slides.html or pass --source yourfile.html", str(source_path)))
    source_text = source_path.read_text(encoding="utf-8")
    slide_sources = split_slide_sources(source_text)
    if not slide_sources:
        raise OfficeFailure(NO_SLIDE_SECTIONS.issue(f"{source_path.name} must contain at least one <section> slide", str(source_path)))
    return source_text, slide_sources
