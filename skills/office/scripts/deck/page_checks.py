from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import pathlib
import re

from charts.kinds import KIT_STACKED_CHARTS, is_round_kind
from charts.numbers import chart_number, split_chart_list
from core.css_color import parse_css_color
from core.office_result import ERROR, WARNING, Issue, IssueKind
from core.office_schema import closest_name, names_suggestion
from core.text_checks import PLACEHOLDER_LEFT, PLACEHOLDER_PATTERN
from deck.deck_kit import chart_types, icon_names
from deck.deck_source import Element, find_all, normalized_text, visible_text
from deck.design_system import DesignSystem, palette_of
from deck.outline import LAYOUTS, OutlinePage
from deck.resource_inlining import resolve_resource_path


DONUT_SLICE_MAXIMUM = 8
ALWAYS_ALLOWED_COLORS = {"FFFFFF", "000000"}
COLOR_LITERAL_PATTERN = re.compile(r"#[0-9A-Fa-f]{3,8}\b|(?:rgba?|hsla?)\([^)]*\)")
DECLARATION_PATTERN = re.compile(r"([-\w]+)\s*:\s*([^;{}]+)")
LOOSE_PATTERN = re.compile(r"[\W_]+")
CONTENT_TAGS = {"img", "figure", "svg", "table"}
STRUCTURE_TAGS = {"style", "script", "aside", "br"}

SLIDE_WITHOUT_CONTENT = IssueKind("SLIDE_WITHOUT_CONTENT", ERROR, "a page has no visible text, image or chart", "give the page the content its outline entry names")
CHART_DATA_INVALID = IssueKind("CHART_DATA_INVALID", ERROR, "a chart's data attributes do not parse or do not line up", "give data-labels and data-values (or data-series) the same number of plain numbers")
IMAGE_NOT_FOUND = IssueKind("IMAGE_NOT_FOUND", ERROR, "an image is remote or its file does not exist, so the page would show an empty box", "point src at an image office guide design lists, or remove the image")
ICON_UNKNOWN = IssueKind("ICON_UNKNOWN", ERROR, "a data-icon names an icon the kit does not ship", "use a name office guide slides lists under Icons, or drop the data-icon")
OFF_PALETTE_COLOR = IssueKind("OFF_PALETTE_COLOR", ERROR, "the page paints with a color the style sheet does not name", "use the style sheet's colors through var(--accent), var(--text) and the other tokens, or add the color to DESIGN.md")
LAYOUT_NOT_MET = IssueKind("LAYOUT_NOT_MET", ERROR, "the page lacks a part its layout is made of: the photo of a photo layout or the chart of chart_with_insight", "give the page that part from its outline entry")
PAGE_DIFFERS_FROM_OUTLINE = IssueKind("PAGE_DIFFERS_FROM_OUTLINE", WARNING, "the page does not show what its outline entry plans: its title, its planned photo or the blocks its layout is made of", "compose the page from its outline entry in its layout")
PAGE_CHECK_ISSUE_KINDS = (SLIDE_WITHOUT_CONTENT, CHART_DATA_INVALID, IMAGE_NOT_FOUND, ICON_UNKNOWN, OFF_PALETTE_COLOR, LAYOUT_NOT_MET, PAGE_DIFFERS_FROM_OUTLINE)


@dataclass(frozen=True)
class Page:
    number: int
    element: Element
    entry: OutlinePage

    @property
    def location(self) -> str:
        return f"page {self.number}"

    def text(self) -> str:
        return normalized_text(visible_text(self.element))

    def images(self) -> list[Element]:
        return [image for image in find_all(self.element, "img") if "data-logo" not in image.attributes]

    def charts(self) -> list[Element]:
        return [figure for figure in find_all(self.element, "figure") if "data-chart" in figure.attributes]


def page_issues(page: Page, directory: pathlib.Path, system: DesignSystem) -> list[Issue]:
    return (
        empty_page_issues(page)
        + chart_issues(page)
        + icon_issues(page)
        + image_issues(page, directory)
        + placeholder_issues(page)
        + palette_issues(page, system)
        + layout_issues(page)
    )


def empty_page_issues(page: Page) -> list[Issue]:
    if page.text() or any(element.tag in CONTENT_TAGS for element in page.element.descendants()):
        return []
    return [SLIDE_WITHOUT_CONTENT.issue(f"{page.location} shows nothing", page.location)]


def icon_issues(page: Page) -> list[Issue]:
    names = [element.attributes["data-icon"].strip() for element in page.element.descendants() if "data-icon" in element.attributes]
    return [ICON_UNKNOWN.issue(f'{page.location}: data-icon="{name}" is not an icon the kit ships', page.location, suggestion=names_suggestion(name, icon_names())) for name in names if name not in icon_names()]


def chart_issues(page: Page) -> list[Issue]:
    issues = []
    for figure in page.charts():
        chart_type = figure.attributes["data-chart"].strip()
        if chart_type not in chart_types():
            issues.append(CHART_DATA_INVALID.issue(f'{page.location}: data-chart="{chart_type}" is not one of {", ".join(chart_types())}', page.location, suggestion=names_suggestion(chart_type, chart_types())))
            chart_type = closest_name(chart_type, chart_types()) or ""
        issues += [CHART_DATA_INVALID.issue(f"{page.location}: {problem}", page.location) for problem in chart_problems(chart_type, figure.attributes)]
    return issues


def chart_problems(chart_type: str, attributes: dict[str, str]) -> list[str]:
    labels = split_chart_list(attributes.get("data-labels", ""))
    if not labels:
        return ["data-labels is empty"]
    series = chart_series(attributes)
    if isinstance(series, str):
        return [series]
    problems = [series_problem(name, values, len(labels)) for name, values in series]
    problems += shape_problems(chart_type, labels, series, attributes.get("data-highlight"))
    return [problem for problem in problems if problem]


def chart_series(attributes: dict[str, str]) -> list[tuple[str, list[str]]] | str:
    if attributes.get("data-series", "").strip():
        series = []
        for part in [part.strip() for part in attributes["data-series"].split(";") if part.strip()]:
            name, separator, values = part.partition(":")
            if not separator:
                return f'data-series part "{part}" has no "name:" before its numbers'
            series.append((name.strip(), split_chart_list(values)))
        return series
    if attributes.get("data-values", "").strip():
        return [("data-values", split_chart_list(attributes["data-values"]))]
    return "the chart has neither data-values nor data-series"


def series_problem(name: str, values: list[str], label_count: int) -> str:
    not_numbers = [value for value in values if not is_number(value)]
    if not_numbers:
        return f"{name} holds {', '.join(not_numbers[:3])}, which are not plain numbers; put the unit in data-unit"
    if len(values) != label_count:
        return f"{name} has {len(values)} numbers for {label_count} labels{thousands_hint(values)}"
    return ""


def thousands_hint(values: list[str]) -> str:
    if not any(len(value) == 3 and value.isdigit() for value in values[1:]):
        return ""
    return '; if a comma groups thousands, separate the values with a comma and a space ("1,200, 1,350") or write them without the grouping comma ("1200, 1350")'


def shape_problems(chart_type: str, labels: list[str], series: list[tuple[str, list[str]]], highlight: str | None) -> list[str]:
    problems = []
    if highlight is not None and highlight.strip() not in labels:
        problems.append(f'data-highlight="{highlight}" is not one of the labels')
    if chart_type == "combo" and len(series) < 2:
        problems.append("a combo chart takes data-series with the column series first and the line series last")
    if chart_type == "scatter" and len(series) != 2:
        problems.append('a scatter chart takes exactly two series in data-series: the horizontal axis first, then the vertical, such as "Revenue: 12, 30; Margin: 8, 11"')
    if chart_type in KIT_STACKED_CHARTS and any(value < 0 for _, values in series for value in numbers_in(values)):
        problems.append(f"a {chart_type} chart stacks its series, so every value must be zero or more")
    if not is_round_kind(chart_type):
        return problems
    values = numbers_in(series[0][1])
    if len(series) > 1:
        problems.append(f"a {chart_type} chart takes one series in data-values")
    if any(value < 0 for value in values) or sum(values) <= 0:
        problems.append(f"a {chart_type} chart needs positive shares")
    if len(labels) > DONUT_SLICE_MAXIMUM:
        problems.append(f"{len(labels)} slices are too many to read; group the smallest into one")
    return problems


def numbers_in(values: list[str]) -> list[float]:
    return [chart_number(value) for value in values if is_number(value)]


def is_number(text: str) -> bool:
    return chart_number(text) is not None


def image_issues(page: Page, directory: pathlib.Path) -> list[Issue]:
    problems = [image_problem(image.attributes.get("src", "").strip(), directory) for image in page.images()]
    return [IMAGE_NOT_FOUND.issue(f"{page.location}: {problem}", page.location) for problem in problems if problem]


def image_problem(source: str, directory: pathlib.Path) -> str:
    if not source:
        return "an <img> has no src"
    if source.startswith("data:"):
        return ""
    if source.startswith(("http:", "https:")):
        return f"{source} is remote and the build does not fetch it"
    resolved = resolve_resource_path(source, directory)
    return "" if resolved is not None and resolved.exists() else f"{source} does not exist"


def placeholder_issues(page: Page) -> list[Issue]:
    found = PLACEHOLDER_PATTERN.findall(page.text())
    if not found:
        return []
    return [PLACEHOLDER_LEFT.issue(f"{page.location} still shows {', '.join(sorted(set(found)))}", page.location, suggestion="replace it with the real value from the outline entry, or leave it out")]


def palette_issues(page: Page, system: DesignSystem) -> list[Issue]:
    palette = {normalized_color(f"#{value}") for value in palette_of(system).values()} - {""}
    off_palette = colors_in(page_style_texts(page.element)) - palette - ALWAYS_ALLOWED_COLORS
    if not off_palette:
        return []
    listed = ", ".join(f"#{color}" for color in sorted(off_palette))
    palette_listed = ", ".join(sorted(f"#{color}" for color in palette))
    return [OFF_PALETTE_COLOR.issue(f"{page.location} uses {listed}, outside the style sheet", page.location, suggestion=f"{OFF_PALETTE_COLOR.default_suggestion()}; its colors are {palette_listed}")]


def page_style_texts(section: Element) -> list[str]:
    blocks = ["".join(child for child in style.children if isinstance(child, str)) for style in find_all(section, "style")]
    return blocks + [element.attributes["style"] for element in (section, *section.descendants()) if "style" in element.attributes]


def colors_in(style_texts: list[str]) -> set[str]:
    colors = set()
    for style_text in style_texts:
        for _, value in DECLARATION_PATTERN.findall(style_text):
            colors |= {normalized_color(literal) for literal in COLOR_LITERAL_PATTERN.findall(value) if parse_css_color(literal).alpha > 0}
    return colors - {""}


def normalized_color(literal: str) -> str:
    try:
        return parse_css_color(literal).hex_value
    except (ValueError, IndexError):
        return ""


def loose(text: str) -> str:
    return LOOSE_PATTERN.sub("", text).casefold()


def layout_issues(page: Page) -> list[Issue]:
    layout = LAYOUTS.get(page.entry.layout, {})
    issues = []
    if layout.get("photo") and not page.images():
        issues.append(LAYOUT_NOT_MET.issue(f"{page.location} is {page.entry.layout}, a photo layout, and shows no photo", page.location, suggestion=f"put {', '.join(page.entry.photos) or 'the planned photo'} in it"))
    if layout.get("chart") and not page.charts():
        issues.append(LAYOUT_NOT_MET.issue(f"{page.location} is {page.entry.layout} and shows no chart", page.location, suggestion="draw the brief's figures as a <figure data-chart>"))
    return issues + agreement_warnings(page, layout)


def agreement_warnings(page: Page, layout: dict) -> list[Issue]:
    differences = []
    if page.entry.title and loose(page.entry.title) not in loose(page.text()):
        differences.append(f'the outline title "{page.entry.title}" is not on the page')
    if page.entry.photos and not page.images():
        differences.append(f"the outline plans {len(page.entry.photos)} photo(s) and the page shows none")
    blocks = layout.get("parallelBlocks")
    if blocks and not has_parallel_blocks(page.element, *blocks):
        differences.append(f"{page.entry.layout} is made of {blocks[0]}{'' if blocks[0] == blocks[1] else ' to ' + str(blocks[1])} parallel blocks of one kind, and the page has no such group")
    return [PAGE_DIFFERS_FROM_OUTLINE.issue(f"{page.location}: {difference}", page.location) for difference in differences]


def has_parallel_blocks(section: Element, fewest: int, most: int) -> bool:
    for element in (section, *section.descendants()):
        kinds = Counter((child.tag, child.attributes.get("class", "").strip()) for child in element.child_elements() if child.tag not in STRUCTURE_TAGS)
        if any(fewest <= count <= most for count in kinds.values()):
            return True
    return False
