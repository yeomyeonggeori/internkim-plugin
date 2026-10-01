from __future__ import annotations

from dataclasses import dataclass

from fonts.registry import DECK, default_family
from deck_kit import DEFAULT_THEME, chart_types, slide_size, theme_palettes
from layout_thresholds import SMALLEST_TEXT_SHARE_OF_WIDTH, TITLE_LINE_MAXIMUM
from office_operations import OPERATION_ISSUE_KINDS
from template_merge import MERGE_VALUES, PACKAGE_MERGE_ISSUE_KINDS
from office_result import ERROR, WARNING, Issue, IssueKind
from office_schema import ListOf
from pptx_edit_definitions import OPERATIONS
from render.renderer import RENDER_ISSUE_KINDS
from text_checks import PLACEHOLDER_LEFT, REQUIRED_TEXT_MISSING
from image_formats import PICTURE_FORMATS_TEXT


DECK_LOCATION = "deck"
LAYOUT_RENDER_SOURCE = "layout"
NATIVE_RENDER_SOURCE = "nativeFallback"


@dataclass(frozen=True)
class ReviewCheck:
    kind: IssueKind

    def issue(self, text: str, location: str | None = None, suggestion: object = None) -> Issue:
        return self.kind.issue(text, location, suggestion)

    def deck_issue(self, text: str) -> Issue:
        return self.issue(text, DECK_LOCATION)


def review_check(code: str, meaning: str, suggestion: str) -> ReviewCheck:
    return ReviewCheck(IssueKind(code, WARNING, meaning, suggestion))


SLIDE_BLANK = review_check("SLIDE_BLANK", "the slide render shows no content", "check that the slide's content is not hidden or outside the frame")
CONTENT_OVERFLOW = review_check("CONTENT_OVERFLOW", "an element's content is larger than its box, so it is clipped or spills out", "cut or split what the message names; a build suggestion says how many rows, items or characters fit at full type size, and a .pptx suggestion is the operation to apply")
OUT_OF_FRAME = review_check("OUT_OF_FRAME", "an element lies partly or wholly outside its slide", "keep every part on the slide: split or cut what pushes it off, as the suggestion counts; in a .pptx, apply the operation the suggestion names")
TEXT_OVERLAP = review_check("TEXT_OVERLAP", "two pieces of text cover each other", "separate the two text blocks or shorten the one that spills")
TEXT_COVERED = review_check("TEXT_COVERED", "a box painted over text hides part of it", "follow the suggestion, which names the cause: rows, items or text that do not fit, or a custom style that moves a part over another")
FOOTER_CROSSED = review_check("FOOTER_CROSSED", "slide content reaches into the footer band", "shorten or split the content so it ends above the footer")
TITLE_TOO_LONG = review_check("TITLE_TOO_LONG", f"a slide title runs past {TITLE_LINE_MAXIMUM} lines", "state the conclusion in one short sentence and move the detail into the body or the speaker notes")
TINY_TEXT = review_check("TINY_TEXT", f"rendered text is smaller than {SMALLEST_TEXT_SHARE_OF_WIDTH:.0%} of the slide width ({SMALLEST_TEXT_SHARE_OF_WIDTH * slide_size()[0]:g}px on a {slide_size()[0]}px slide)", "shorten the slide so the kit does not shrink its type; the suggestion says how much fits at full size")
IMAGE_DISTORTED = review_check("IMAGE_DISTORTED", "an image is stretched away from its own aspect ratio", "put the photo in a cover or image slide, which crops it to its frame; in a .pptx, apply the set_transform the suggestion names")
GEOMETRY_NOT_MEASURED = review_check("GEOMETRY_NOT_MEASURED", "no renderer measured element geometry, so overflow, overlap and stretched images were not checked", "install bun or node 18 and build again, or say the layout was not measured")
UNRELIABLE_VISUAL_EVIDENCE = review_check("UNRELIABLE_VISUAL_EVIDENCE", "review images were not drawn from the deck's layout", "treat the previews as approximate and say so when delivering")

TOPIC_TITLE = review_check("TOPIC_TITLE", "the title is a topic label, not a claim", "write the title as the slide's conclusion")
LANGUAGE_MISMATCH = review_check("LANGUAGE_MISMATCH", "slide titles are Latin-only in a Korean deck", "write the titles in the request language")
UNSOURCED_CURRENT_DATE = review_check("UNSOURCED_CURRENT_DATE", "a slide shows today's date that the source does not", "show only dates from the source material")
VERTICAL_DEAD_ZONE = review_check("VERTICAL_DEAD_ZONE", "an empty band spans much of the slide height, between content or under the body", "give the body what its layout holds, such as a .takeaway band, more items or an .insight, or move the content to a layout that fills the frame")
EMOJI_ICON = review_check("EMOJI_ICON", "a slide uses emoji glyphs", "write a .label word instead; the kit draws list markers and numbers itself")
MISSING_SPEAKER_NOTES = review_check("MISSING_SPEAKER_NOTES", "a slide has no speaker notes", 'add an <aside class="notes"> script to every slide')

SLIDE_RENDER_CHECKS = (SLIDE_BLANK, CONTENT_OVERFLOW, OUT_OF_FRAME, TEXT_OVERLAP, TEXT_COVERED, FOOTER_CROSSED, TITLE_TOO_LONG, IMAGE_DISTORTED, TINY_TEXT, GEOMETRY_NOT_MEASURED, UNRELIABLE_VISUAL_EVIDENCE)
DESIGN_CHECKS = (
    TOPIC_TITLE,
    LANGUAGE_MISMATCH,
    UNSOURCED_CURRENT_DATE,
    VERTICAL_DEAD_ZONE,
    EMOJI_ICON,
    MISSING_SPEAKER_NOTES,
)
REVIEW_ISSUE_KINDS = tuple(check.kind for check in SLIDE_RENDER_CHECKS + DESIGN_CHECKS)

SOURCE_NOT_HTML = IssueKind("SOURCE_NOT_HTML", ERROR, "the deck source is not an .html file", "write slides.html, or pass --source with an .html file")
NO_SLIDE_SECTIONS = IssueKind("NO_SLIDE_SECTIONS", ERROR, "the HTML has no <section> slides", "put each slide in its own <section>")
UNKNOWN_FORMAT = IssueKind("UNKNOWN_FORMAT", ERROR, "--format names a format the build cannot write", "use pdf, pptx, html, or all")
PPTX_WITHOUT_DESIGN = IssueKind("PPTX_WITHOUT_DESIGN", WARNING, "no renderer drew the deck, so the PPTX re-lays the slide text into stock layouts", "say the PPTX does not carry the deck's design, or install bun or node 18 and build again")
FONT_NOT_EMBEDDED = IssueKind("FONT_NOT_EMBEDDED", WARNING, "the PPTX names a font it could not embed, so the recipient sees a substitute unless that font is installed", f"use {default_family(DECK).name}, or tell the recipient which font to install")
TEXT_KEPT_AS_PICTURE = IssueKind("TEXT_KEPT_AS_PICTURE", WARNING, "some slide text is drawn into the slide picture, so the recipient cannot edit it", "name that text when delivering; rotated, skewed, filtered, gradient-clipped and SVG text stays a picture")

LAYOUT_UNKNOWN = IssueKind("LAYOUT_UNKNOWN", ERROR, "a slide's data-layout is not one of the kit's layouts", "use a layout office guide deck lists")
LAYOUT_MISSING = IssueKind("LAYOUT_MISSING", ERROR, "a slide in a kit deck has no data-layout", "give every <section> a data-layout")
THEME_UNKNOWN = IssueKind("THEME_UNKNOWN", ERROR, "the body's data-theme is not one of the kit's themes", "use a theme office guide deck lists")
LAYOUT_PART_MISSING = IssueKind("LAYOUT_PART_MISSING", ERROR, "a slide lacks a part its layout needs, as a direct child of the <section>", "add the part the message names; office guide deck lists each layout's parts")
LAYOUT_PART_EXCESS = IssueKind("LAYOUT_PART_EXCESS", ERROR, "a slide holds more of one part than its layout can lay out", "split the slide in two, or move the detail to a table slide")
LAYOUT_REPEATED = IssueKind("LAYOUT_REPEATED", ERROR, "three slides in a row use the same layout", "change the middle slide to another layout that fits its content")
TOO_FEW_LAYOUTS = IssueKind("TOO_FEW_LAYOUTS", ERROR, "a deck of six or more slides uses fewer than three layouts", "pick each slide's layout from its content: one number, metrics, comparison, sequence, table or chart")
FIRST_SLIDE_NOT_COVER = IssueKind("FIRST_SLIDE_NOT_COVER", WARNING, "the deck does not open with a cover slide", 'make slide 1 data-layout="cover" with the deck title and who presents it')
LAST_SLIDE_NOT_CLOSING = IssueKind("LAST_SLIDE_NOT_CLOSING", WARNING, "a deck of three or more slides does not end on a closing slide", 'end with data-layout="closing": the decision asked for or the next steps')
SLIDE_COUNT_MISMATCH = IssueKind("SLIDE_COUNT_MISMATCH", ERROR, "the slide count differs from --slide-count", "add or remove slides until the count matches the request")
SLIDE_WITHOUT_CONTENT = IssueKind("SLIDE_WITHOUT_CONTENT", ERROR, "a slide has no visible text, image or chart", "give the slide its content or delete it")
CHART_DATA_INVALID = IssueKind("CHART_DATA_INVALID", ERROR, "a chart's data attributes do not parse or do not line up", "give data-labels and data-values (or data-series) the same number of plain numbers")
IMAGE_NOT_FOUND = IssueKind("IMAGE_NOT_FOUND", ERROR, "an image is remote or its file does not exist, so the slide would show an empty box", "download it with office deck image and point src at the local file, or remove the image")
OFF_PALETTE_COLOR = IssueKind("OFF_PALETTE_COLOR", WARNING, "the source uses colors outside the theme or DESIGN.md palette", "use the theme tokens such as var(--accent) and var(--ink), or name the brand color in DESIGN.md colors")

SOURCE_CHECK_ISSUE_KINDS = (
    SOURCE_NOT_HTML,
    NO_SLIDE_SECTIONS,
    LAYOUT_UNKNOWN,
    LAYOUT_MISSING,
    THEME_UNKNOWN,
    LAYOUT_PART_MISSING,
    LAYOUT_PART_EXCESS,
    LAYOUT_REPEATED,
    TOO_FEW_LAYOUTS,
    FIRST_SLIDE_NOT_COVER,
    LAST_SLIDE_NOT_CLOSING,
    SLIDE_COUNT_MISMATCH,
    SLIDE_WITHOUT_CONTENT,
    CHART_DATA_INVALID,
    IMAGE_NOT_FOUND,
    PLACEHOLDER_LEFT,
    REQUIRED_TEXT_MISSING,
    OFF_PALETTE_COLOR,
)

BUILD_ISSUE_KINDS = (
    UNKNOWN_FORMAT,
    *RENDER_ISSUE_KINDS,
    PPTX_WITHOUT_DESIGN,
    FONT_NOT_EMBEDDED,
    TEXT_KEPT_AS_PICTURE,
)

IMAGE_SEARCH_FAILED = IssueKind("IMAGE_SEARCH_FAILED", ERROR, "the image search could not be reached", "skip imagery or try a simpler English query")
NO_IMAGE_FOUND = IssueKind("NO_IMAGE_FOUND", ERROR, "no usable public-domain image matched", "try a simpler English query or skip imagery")

IMAGE_ISSUE_KINDS = (IMAGE_SEARCH_FAILED, NO_IMAGE_FOUND)
LAYOUT_AUDIT_ISSUE_KINDS = (CONTENT_OVERFLOW.kind, OUT_OF_FRAME.kind, TEXT_OVERLAP.kind, IMAGE_DISTORTED.kind)

PICTURE_UNREADABLE = IssueKind("PICTURE_UNREADABLE", ERROR, f"an image file given to an operation is not a {PICTURE_FORMATS_TEXT} picture", f"pass the path of a {PICTURE_FORMATS_TEXT} file")
PPTX_NOT_RENDERED = IssueKind("PPTX_NOT_RENDERED", WARNING, "the renderer could not draw the slides, so nobody looked at them", "install bun or node 18 and run again, or say the slides were checked by measurement only and not seen")

APPLY_ISSUE_KINDS = (PICTURE_UNREADABLE,)
PPTX_CHECK_ISSUE_KINDS = (PPTX_NOT_RENDERED,)

@dataclass(frozen=True)
class ItemLimits:
    minimum: int
    maximum: int
    levels: int = 1
    leaves: int | None = None


@dataclass(frozen=True)
class LayoutPart:
    selector: str
    minimum: int = 1
    maximum: int | None = 1
    items: ItemLimits | None = None

    def matches(self, tag: str, classes: set[str], attributes: dict[str, str]) -> bool:
        return any(selector_matches(alternative, tag, classes, attributes) for alternative in self.selector.split("|"))


@dataclass(frozen=True)
class KitLayout:
    name: str
    purpose: str
    parts: tuple[LayoutPart, ...]


def selector_matches(selector: str, tag: str, classes: set[str], attributes: dict[str, str]) -> bool:
    if selector.startswith("."):
        return selector[1:] in classes
    if "[" in selector:
        element, attribute = selector.rstrip("]").split("[")
        return tag == element and attribute in attributes
    return tag == selector


TITLE = LayoutPart("h2")
KIT_LAYOUTS = (
    KitLayout("cover", "first slide: the deck's claim, a lead line and a .meta line with presenter and date; an <img> fills the right panel", (LayoutPart("h1"), LayoutPart("img", 0))),
    KitLayout("agenda", "the order of the talk, three to six items", (TITLE, LayoutPart("ol|ul"))),
    KitLayout("section", "a divider before a part of the talk; the .eyebrow holds its number", (TITLE,)),
    KitLayout("statement", "one sentence the audience must remember; <em> marks the words in the accent color", (TITLE,)),
    KitLayout("number", "one number that carries the slide, with its .label and the points that explain it", (TITLE, LayoutPart(".value"), LayoutPart(".label", 0))),
    KitLayout("kpi", "two to four metrics in one unit system, each a .kpi with .value, .label and a change line", (TITLE, LayoutPart(".kpi", 2, 4))),
    KitLayout("cards", "two to four parallel points, each a .card with an optional .label or .value, an <h3> and a <p>; two or three stand side by side, four form a 2x2", (TITLE, LayoutPart(".card", 2, 4))),
    KitLayout("comparison", "two options side by side, each a .column with .label, <h3> and <ul>; .pick marks the recommended one", (TITLE, LayoutPart(".column", 2, 2))),
    KitLayout("timeline", "a sequence of three to six .step blocks, each with a .label date, <h3> and <p>; .done fills the dot", (TITLE, LayoutPart(".step", 3, 6))),
    KitLayout("table", "rows and columns the audience must read; numeric cells align right by themselves, tr.pick highlights a row", (TITLE, LayoutPart("table"))),
    KitLayout("chart", "a trend, ranking or share drawn from data attributes, with an optional .insight beside it", (TITLE, LayoutPart("figure[data-chart]"), LayoutPart(".insight", 0))),
    KitLayout("quote", "a customer's or expert's words in a <blockquote> with a .by line", (LayoutPart("blockquote"),)),
    KitLayout("image", "a photo that carries meaning on the left half, the text on the right", (TITLE, LayoutPart("img"))),
    KitLayout("closing", "the decision or next actions as .card blocks or an <ol>, on the deck's dark feature color", (TITLE, LayoutPart(".card", 0, 4))),
    KitLayout("process", "steps in order, each an <li> of an <ol> drawn as a box with an arrow to the next", (TITLE, LayoutPart("ol", items=ItemLimits(3, 6)))),
    KitLayout("cycle", "stages that repeat, each an <li> of an <ol> placed around a circle with arrows clockwise back to the first", (TITLE, LayoutPart("ol", items=ItemLimits(3, 6)))),
    KitLayout("hierarchy", "an org chart or breakdown as nested <ul>: one top <li>, each <li> holding its own <ul> of children; <small> adds a second line to a box", (TITLE, LayoutPart("ul", items=ItemLimits(1, 1, levels=3, leaves=8)))),
    KitLayout("pyramid", "levels of an <ol>, the top <li> the narrowest and most important", (TITLE, LayoutPart("ol", items=ItemLimits(3, 5)))),
    KitLayout("matrix", "a 2x2 of the <li> in a <ul>, read left to right then top to bottom; data-y and data-x on the <ul> name the axes", (TITLE, LayoutPart("ul", items=ItemLimits(4, 4)))),
)
KIT_LAYOUT_NAMES = tuple(layout.name for layout in KIT_LAYOUTS)
SHARED_PARTS = (
    ".eyebrow: a short kicker above the title",
    ".lead: one subtitle line under the title",
    ".takeaway: the conclusion band under the body",
    ".source: the source line, placed in the footer beside the page number",
    "<em>: words in the accent color; .up and .down color a change; .pick highlights one item",
    "<aside class=\"notes\">: the speaker notes",
)
DIAGRAM_NOTES = (
    "each <li> is one box: a short phrase, or an <h3> and a <p>; .pick on an <li> fills its box with the accent",
    "process and cycle number their boxes; the top box of a hierarchy is dark and the top level of a pyramid takes the accent",
    "the PPTX draws each box as a native shape and each arrow as a connector attached to the boxes it joins",
    "deck check refuses a list with fewer or more items than the layout holds and names the count",
)
CHART_ATTRIBUTES = (
    "data-chart: " + ", ".join(chart_types()),
    "data-labels: category names separated by commas",
    "data-values: one number per label, for a single series",
    "data-series: \"name: 1, 2, 3; other: 4, 5, 6\" for several series, each with one number per label",
    "combo: the last series is a line on its own axis, the ones before it are columns",
    "scatter: two series, the horizontal axis first and the vertical second; each label names one point",
    "stacked100: each column shows its series as shares of the column's total",
    "area: the series stacked as bands over the labels, a total over time and what it is made of",
    "data-unit: text after every value, such as 억, %, 건; combo and scatter take one per axis, \"억, %\"",
    "data-highlight: one label drawn in the accent color while the others are muted (single series, or a scatter point)",
    "data-center, data-center-label: the text in a donut's hole; default the first slice's share",
    "data-zero: true starts a line chart's axis at zero",
    "<figcaption>: the unit, period and source under the chart",
)


def kit_layout(name: str) -> KitLayout | None:
    return next((layout for layout in KIT_LAYOUTS if layout.name == name), None)


def part_label(part: LayoutPart) -> str:
    label = f"{part.selector.replace('|', ' or ')} x{count_label(part.minimum, part.maximum)}"
    return f"{label} holding {items_label(part.items)}" if part.items else label


def items_label(limits: ItemLimits) -> str:
    label = f"{count_label(limits.minimum, limits.maximum)} <li>"
    if limits.levels > 1:
        label += f", nested at most {limits.levels} levels deep"
    if limits.leaves is not None:
        label += f" with at most {limits.leaves} on the lowest level"
    return label


def count_label(minimum: int, maximum: int | None) -> str:
    return str(minimum) if maximum == minimum else f"{minimum}-{maximum}" if maximum else f"{minimum}+"


def theme_lines() -> list[str]:
    palettes = theme_palettes()
    return [
        f"  {name}{' (default)' if name == DEFAULT_THEME else ''}: background {palette['bg']}, ink {palette['ink']}, accent {palette['accent']}, second accent {palette['accent-2']}"
        for name, palette in palettes.items()
    ] + ["  data-accent=\"#RRGGBB\" on <body> replaces the accent with a brand color"]


def layout_lines() -> list[str]:
    width = max(len(name) for name in KIT_LAYOUT_NAMES)
    lines = [f"  {layout.name.ljust(width)}  {layout.purpose}; parts: {', '.join(part_label(part) for part in layout.parts)}" for layout in KIT_LAYOUTS]
    return lines + ["  Any layout also takes:"] + [f"    {part}" for part in SHARED_PARTS]


def diagram_lines() -> list[str]:
    return [f"  {note}" for note in DIAGRAM_NOTES]


def chart_lines() -> list[str]:
    return [f"  {attribute}" for attribute in CHART_ATTRIBUTES]


GUIDE_SECTIONS = (
    ("Themes (<body data-theme=\"...\">)", theme_lines),
    ("Layouts (<section data-layout=\"...\">; parts are direct children of the section)", layout_lines),
    ("Diagrams (process, cycle, hierarchy, pyramid, matrix)", diagram_lines),
    ("Charts (<figure data-chart=\"...\"> in a chart slide)", chart_lines),
)

GUIDE_INPUTS = (
    ("deck apply <file.pptx> <ops.json>", ListOf(OPERATIONS, non_empty=True)),
    ("deck merge <template.pptx> <values.json> <output.pptx>: values", MERGE_VALUES),
)
GUIDE_ISSUES = (
    ("deck build", BUILD_ISSUE_KINDS + REVIEW_ISSUE_KINDS),
    ("deck apply", OPERATION_ISSUE_KINDS + APPLY_ISSUE_KINDS + LAYOUT_AUDIT_ISSUE_KINDS),
    ("deck check", SOURCE_CHECK_ISSUE_KINDS + LAYOUT_AUDIT_ISSUE_KINDS + PPTX_CHECK_ISSUE_KINDS),
    ("deck merge", PACKAGE_MERGE_ISSUE_KINDS),
    ("deck restore", (NO_SLIDE_SECTIONS,)),
    ("deck image", IMAGE_ISSUE_KINDS),
)
