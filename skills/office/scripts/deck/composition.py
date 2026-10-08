from __future__ import annotations

from dataclasses import dataclass

from core.design_rules import DECK_RULE_KINDS, threshold_of
from core.office_result import Issue


REPEATED_COMPOSITION = DECK_RULE_KINDS["REPEATED_COMPOSITION"]
COMPOSITION_THRESHOLD = threshold_of(REPEATED_COMPOSITION.code)
MAXIMUM_PAGES_PER_COMPOSITION = COMPOSITION_THRESHOLD["maximumPages"]


@dataclass(frozen=True)
class PageComposition:
    number: int
    page_type: str
    measured: dict | None

    @property
    def shape(self) -> str | None:
        if self.measured is None or self.page_type not in COMPOSITION_THRESHOLD["pageTypes"]:
            return None
        return f"{self.measured['arrangement']} {self.measured['rows']}x{self.measured['columns']}"

    def described(self) -> str:
        measured = self.measured or {}
        if measured.get("arrangement") == "grid":
            return f"a {measured['rows']}x{measured['columns']} grid of equal cards"
        return f"one {measured.get('arrangement')} of {measured.get('count')} equal cards"


def page_list(numbers: list[int]) -> str:
    named = [f"page {number}" for number in numbers]
    return named[0] if len(named) == 1 else f"{', '.join(named[:-1])} and {named[-1]}"


def repeats(page: PageComposition, earlier: list[PageComposition]) -> list[int]:
    alike = [other.number for other in earlier if other.shape == page.shape]
    follows_alike = page.number - 1 in alike
    return alike if follows_alike or len(alike) >= MAXIMUM_PAGES_PER_COMPOSITION else []


def repeated_composition_issues(pages: list[PageComposition]) -> list[Issue]:
    issues = []
    for index, page in enumerate(pages):
        if page.shape is None:
            continue
        alike = repeats(page, pages[:index])
        if alike:
            selector = (page.measured or {}).get("selector", "")
            detail = f"page {page.number} sets its content as {page.described()} ({selector}), as {page_list(alike)} already do{'es' if len(alike) == 1 else ''}"
            issues.append(REPEATED_COMPOSITION.issue(f"{REPEATED_COMPOSITION.meaning}: {detail}", f"page {page.number}"))
    return issues
