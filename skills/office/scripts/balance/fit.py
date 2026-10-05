from __future__ import annotations

from typing import Callable

from balance.measure import PageMeasure
from balance.rhythm import Rhythm
from balance.tokens import GROWN_PAGE_FILL, LIFT_SHARE_OF_FREE_SPACE, SEARCH_STEPS, SHORT_PAGE_FILL, SPARSE_LAST_PAGE_FILL

Draw = Callable[[Rhythm], list[PageMeasure]]


def fit_rhythm(draw: Draw) -> Rhythm:
    neutral = Rhythm()
    pages = draw(neutral)
    if len(pages) == 1 and pages[0].fill < SHORT_PAGE_FILL:
        return grown(draw)
    if len(pages) > 1 and pages[-1].fill < SPARSE_LAST_PAGE_FILL:
        return tightened(draw, len(pages))
    return neutral


def grown(draw: Draw) -> Rhythm:
    def fits(airiness: float) -> bool:
        pages = draw(Rhythm(airiness))
        return len(pages) == 1 and pages[0].fill <= GROWN_PAGE_FILL

    airiness = 1.0 if fits(1.0) else bisect_largest(fits)
    pages = draw(Rhythm(airiness))
    free_points = (1 - pages[0].fill) * pages[0].body_height
    return Rhythm(airiness, LIFT_SHARE_OF_FREE_SPACE * free_points)


def tightened(draw: Draw, page_count: int) -> Rhythm:
    def fits(tightness: float) -> bool:
        return len(draw(Rhythm(-tightness))) < page_count

    if not fits(1.0):
        return Rhythm()
    return Rhythm(-bisect_smallest(fits))


def bisect_largest(accepts: Callable[[float], bool]) -> float:
    low, high = 0.0, 1.0
    for _ in range(SEARCH_STEPS):
        middle = (low + high) / 2
        low, high = (middle, high) if accepts(middle) else (low, middle)
    return low


def bisect_smallest(accepts: Callable[[float], bool]) -> float:
    low, high = 0.0, 1.0
    for _ in range(SEARCH_STEPS):
        middle = (low + high) / 2
        low, high = (low, middle) if accepts(middle) else (middle, high)
    return high
