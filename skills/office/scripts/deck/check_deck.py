#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, replace
import pathlib
import re

from core.css_color import parse_css_color
from deck.deck_definitions import (
    CHART_DATA_INVALID,
    ICON_UNKNOWN,
    IMAGE_NOT_FOUND,
    NO_SLIDE_SECTIONS,
    OFF_PALETTE_COLOR,
    SLIDE_COUNT_MISMATCH,
    SLIDE_WITHOUT_CONTENT,
    SOURCE_NOT_HTML,
)
from charts.kinds import KIT_STACKED_CHARTS, is_round_kind
from charts.numbers import chart_number, split_chart_list
from deck.draft_claims import draft_claim_issues
from deck.deck_html import render_gate_issues
from deck.deck_kit import chart_types, icon_names
from deck.deck_preparation import prepare_deck
from deck.deck_source import Element, find_all, normalized_text, parse_source, style_texts, visible_text
from deck.design_system import DESIGN_FILE_NAME, DesignSystem, palette_of, read_design_system, token_issues
from core.office_arguments import route_arguments
from core.office_result import ERROR, WARNING, Issue, OfficeFailure, Result, run_command
from core.office_schema import closest_name, names_suggestion
from deck.resource_inlining import resolve_resource_path
from core.text_checks import PLACEHOLDER_PATTERN, PLACEHOLDER_LEFT, text_presence_issues


DONUT_SLICE_MAXIMUM = 8
ALWAYS_ALLOWED_COLORS = {"FFFFFF", "000000"}
COLOR_LITERAL_PATTERN = re.compile(r"#[0-9A-Fa-f]{3,8}\b|(?:rgba?|hsla?)\([^)]*\)")
DECLARATION_PATTERN = re.compile(r"([-\w]+)\s*:\s*([^;{}]+)")
HEX_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}\b")
CONTENT_TAGS = {"img", "figure", "svg", "table"}


@dataclass(frozen=True)
class CheckRequest:
    source_path: pathlib.Path
    requested_slide_count: int | None = None
    required_text: tuple[str, ...] = ()
    forbidden_text: tuple[str, ...] = ()
    is_blank_remake: bool = False


@dataclass(frozen=True)
class Slide:
    index: int
    element: Element

    @property
    def location(self) -> str:
        return f"slide {self.index}"

    @property
    def title(self) -> str:
        headings = [child for child in self.element.child_elements() if child.tag in ("h1", "h2")]
        return normalized_text(visible_text(headings[0])) if headings else ""

    def text(self) -> str:
        return normalized_text(visible_text(self.element))


def check_deck(request: CheckRequest) -> Result:
    if request.source_path.suffix.casefold() != ".html":
        raise OfficeFailure(SOURCE_NOT_HTML.issue(f"{request.source_path.name} is not HTML; write slides.html", str(request.source_path)))
    source_text = request.source_path.read_text(encoding="utf-8")
    root = parse_source(source_text)
    slides = [Slide(index, section) for index, section in enumerate(find_all(root, "section"), start=1)]
    if not slides:
        raise OfficeFailure(NO_SLIDE_SECTIONS.issue(f"{request.source_path.name} has no <section> slides", str(request.source_path)))
    system, design_issues = design_gate(request.source_path.parent)
    if has_errors(design_issues):
        return Result(summary=check_summary(slides, design_issues), output_path=str(request.source_path), issues=tuple(design_issues), details=check_details(slides))
    issues = design_issues + deck_issues(request, root, slides, system)
    if not request.is_blank_remake:
        issues += draft_claim_issues(source_text)
    if not has_errors(issues):
        issues += render_gate_issues(request.source_path, system)
    if request.is_blank_remake:
        issues = [demoted_to_warning(issue) for issue in issues]
    return Result(summary=check_summary(slides, issues), output_path=str(request.source_path), issues=tuple(issues), details=check_details(slides))


def demoted_to_warning(issue: Issue) -> Issue:
    return replace(issue, kind=replace(issue.kind, severity=WARNING)) if issue.kind.severity == ERROR else issue


def check_design(design_path: pathlib.Path) -> Result:
    system, issues = design_gate(design_path.parent, design_path.name)
    summary = check_summary([], issues) if has_errors(issues) else f"{design_path.name} passes the design gate: write slides.html within it, then run office check slides.html"
    return Result(summary=summary, output_path=str(design_path), issues=tuple(issues), details={"slideCount": 0})


def design_gate(directory: pathlib.Path, file_name: str = DESIGN_FILE_NAME) -> tuple[DesignSystem | None, list[Issue]]:
    system, issues = read_design_system(directory / file_name)
    return system, issues + (token_issues(system) if system else [])


def has_errors(issues: list[Issue]) -> bool:
    return any(issue.kind.severity == ERROR for issue in issues)


def deck_issues(request: CheckRequest, root: Element, slides: list[Slide], system: DesignSystem) -> list[Issue]:
    issues = slide_count_issues(request.requested_slide_count, slides)
    for slide in slides:
        issues += empty_slide_issues(slide) + chart_issues(slide) + icon_issues(slide) + image_issues(slide, request.source_path.parent) + placeholder_issues(slide)
    issues += text_presence_issues(" ".join(slide.text() for slide in slides), request.required_text, request.forbidden_text)
    return issues + palette_issues(root, slides, system)


def slide_count_issues(requested_slide_count: int | None, slides: list[Slide]) -> list[Issue]:
    if requested_slide_count is None or requested_slide_count == len(slides):
        return []
    return [SLIDE_COUNT_MISMATCH.issue(f"slides.html has {len(slides)} slides, but {requested_slide_count} were requested", "deck")]


def icon_issues(slide: Slide) -> list[Issue]:
    names = [element.attributes["data-icon"].strip() for element in slide.element.descendants() if "data-icon" in element.attributes]
    return [ICON_UNKNOWN.issue(f'{slide.location}: data-icon="{name}" is not an icon the kit ships', slide.location, suggestion=names_suggestion(name, icon_names())) for name in names if name not in icon_names()]


def empty_slide_issues(slide: Slide) -> list[Issue]:
    if slide.text() or any(element.tag in CONTENT_TAGS for element in slide.element.descendants()):
        return []
    return [SLIDE_WITHOUT_CONTENT.issue(f"{slide.location} shows nothing", slide.location)]


def chart_issues(slide: Slide) -> list[Issue]:
    issues = []
    for figure in find_all(slide.element, "figure"):
        if "data-chart" in figure.attributes:
            chart_type = figure.attributes["data-chart"].strip()
            if chart_type not in chart_types():
                issues.append(CHART_DATA_INVALID.issue(f'{slide.location}: data-chart="{chart_type}" is not one of {", ".join(chart_types())}', slide.location, suggestion=names_suggestion(chart_type, chart_types())))
                chart_type = closest_name(chart_type, chart_types()) or ""
            issues += [CHART_DATA_INVALID.issue(f"{slide.location}: {problem}", slide.location) for problem in chart_problems(chart_type, figure.attributes)]
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


def image_issues(slide: Slide, base_path: pathlib.Path) -> list[Issue]:
    issues = []
    for image in [image for image in find_all(slide.element, "img") if "data-logo" not in image.attributes]:
        source = image.attributes.get("src", "").strip()
        problem = image_problem(source, base_path)
        if problem:
            issues.append(IMAGE_NOT_FOUND.issue(f"{slide.location}: {problem}", slide.location))
    return issues


def image_problem(source: str, base_path: pathlib.Path) -> str:
    if not source:
        return "an <img> has no src"
    if source.startswith("data:"):
        return ""
    if source.startswith(("http:", "https:")):
        return f"{source} is remote and the build does not fetch it"
    resolved = resolve_resource_path(source, base_path)
    return "" if resolved is not None and resolved.exists() else f"{source} does not exist beside slides.html"


def placeholder_issues(slide: Slide) -> list[Issue]:
    found = PLACEHOLDER_PATTERN.findall(slide.text())
    if not found:
        return []
    return [PLACEHOLDER_LEFT.issue(f"{slide.location} still shows {', '.join(sorted(set(found)))}", slide.location, suggestion="replace it with the real value from the source, or write \"Not provided\" in the deck's language")]


def palette_issues(root: Element, slides: list[Slide], system: DesignSystem) -> list[Issue]:
    palette = allowed_colors(system)
    places = [("slides.html", shared_style_texts(root, slides))] + [(slide.location, slide_style_texts(slide.element)) for slide in slides]
    palette_listed = ", ".join(sorted(f"#{color}" for color in palette))
    return [issue for location, texts in places for issue in off_palette_issues(colors_in(texts) - palette - ALWAYS_ALLOWED_COLORS, location, palette_listed)]


def off_palette_issues(off_palette: set[str], location: str, palette_listed: str) -> list[Issue]:
    if not off_palette:
        return []
    listed = ", ".join(f"#{color}" for color in sorted(off_palette))
    return [OFF_PALETTE_COLOR.issue(f"{len(off_palette)} colors are outside the palette: {listed}", location, suggestion=f"{OFF_PALETTE_COLOR.default_suggestion()}; the palette is {palette_listed}")]


def slide_style_texts(section: Element) -> list[str]:
    return [element.attributes["style"] for element in (section, *section.descendants()) if "style" in element.attributes]


def shared_style_texts(root: Element, slides: list[Slide]) -> list[str]:
    in_slides = {id(element) for slide in slides for element in (slide.element, *slide.element.descendants())}
    blocks = ["".join(child for child in style.children if isinstance(child, str)) for style in find_all(root, "style")]
    return blocks + [element.attributes["style"] for element in root.descendants() if "style" in element.attributes and id(element) not in in_slides]


def allowed_colors(system: DesignSystem) -> set[str]:
    return {normalized_color(f"#{value}") for value in palette_of(system).values()} - {""}


def colors_in(style_texts_found: list[str]) -> set[str]:
    colors = set()
    for style_text in style_texts_found:
        for name, value in DECLARATION_PATTERN.findall(style_text):
            colors |= {normalized_color(literal) for literal in COLOR_LITERAL_PATTERN.findall(value) if parse_css_color(literal).alpha > 0}
    return colors - {""}


def normalized_color(literal: str) -> str:
    try:
        return parse_css_color(literal).hex_value
    except (ValueError, IndexError):
        return ""




def check_summary(slides: list[Slide], issues: list[Issue]) -> str:
    errors = [issue for issue in issues if issue.kind.severity == ERROR]
    if errors:
        listed = "; ".join(f"{number}. {issue.kind.code}{' on ' + issue.location if issue.location else ''}: {issue.message}" for number, issue in enumerate(errors, start=1))
        return f"{len(errors)} problems to fix before the deck can be built, all listed here: {listed}"
    warnings = f", {len(issues)} warnings" if issues else ""
    return f"checked {len(slides)} slides: ready to build{warnings}"


def check_details(slides: list[Slide]) -> dict:
    return {"slideCount": len(slides), "outline": [{"slide": slide.index, "title": slide.title} for slide in slides]}


def check_request(source_path: pathlib.Path, parsed, holds_blanks: bool = False) -> CheckRequest:
    return CheckRequest(source_path.resolve(), parsed.slide_count, tuple(parsed.required_text), tuple(parsed.forbidden_text), bool(holds_blanks or getattr(parsed, "blank", None) or getattr(parsed, "replace", None)))


def deck_source_path(target: str) -> pathlib.Path:
    path = pathlib.Path(target).expanduser()
    return path / "slides.html" if path.is_dir() else path


def main() -> Result:
    parsed = route_arguments("check", "slides")
    path = pathlib.Path(parsed.file).expanduser()
    if path.name == DESIGN_FILE_NAME:
        return check_design(path.resolve())
    return check_deck(check_request(deck_source_path(parsed.file), parsed))


if __name__ == "__main__":
    raise SystemExit(run_command(main))
