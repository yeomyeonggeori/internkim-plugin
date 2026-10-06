# Adapted from GenOffice packages/pipelines/src/slides/outline.ts (Apache-2.0, Copyright 2026 Mainfunc, Inc.); see NOTICE.
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import pathlib

from core.office_result import ERROR, WARNING, Issue, IssueKind
from core.text_checks import PLACEHOLDER_LEFT, PLACEHOLDER_PATTERN
from charts.numbers import chart_number
from deck.chart_data import spaced_unit
from deck.deck_kit import KIT_PATH
from powerpoint.definitions import SLIDE_COUNT_MISMATCH


OUTLINE_FILE_NAME = "outline.json"
PAGES_DIRECTORY_NAME = "pages"
LIBRARY = json.loads((KIT_PATH / "layouts.json").read_text(encoding="utf-8"))
LAYOUTS = LIBRARY["layouts"]
PAGE_TYPES = tuple(LIBRARY["types"])
BODY_TYPES = ("content", "data")
VARIETY_MINIMUM = 3
VARIETY_MINIMUM_BODY_PAGES = 4

OUTLINE_INVALID = IssueKind("OUTLINE_INVALID", ERROR, "outline.json is not the outline shape", 'write {"core_hook": "...", "pages": [{"title": "...", "type": "cover", "brief": ["..."], "photos": []}]} as references/deck.md shows')
OUTLINE_INCOMPLETE = IssueKind("OUTLINE_INCOMPLETE", ERROR, "the outline lacks a value every deck needs", "add the value the message names")
PHOTO_NOT_LISTED = IssueKind("PHOTO_NOT_LISTED", ERROR, "an outline page plans a photo that is not one of the images office guide design lists", "use a path office guide design lists, or plan the page without a photo")
LAYOUT_INVALID = IssueKind("LAYOUT_INVALID", ERROR, "an outline page names a layout that is not in the library for its type, or a photo layout for a page without a photo", "choose a layout office guide design lists for the page's type; photo layouts only for a page that plans a photo")
LAYOUT_REPEATED = IssueKind("LAYOUT_REPEATED", ERROR, "two body pages in a row share one layout", "vary the composition: give the second page another layout its content fits")
LAYOUT_VARIETY = IssueKind("LAYOUT_VARIETY", ERROR, f"the body pages use fewer than {VARIETY_MINIMUM} layouts", f"give the body pages at least {VARIETY_MINIMUM} different layouts, each chosen from its page's content")
FIGURE_INVALID = IssueKind("FIGURE_INVALID", ERROR, "an outline figure lacks its label, a plain number as its value, or its unit", 'write each figure as {"label": "what it measures", "value": "64", "unit": "곳"}; the unit is "" only for a bare count, and a figure of a chart with several series names it in "series"')
OUTLINE_ORDER = IssueKind("OUTLINE_ORDER", WARNING, "the first page is not a cover or the last page is not a closing page", "open with a cover and end with the decision or next step, unless the request asks otherwise")
OUTLINE_ISSUE_KINDS = (OUTLINE_INVALID, OUTLINE_INCOMPLETE, FIGURE_INVALID, PHOTO_NOT_LISTED, LAYOUT_INVALID, LAYOUT_REPEATED, LAYOUT_VARIETY, OUTLINE_ORDER)


@dataclass(frozen=True)
class OutlineFigure:
    label: str
    value: str
    unit: str | None
    series: str = ""

    @property
    def number(self) -> float | None:
        return chart_number(self.value)

    def shown(self) -> str:
        return " ".join(part for part in (self.label, self.series, f"{self.value}{spaced_unit(self.unit or '')}") if part)

    def to_json(self) -> dict:
        return {"label": self.label, "value": self.value, "unit": self.unit} | ({"series": self.series} if self.series else {})


@dataclass(frozen=True)
class OutlinePage:
    title: str
    type: str
    brief: tuple[str, ...]
    photos: tuple[str, ...]
    layout: str = ""
    figures: tuple[OutlineFigure, ...] = ()

    @property
    def is_body(self) -> bool:
        return self.type in BODY_TYPES

    def figure(self, series: str, label: str) -> OutlineFigure | None:
        return next((figure for figure in self.figures if (figure.series, figure.label) == (series, label)), None)

    def to_json(self) -> dict:
        record = {"title": self.title, "type": self.type, "brief": list(self.brief), "figures": [figure.to_json() for figure in self.figures], "photos": list(self.photos)}
        return record | ({"layout": self.layout} if self.layout else {})


@dataclass(frozen=True)
class Outline:
    core_hook: str
    pages: tuple[OutlinePage, ...]

    def to_json(self) -> dict:
        return {"core_hook": self.core_hook, "pages": [page.to_json() for page in self.pages]}

    def with_layouts(self, layouts: list[str]) -> "Outline":
        return replace(self, pages=tuple(replace(page, layout=layout) for page, layout in zip(self.pages, layouts)))


def page_location(index: int) -> str:
    return f"outline page {index + 1}"


def read_outline(path: pathlib.Path) -> tuple[Outline | None, list[Issue]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as reason:
        return None, [OUTLINE_INVALID.issue(f"{path.name} cannot be read as JSON: {reason}", path.name)]
    if not isinstance(document, dict) or not isinstance(document.get("pages"), list) or not document["pages"]:
        return None, [OUTLINE_INVALID.issue(f'{path.name} has no "pages" list', path.name)]
    return Outline(text_of(document.get("core_hook")), tuple(outline_page(entry) for entry in document["pages"])), []


def text_of(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def texts_of(value: object) -> tuple[str, ...]:
    entries = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    return tuple(text for text in (text_of(entry) for entry in entries) if text)


def outline_page(entry: object) -> OutlinePage:
    fields = entry if isinstance(entry, dict) else {}
    figures = fields.get("figures") if isinstance(fields.get("figures"), list) else []
    return OutlinePage(text_of(fields.get("title")), text_of(fields.get("type")), texts_of(fields.get("brief")), texts_of(fields.get("photos")), text_of(fields.get("layout")), tuple(outline_figure(figure) for figure in figures))


def outline_figure(entry: object) -> OutlineFigure:
    fields = entry if isinstance(entry, dict) else {}
    value = fields.get("value")
    unit = fields.get("unit")
    return OutlineFigure(text_of(fields.get("label")), str(value).strip() if isinstance(value, (int, float, str)) and not isinstance(value, bool) else "", unit.strip() if isinstance(unit, str) else None, text_of(fields.get("series")))


def write_outline(path: pathlib.Path, outline: Outline) -> None:
    path.write_text(json.dumps(outline.to_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def outline_issues(outline: Outline, listed_photos: set[str], requested_page_count: int | None) -> list[Issue]:
    issues = [] if outline.core_hook else [OUTLINE_INCOMPLETE.issue('"core_hook" is missing: one sentence with tension, a number or a counter-intuitive contrast, from the request', "outline")]
    for index, page in enumerate(outline.pages):
        issues += page_issues(index, page, listed_photos)
    issues += placeholder_issues(outline)
    issues += count_issues(outline, requested_page_count)
    return issues + order_issues(outline)


def page_issues(index: int, page: OutlinePage, listed_photos: set[str]) -> list[Issue]:
    location = page_location(index)
    missing = [name for name, value in (("title", page.title), ("brief", page.brief)) if not value]
    issues = [OUTLINE_INCOMPLETE.issue(f'{location} has no "{name}"', location) for name in missing]
    if page.type not in PAGE_TYPES:
        issues.append(OUTLINE_INCOMPLETE.issue(f'{location} "type" is "{page.type}"; it is one of {", ".join(PAGE_TYPES)}', location))
    issues += figure_issues(location, page)
    unlisted = [photo for photo in page.photos if photo not in listed_photos]
    return issues + [PHOTO_NOT_LISTED.issue(f"{location} plans {photo}, which office guide design does not list", location) for photo in unlisted]


def figure_issues(location: str, page: OutlinePage) -> list[Issue]:
    issues = []
    for figure in page.figures:
        problems = [problem for problem, is_missing in (("no label", not figure.label), (f'value "{figure.value}" is not a plain number', figure.number is None), ('no "unit"', figure.unit is None)) if is_missing]
        if problems:
            issues.append(FIGURE_INVALID.issue(f"{location} figure {figure.label or figure.value or '?'}: {', '.join(problems)}", location))
    keys = [(figure.series, figure.label) for figure in page.figures]
    repeated = sorted({label for series, label in keys if keys.count((series, label)) > 1})
    return issues + [FIGURE_INVALID.issue(f'{location} names the figure "{label}" twice; give each figure its own label, or its series', location) for label in repeated]


def placeholder_issues(outline: Outline) -> list[Issue]:
    issues = []
    for index, page in enumerate(outline.pages):
        found = sorted({match for text in (page.title, *page.brief) for match in PLACEHOLDER_PATTERN.findall(text)})
        if found:
            issues.append(PLACEHOLDER_LEFT.issue(f"{page_location(index)} still holds {', '.join(found)}", page_location(index), suggestion="take every figure and name from the request or its attachments; leave out what they do not state"))
    return issues


def count_issues(outline: Outline, requested_page_count: int | None) -> list[Issue]:
    if requested_page_count is None or requested_page_count == len(outline.pages):
        return []
    return [SLIDE_COUNT_MISMATCH.issue(f"the outline has {len(outline.pages)} pages, but {requested_page_count} were requested", "outline")]


def order_issues(outline: Outline) -> list[Issue]:
    pages = outline.pages
    issues = [] if pages[0].type == "cover" else [OUTLINE_ORDER.issue("the first page is not a cover", page_location(0))]
    if len(pages) > 2 and pages[-1].type != "closing":
        issues.append(OUTLINE_ORDER.issue("the last page is not a closing page", page_location(len(pages) - 1)))
    return issues


def valid_layouts(page: OutlinePage) -> list[str]:
    return [name for name, layout in LAYOUTS.items() if layout["type"] == page.type and (page.photos or not layout.get("photo"))]


def layout_issues(outline: Outline) -> list[Issue]:
    issues = []
    for index, page in enumerate(outline.pages):
        if page.type in PAGE_TYPES and page.layout not in valid_layouts(page):
            issues.append(LAYOUT_INVALID.issue(f'{page_location(index)} layout "{page.layout}"; a {page.type} page{" with a photo" if page.photos else " without a photo"} takes one of {", ".join(valid_layouts(page))}', page_location(index)))
    return issues + repeat_issues(outline) + variety_issues(outline)


def consecutive_body_pairs(pages: tuple[OutlinePage, ...]) -> list[int]:
    return [index for index in range(1, len(pages)) if pages[index].is_body and pages[index - 1].is_body]


def repeat_issues(outline: Outline) -> list[Issue]:
    pages = outline.pages
    return [LAYOUT_REPEATED.issue(f"{page_location(index)} repeats {pages[index].layout}, the layout of the page before it", page_location(index)) for index in consecutive_body_pairs(pages) if pages[index].layout and pages[index].layout == pages[index - 1].layout]


def variety_issues(outline: Outline) -> list[Issue]:
    body = [page.layout for page in outline.pages if page.is_body]
    if len(body) < VARIETY_MINIMUM_BODY_PAGES or len(set(body)) >= VARIETY_MINIMUM:
        return []
    return [LAYOUT_VARIETY.issue(f"{len(body)} body pages use only {', '.join(sorted(set(body)))}", "outline")]
