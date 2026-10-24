from __future__ import annotations

from typing import Callable

from balance.measure import PageMeasure
from balance.rhythm import Rhythm
from balance.tokens import SEARCH_STEPS, SPARSE_LAST_PAGE_FILL

Draw = Callable[[Rhythm], list[PageMeasure]]


def fit_rhythm(draw: Draw) -> Rhythm:
    pages = draw(Rhythm())
    if len(pages) > 1 and pages[-1].fill < SPARSE_LAST_PAGE_FILL:
        return tightened(draw, len(pages))
    return Rhythm()


def tightened(draw: Draw, page_count: int) -> Rhythm:
    def removes_the_last_page(tightness: float) -> bool:
        return len(draw(Rhythm(tightness))) < page_count

    if not removes_the_last_page(1.0):
        return Rhythm()
    return Rhythm(smallest_accepted(removes_the_last_page))


def smallest_accepted(accepts: Callable[[float], bool]) -> float:
    low, high = 0.0, 1.0
    for _ in range(SEARCH_STEPS):
        middle = (low + high) / 2
        low, high = (low, middle) if accepts(middle) else (middle, high)
    return high
