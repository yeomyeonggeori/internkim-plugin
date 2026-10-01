from __future__ import annotations

from core.office_operations import TARGET_NOT_FOUND
from core.office_result import INVALID_ARGUMENTS, OfficeFailure


def select_slides(selection: str, slide_count: int) -> list[int]:
    if not selection.strip():
        return list(range(1, slide_count + 1))
    numbers = set()
    for part in selection.split(","):
        numbers.update(expand_range(part.strip(), slide_count))
    return sorted(numbers)


def expand_range(part: str, slide_count: int) -> range:
    first_text, separator, last_text = part.partition("-")
    if not first_text.isdigit() or separator and not last_text.isdigit():
        raise OfficeFailure(INVALID_ARGUMENTS.issue(f"--slides: {part!r} is not a slide number or range", "--slides", "pass slides such as 2,4-6"))
    first, last = int(first_text), int(last_text) if separator else int(first_text)
    for number in (first, last):
        if not 1 <= number <= slide_count:
            raise OfficeFailure(TARGET_NOT_FOUND.issue(f"--slides: slide {number} does not exist", "--slides", f"use slides from 1 to {slide_count}"))
    return range(first, last + 1)
