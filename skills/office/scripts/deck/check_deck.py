#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import pathlib
import re

from css_color import parse_css_color
from deck_definitions import (
    CHART_DATA_INVALID,
    IMAGE_NOT_FOUND,
    KIT_LAYOUT_NAMES,
    LAYOUT_MISSING,
    LAYOUT_PART_EXCESS,
    LAYOUT_PART_MISSING,
    LAST_SLIDE_NOT_CLOSING,
    LAYOUT_REPEATED,
    LAYOUT_UNKNOWN,
    NO_SLIDE_SECTIONS,
    OFF_PALETTE_COLOR,
    SLIDE_COUNT_MISMATCH,
    SLIDE_WITHOUT_CONTENT,
    SOURCE_NOT_HTML,
    THEME_UNKNOWN,
    TOO_FEW_LAYOUTS,
    FIRST_SLIDE_NOT_COVER,
    KitLayout,
    kit_layout,
    part_label,
)
from deck_kit import DEFAULT_THEME, chart_number, chart_types, split_chart_list, theme_palettes, uses_deck_kit
from deck_source import Element, find_all, normalized_text, parse_source, style_texts, visible_text
from design_tokens import design_front_matter
from office_inputs import PPTX, require_kind
from office_result import ERROR, Issue, OfficeArgumentParser, OfficeFailure, Result, run_command
from office_schema import closest_name
from resource_inlining import resolve_resource_path
from text_checks import DRAFT_PLACEHOLDER_PATTERN, PLACEHOLDER_LEFT, REQUIRED_TEXT_MISSING


REPEAT_LIMIT = 3
COVER_LAYOUT = "cover"
CLOSING_LAYOUT = "closing"
CLOSING_SLIDE_MINIMUM = 3
VARIETY_SLIDE_MINIMUM = 6
VARIETY_LAYOUT_MINIMUM = 3
DONUT_SLICE_MAXIMUM = 8
STACKED_CHART_TYPES = ("stacked", "stacked100", "area")
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


@dataclass(frozen=True)
class Slide:
    index: int
    element: Element

    @property
    def layout(self) -> str:
        return self.element.attributes.get("data-layout", "").strip()

    @property
    def intended_layout(self) -> str:
        if self.layout in KIT_LAYOUT_NAMES:
            return self.layout
        return closest_name(self.layout, KIT_LAYOUT_NAMES) or self.layout

    @property
    def location(self) -> str:
        return f"slide {self.index}"

    @property
    def title(self) -> str:
        headings = [child for child in self.element.child_elements() if child.tag in ("h1", "h2")]
        return normalized_text(visible_text(headings[0])) if headings else ""

    def parts(self) -> list[Element]:
        return [child for child in self.element.child_elements() if not child.is_notes()]

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
    issues = deck_issues(request, root, slides, uses_deck_kit(source_text))
    return Result(summary=check_summary(slides, issues), output_path=str(request.source_path), issues=tuple(issues), details=check_details(root, slides))


def deck_issues(request: CheckRequest, root: Element, slides: list[Slide], is_kit_deck: bool) -> list[Issue]:
    issues = []
    if is_kit_deck:
        issues += theme_issues(root) + layout_issues(slides) + sequence_issues(slides)
    issues += slide_count_issues(request.requested_slide_count, slides)
    for slide in slides:
        issues += empty_slide_issues(slide) + chart_issues(slide) + image_issues(slide, request.source_path.parent) + placeholder_issues(slide)
    issues += required_text_issues(request.required_text, slides)
    return issues + palette_issues(root, request.source_path.parent, is_kit_deck)


def theme_issues(root: Element) -> list[Issue]:
    theme = body_theme(root)
    if theme is None or theme in theme_palettes():
        return []
    return [THEME_UNKNOWN.issue(f'data-theme="{theme}" is not a kit theme', "body", suggestion=name_suggestion(theme, tuple(theme_palettes())))]


def layout_issues(slides: list[Slide]) -> list[Issue]:
    issues = []
    for slide in slides:
        if not slide.layout:
            issues.append(LAYOUT_MISSING.issue(f"{slide.location} has no data-layout", slide.location, suggestion=f"give the <section> a data-layout, one of: {', '.join(KIT_LAYOUT_NAMES)}"))
            continue
        layout = kit_layout(slide.layout)
        if layout is None:
            issues.append(LAYOUT_UNKNOWN.issue(f'{slide.location} uses data-layout="{slide.layout}"', slide.location, suggestion=name_suggestion(slide.layout, KIT_LAYOUT_NAMES)))
            layout = kit_layout(slide.intended_layout)
        if layout is not None:
            issues += part_issues(slide, layout)
    return issues


def part_issues(slide: Slide, layout: KitLayout) -> list[Issue]:
    issues = []
    children = slide.parts()
    for part in layout.parts:
        count = sum(1 for child in children if part.matches(child.tag, child.classes, child.attributes))
        if count < part.minimum:
            issues.append(LAYOUT_PART_MISSING.issue(f"{slide.location} ({layout.name}) has {count} of {part_label(part)} as a direct child of its <section>", slide.location, suggestion=f"add it; {layout_parts(layout)}"))
        elif part.maximum is not None and count > part.maximum:
            issues.append(LAYOUT_PART_EXCESS.issue(f"{slide.location} ({layout.name}) has {count} {part.selector}; the layout holds at most {part.maximum}", slide.location, suggestion=f"{LAYOUT_PART_EXCESS.default_suggestion()}; {layout_parts(layout)}"))
    return issues


def sequence_issues(slides: list[Slide]) -> list[Issue]:
    issues = []
    layouts_in_order = [slide.intended_layout for slide in slides]
    for start in range(len(slides) - REPEAT_LIMIT + 1):
        window = layouts_in_order[start:start + REPEAT_LIMIT]
        if window[0] and len(set(window)) == 1:
            issues.append(LAYOUT_REPEATED.issue(f"slides {start + 1}-{start + REPEAT_LIMIT} all use {window[0]}", f"slide {start + 2}"))
    layouts = {slide.intended_layout for slide in slides if slide.layout}
    if len(slides) >= VARIETY_SLIDE_MINIMUM and len(layouts) < VARIETY_LAYOUT_MINIMUM:
        issues.append(TOO_FEW_LAYOUTS.issue(f"{len(slides)} slides use only {', '.join(sorted(layouts))}", "deck"))
    return issues + outline_issues(slides)


def outline_issues(slides: list[Slide]) -> list[Issue]:
    issues = []
    if slides[0].intended_layout != COVER_LAYOUT:
        issues.append(FIRST_SLIDE_NOT_COVER.issue(f'slide 1 uses data-layout="{slides[0].layout}"', slides[0].location))
    if len(slides) >= CLOSING_SLIDE_MINIMUM and slides[-1].intended_layout != CLOSING_LAYOUT:
        issues.append(LAST_SLIDE_NOT_CLOSING.issue(f'the last slide uses data-layout="{slides[-1].layout}"', slides[-1].location))
    return issues


def slide_count_issues(requested_slide_count: int | None, slides: list[Slide]) -> list[Issue]:
    if requested_slide_count is None or requested_slide_count == len(slides):
        return []
    return [SLIDE_COUNT_MISMATCH.issue(f"slides.html has {len(slides)} slides, but {requested_slide_count} were requested", "deck")]


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
                issues.append(CHART_DATA_INVALID.issue(f'{slide.location}: data-chart="{chart_type}" is not one of {", ".join(chart_types())}', slide.location, suggestion=name_suggestion(chart_type, chart_types())))
                chart_type = closest_name(chart_type, chart_types()) or ""
            issues += [CHART_DATA_INVALID.issue(f"{slide.location}: {problem}", slide.location) for problem in chart_problems(chart_type, figure.attributes)]
    return issues


def chart_problems(chart_type: str, attributes: dict[str, str]) -> list[str]:
    labels = split_list(attributes.get("data-labels", ""))
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
            series.append((name.strip(), split_list(values)))
        return series
    if attributes.get("data-values", "").strip():
        return [("data-values", split_list(attributes["data-values"]))]
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
        problems.append('a scatter chart takes exactly two series in data-series: the horizontal axis first, then the vertical, such as "매출: 12, 30; 이익률: 8, 11"')
    if chart_type in STACKED_CHART_TYPES and any(value < 0 for _, values in series for value in numbers_in(values)):
        problems.append(f"a {chart_type} chart stacks its series, so every value must be zero or more")
    if chart_type not in ("donut", "pie"):
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


def split_list(text: str) -> list[str]:
    return split_chart_list(text)


def is_number(text: str) -> bool:
    return chart_number(text) is not None


def image_issues(slide: Slide, base_path: pathlib.Path) -> list[Issue]:
    issues = []
    for image in find_all(slide.element, "img"):
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
    found = DRAFT_PLACEHOLDER_PATTERN.findall(slide.text())
    if not found:
        return []
    return [PLACEHOLDER_LEFT.issue(f"{slide.location} still shows {', '.join(sorted(set(found)))}", slide.location, suggestion="replace it with the real value from the source, or write \"Not provided\" in the deck's language")]


def required_text_issues(required_text: tuple[str, ...], slides: list[Slide]) -> list[Issue]:
    deck_text = " ".join(slide.text() for slide in slides).casefold()
    spaceless_text = deck_text.replace(" ", "")
    missing = [value for value in required_text if normalized_text(value).casefold() not in deck_text and normalized_text(value).casefold().replace(" ", "") not in spaceless_text]
    return [REQUIRED_TEXT_MISSING.issue(f"required text is missing: {value}", value) for value in missing]


def palette_issues(root: Element, base_path: pathlib.Path, is_kit_deck: bool) -> list[Issue]:
    palette = allowed_colors(root, base_path, is_kit_deck)
    if palette is None:
        return []
    off_palette = sorted(used_colors(root) - palette - ALWAYS_ALLOWED_COLORS)
    if not off_palette:
        return []
    listed = ", ".join(f"#{color}" for color in off_palette)
    palette_listed = ", ".join(sorted(f"#{color}" for color in palette))
    return [OFF_PALETTE_COLOR.issue(f"{len(off_palette)} colors are outside the palette: {listed}", "slides.html", suggestion=f"{OFF_PALETTE_COLOR.default_suggestion()}; the palette is {palette_listed}")]


def allowed_colors(root: Element, base_path: pathlib.Path, is_kit_deck: bool) -> set[str] | None:
    design_colors = design_document_colors(base_path / "DESIGN.md")
    if not is_kit_deck and not design_colors:
        return None
    palette = set(design_colors)
    if is_kit_deck:
        theme = theme_palettes().get(body_theme(root) or DEFAULT_THEME, {})
        palette |= {normalized_color(value) for value in theme.values()}
        palette |= token_overrides(root, set(theme))
        accent = body_element(root).attributes.get("data-accent", "") if body_element(root) else ""
        palette |= {normalized_color(accent)} if accent else set()
    return palette - {""}


def design_document_colors(design_path: pathlib.Path) -> set[str]:
    if not design_path.exists():
        return set()
    front_matter = design_front_matter(design_path.read_text(encoding="utf-8"))
    return {normalized_color(value) for value in HEX_PATTERN.findall(front_matter)}


def token_overrides(root: Element, token_names: set[str]) -> set[str]:
    colors = set()
    for style_text in style_texts(root):
        for name, value in DECLARATION_PATTERN.findall(style_text):
            if name.startswith("--") and name[2:] in token_names:
                colors |= {normalized_color(literal) for literal in COLOR_LITERAL_PATTERN.findall(value)}
    return colors


def used_colors(root: Element) -> set[str]:
    colors = set()
    for style_text in style_texts(root):
        for name, value in DECLARATION_PATTERN.findall(style_text):
            colors |= {normalized_color(literal) for literal in COLOR_LITERAL_PATTERN.findall(value) if parse_css_color(literal).alpha > 0}
    return colors - {""}


def normalized_color(literal: str) -> str:
    try:
        return parse_css_color(literal).hex_value
    except (ValueError, IndexError):
        return ""


def body_element(root: Element) -> Element | None:
    bodies = find_all(root, "body")
    return bodies[0] if bodies else None


def body_theme(root: Element) -> str | None:
    body = body_element(root)
    if body is None or "data-theme" not in body.attributes:
        return None
    return body.attributes["data-theme"].strip()


def name_suggestion(name: str, available: tuple[str, ...]) -> str:
    match = closest_name(name, available)
    listed = f"use one of: {', '.join(available)}"
    return f"did you mean {match!r}? {listed}" if match else listed


def layout_parts(layout: KitLayout) -> str:
    return f"the {layout.name} layout takes, as direct children of its <section>: {', '.join(part_label(part) for part in layout.parts)}"


def check_summary(slides: list[Slide], issues: list[Issue]) -> str:
    errors = [issue for issue in issues if issue.kind.severity == ERROR]
    if errors:
        listed = "; ".join(f"{number}. {issue.message}" for number, issue in enumerate(errors, start=1))
        return f"{len(errors)} problems to fix in slides.html before it can be built, all listed here: {listed}"
    warnings = f", {len(issues)} warnings" if issues else ""
    return f"checked {len(slides)} slides: ready to build{warnings}"


def check_details(root: Element, slides: list[Slide]) -> dict:
    return {
        "slideCount": len(slides),
        "theme": body_theme(root),
        "outline": [{"slide": slide.index, "layout": slide.layout or None, "title": slide.title} for slide in slides],
    }


def parse_arguments(arguments: list[str] | None = None):
    parser = OfficeArgumentParser(description=(
        "Check a deck. For slides.html (the default, or its directory): layouts, parts, charts, images, placeholders, required text, slide count and palette, "
        "without rendering; deck build runs this first. For a .pptx: text measured with the deck's fonts that overflows its box, shapes off the slide, "
        "overlapping text and stretched pictures, each with an operation deck apply accepts, then an HTML preview of the slides drawn from the same geometry, styles and fonts."
    ))
    parser.add_argument("target", nargs="?", default="slides.html", help="slides.html, the directory holding it, or a .pptx (default slides.html)")
    add_check_arguments(parser)
    parser.add_argument("--slides", default="", help=".pptx: slides to check, such as 2,4-6; default every slide")
    parser.add_argument("--output-directory", default="", help=".pptx: where the preview goes, default <file name>-check beside the file")
    parser.add_argument("--no-preview", action="store_true", help=".pptx: measure only, without writing the preview")
    return parser.parse_args(arguments)


def add_check_arguments(parser: OfficeArgumentParser) -> None:
    parser.add_argument("--slide-count", type=int, help="slides.html: the slide count the user asked for; a different count is an error")
    parser.add_argument("--required-text", action="append", default=[], help="slides.html: a source fact that must be visible on a slide; repeat for each fact")


def check_request(source_path: pathlib.Path, parsed) -> CheckRequest:
    return CheckRequest(source_path.resolve(), parsed.slide_count, tuple(parsed.required_text))


def deck_source_path(target: str) -> pathlib.Path:
    path = pathlib.Path(target).expanduser()
    return path / "slides.html" if path.is_dir() else path


def main() -> Result:
    parsed = parse_arguments()
    if pathlib.Path(parsed.target).suffix.casefold() not in ("", ".html"):
        from check_pptx import check_presentation
        require_kind(parsed.target, PPTX)
        return check_presentation(pathlib.Path(parsed.target).expanduser(), parsed.slides, parsed.output_directory, not parsed.no_preview)
    return check_deck(check_request(deck_source_path(parsed.target), parsed))


if __name__ == "__main__":
    raise SystemExit(run_command(main))
