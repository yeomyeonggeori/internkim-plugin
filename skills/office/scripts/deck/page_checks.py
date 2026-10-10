from __future__ import annotations

from dataclasses import dataclass
import pathlib
import re

from charts.kinds import KIT_STACKED_CHARTS, is_round_kind, single_slice_problem
from charts.numbers import chart_number, split_chart_list
from core.css_color import parse_css_color
from core.office_result import ERROR, WARNING, Issue, IssueKind
from core.office_schema import closest_name, names_suggestion
from core.text_checks import PLACEHOLDER_LEFT, PLACEHOLDER_PATTERN
from deck.chart_data import axis_unit_texts, chart_series, series_axes
from deck.deck_kit import chart_types, icon_names
from deck.deck_source import Element, find_all, normalized_text, visible_text
from deck.design_system import DesignSystem, palette_of
from deck.outline import OutlinePage
from deck.resource_inlining import resolve_resource_path


DONUT_SLICE_MAXIMUM = 8
ALWAYS_ALLOWED_COLORS = {"FFFFFF", "000000"}
COLOR_LITERAL_PATTERN = re.compile(r"#[0-9A-Fa-f]{3,8}\b|(?:rgba?|hsla?)\([^)]*\)")
DECLARATION_PATTERN = re.compile(r"([-\w]+)\s*:\s*([^;{}]+)")
CONTENT_TAGS = {"img", "figure", "svg", "table"}

SLIDE_WITHOUT_CONTENT = IssueKind("SLIDE_WITHOUT_CONTENT", ERROR, "a page has no visible text, image or chart", "give the page the content its outline entry names")
CHART_DATA_INVALID = IssueKind("CHART_DATA_INVALID", ERROR, "a chart's data attributes do not parse or do not line up", "give data-labels and data-values (or data-series) the same number of plain numbers")
IMAGE_NOT_FOUND = IssueKind("IMAGE_NOT_FOUND", ERROR, "an image is remote or its file does not exist, so the page would show an empty box", "point src at an image office guide design lists, or remove the image")
ICON_UNKNOWN = IssueKind("ICON_UNKNOWN", ERROR, "a data-icon names an icon the kit does not ship", "use a name office guide slides lists under Icons, or drop the data-icon")
OFF_PALETTE_COLOR = IssueKind("OFF_PALETTE_COLOR", WARNING, "the page paints with a color the style sheet does not name", "use the style sheet's colors through var(--accent), var(--text) and the other tokens, or add the color to DESIGN.md")
CHART_NOT_FROM_FIGURES = IssueKind("CHART_NOT_FROM_FIGURES", ERROR, "a chart plots a value that is not one of its page's outline figures, or not as the figure states it", "plot the page's outline figures: each data-labels entry is a figure's label, each value that figure's value, data-unit its unit, and a data-series name its series")
CHART_MIXED_UNITS = IssueKind("CHART_MIXED_UNITS", ERROR, "one chart axis plots figures whose units differ, so a count and a share read as one kind of number", "keep one unit per axis: chart the figures that share a unit and show the other apart, such as a KPI for the count beside a chart of the percentages")
PAGE_TITLE_UNBOUND = IssueKind("PAGE_TITLE_UNBOUND", ERROR, "the page does not hold exactly one element with data-title, where the build writes its outline entry's title", "write the title as one empty element, such as <h1 data-title></h1>; the build fills in the outline entry's title")
PAGE_DIFFERS_FROM_OUTLINE = IssueKind("PAGE_DIFFERS_FROM_OUTLINE", WARNING, "the page does not show the photo its outline entry plans", "compose the page from its outline entry in its layout")
PAGE_CHECK_ISSUE_KINDS = (SLIDE_WITHOUT_CONTENT, CHART_DATA_INVALID, CHART_NOT_FROM_FIGURES, CHART_MIXED_UNITS, PAGE_TITLE_UNBOUND, IMAGE_NOT_FOUND, ICON_UNKNOWN, OFF_PALETTE_COLOR, PAGE_DIFFERS_FROM_OUTLINE)


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
        + chart_figure_issues(page)
        + title_issues(page)
        + icon_issues(page)
        + image_issues(page, directory)
        + placeholder_issues(page)
        + palette_issues(page, system)
        + agreement_warnings(page)
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
    problems = [series_problem(name or "data-values", values, len(labels)) for name, values in series]
    problems += shape_problems(chart_type, labels, series, attributes.get("data-highlight"))
    return [problem for problem in problems if problem]


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
    return [*problems, single_slice_problem(chart_type, len(labels))]


def chart_figure_issues(page: Page) -> list[Issue]:
    issues = []
    for figure in page.charts():
        problems, units_by_axis = plotted_figure_problems(page.entry, figure.attributes)
        issues += [CHART_NOT_FROM_FIGURES.issue(f"{page.location}: {problem}", page.location) for problem in problems]
        issues += axis_unit_issues(page, figure.attributes, units_by_axis)
    return issues


def plotted_figure_problems(entry: OutlinePage, attributes: dict[str, str]) -> tuple[list[str], dict[int, dict[str, str]]]:
    series = chart_series(attributes)
    if isinstance(series, str):
        return [], {}
    labels = split_chart_list(attributes.get("data-labels", ""))
    axes = series_axes(attributes["data-chart"].strip(), len(series))
    problems, units_by_axis = [], {}
    for (name, values), axis in zip(series, axes):
        for label, value in zip(labels, values):
            figure = entry.figure(name, label)
            if figure is None:
                problems.append(f'"{" ".join(part for part in (label, name) if part)}" is not a figure of this page\'s outline entry; its figures are {listed_figures(entry)}')
            elif chart_number(value) != figure.number:
                problems.append(f'"{label}" plots {value}, but its figure is {figure.value}')
            else:
                units_by_axis.setdefault(axis, {})[figure.shown()] = figure.unit or ""
    return problems, units_by_axis


def listed_figures(entry: OutlinePage) -> str:
    return ", ".join(figure.shown() for figure in entry.figures) or "none"


def axis_unit_issues(page: Page, attributes: dict[str, str], units_by_axis: dict[int, dict[str, str]]) -> list[Issue]:
    issues = []
    written = axis_unit_texts(attributes["data-chart"].strip(), attributes.get("data-unit", ""))
    for axis, units in sorted(units_by_axis.items()):
        if len(set(units.values())) > 1:
            issues.append(CHART_MIXED_UNITS.issue(f"{page.location}: one axis plots {', '.join(units)}", page.location))
        elif written[axis] != next(iter(units.values())):
            issues.append(CHART_NOT_FROM_FIGURES.issue(f'{page.location}: data-unit gives "{written[axis]}", but the figures it plots are in "{next(iter(units.values()))}"', page.location))
    return issues


def title_issues(page: Page) -> list[Issue]:
    count = sum(1 for element in (page.element, *page.element.descendants()) if "data-title" in element.attributes)
    return [] if count == 1 else [PAGE_TITLE_UNBOUND.issue(f"{page.location} has {count} elements with data-title", page.location)]


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


def agreement_warnings(page: Page) -> list[Issue]:
    differences = []
    if page.entry.photos and not page.images():
        differences.append(f"the outline plans {len(page.entry.photos)} photo(s) and the page shows none")
    return [PAGE_DIFFERS_FROM_OUTLINE.issue(f"{page.location}: {difference}", page.location) for difference in differences]
