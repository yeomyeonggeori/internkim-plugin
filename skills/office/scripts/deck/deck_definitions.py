from __future__ import annotations

from dataclasses import dataclass

from deck_kit import DEFAULT_THEME, chart_types, theme_palettes
from office_operations import OPERATION_ISSUE_KINDS
from template_merge import MERGE_VALUES, PACKAGE_MERGE_ISSUE_KINDS
from office_result import ERROR, WARNING, Issue, IssueKind
from office_schema import ListOf
from pptx_edit_definitions import OPERATIONS
from text_checks import PLACEHOLDER_LEFT, REQUIRED_TEXT_MISSING


DECK_LOCATION = "deck"


@dataclass(frozen=True)
class ReviewCheck:
    kind: IssueKind
    label: str = ""
    weight: int = 0

    def issue(self, text: str, location: str | None = None) -> Issue:
        message = f"{self.label}: {text}" if self.label else text
        return self.kind.issue(message, location)

    def deck_issue(self, text: str) -> Issue:
        return self.issue(text, DECK_LOCATION)


def review_check(code: str, meaning: str, suggestion: str, label: str = "", weight: int = 0) -> ReviewCheck:
    return ReviewCheck(IssueKind(code, WARNING, meaning, suggestion), label, weight)


SLIDE_BLANK = review_check("SLIDE_BLANK", "the slide render shows no content", "check that the slide's content is not hidden or outside the frame")
SAFE_MARGIN_INTRUSION = review_check("SAFE_MARGIN_INTRUSION", "content reaches inside the DESIGN.md safe margin", "pull content back inside layout.margin")
EDGE_CLIPPING = review_check("EDGE_CLIPPING", "content touches the slide edge", "keep content off the frame edge so nothing is clipped")
SLIDE_TOO_SPARSE = review_check("SLIDE_TOO_SPARSE", "the slide is nearly empty", "give the slide enough content to justify it, or merge it")
SLIDE_TOO_CROWDED = review_check("SLIDE_TOO_CROWDED", "the slide is visually crowded", "cut or split the content")
CONTENT_OVERFLOW = review_check("CONTENT_OVERFLOW", "an element's content is larger than its box, so it is clipped or spills out", "enlarge the box, cut the content, or lower the type size")
OUT_OF_FRAME = review_check("OUT_OF_FRAME", "an element lies partly or wholly outside its slide", "move or resize the element so it sits inside the slide")
TEXT_OVERLAP = review_check("TEXT_OVERLAP", "two pieces of text cover each other", "separate the two text blocks or shorten the one that spills")
IMAGE_DISTORTED = review_check("IMAGE_DISTORTED", "an image is stretched away from its own aspect ratio", "set object-fit: cover or contain, or size the image to its ratio")
GEOMETRY_NOT_MEASURED = review_check("GEOMETRY_NOT_MEASURED", "no browser measured element geometry, so overflow, overlap and stretched images were not checked", "rerun the build where a browser renders the deck, or say the layout was not measured")
FRAME_FIT_RISK = review_check("FRAME_FIT_RISK", "content is close to the right or bottom frame edge", "check the contact sheet for clipped text", label="frameFitRisk")
UNRELIABLE_VISUAL_EVIDENCE = review_check("UNRELIABLE_VISUAL_EVIDENCE", "review images did not come from a browser", "treat the previews as approximate and say so when delivering", label="unreliableVisualEvidenceWarning")

WEAK_VISUAL_IDENTITY = review_check("WEAK_VISUAL_IDENTITY", "the deck declares no visual system", "add data-visual-system to slides.html and describe the system in DESIGN.md", "weakVisualIdentityWarning", 24)
MISSING_SLIDE_ROLE = review_check("MISSING_SLIDE_ROLE", "a slide lacks data-slide-role", "give every slide section a data-slide-role", "missingSlideRoleWarning", 16)
SIDE_STRIPE = review_check("SIDE_STRIPE", "thick side border accents carry the visual identity", "carry the identity through composition, type, and color instead", "sideStripeWarning", 14)
GHOST_CARD = review_check("GHOST_CARD", "thin-bordered soft-shadow boxes read as a default template", "replace them with the deck's own surfaces", "ghostCardWarning", 14)
TINY_TEXT = review_check("TINY_TEXT", "several CSS font sizes are below 16px", "raise text to at least 16px", "tinyTextWarning", 8)
REPEATED_COMPOSITION = review_check("REPEATED_COMPOSITION", "three or more slides share one composition", "vary slide composition by role", "repeatedCompositionWarning", 14)
RAW_STRUCTURE_PATTERN = review_check("RAW_STRUCTURE_PATTERN", "several slides are a raw table or bare list", "turn the tables and lists into designed compositions", "rawStructurePatternWarning", 12)
RAW_TABLE = review_check("RAW_TABLE", "a raw table is the slide's main composition", "design the comparison instead of dropping in a table", "rawTableWarning", 10)
BARE_LIST = review_check("BARE_LIST", "a bare list is the slide's main composition", "design the points instead of listing them", "bareListWarning", 10)
TOPIC_TITLE = review_check("TOPIC_TITLE", "the title is a topic label, not a claim", "write the title as the slide's conclusion", "topicTitleWarning", 8)
LANGUAGE_MISMATCH = review_check("LANGUAGE_MISMATCH", "slide titles are Latin-only in a Korean deck", "write the titles in the request language", "languageMismatchWarning", 10)
UNSOURCED_CURRENT_DATE = review_check("UNSOURCED_CURRENT_DATE", "a slide shows today's date that the source does not", "show only dates from the source material", "unsourcedCurrentDateWarning", 10)
VERTICAL_DEAD_ZONE = review_check("VERTICAL_DEAD_ZONE", "an empty band spans much of the slide height, between content or under the body", "distribute content to fill the frame", "verticalDeadZoneWarning", 10)
ABSOLUTE_FOOTER = review_check("ABSOLUTE_FOOTER", "an absolutely positioned bottom strip carries text", "make header, body, and footer sibling flow children", "absoluteFooterWarning", 12)
EMOJI_ICON = review_check("EMOJI_ICON", "a slide uses emoji glyphs", "use text labels, CSS markers, or inline SVG", "emojiIconWarning", 8)
MISSING_REQUIRED_TEXT = review_check("MISSING_REQUIRED_TEXT", "required-visible-text.txt lines are not visible", "put every required line on a slide", "missingRequiredTextWarning", 14)
INCONSISTENT_FOOTER_BASELINE = review_check("INCONSISTENT_FOOTER_BASELINE", "the content bottom edge varies across slides", "keep the footer on one baseline", "inconsistentFooterBaselineWarning", 8)
UNPINNED_FOOTER = review_check("UNPINNED_FOOTER", "the recurring footer is not pinned to the frame bottom", "give it margin-top: auto inside the flex column slide", "unpinnedFooterWarning", 10)
MISSING_SPEAKER_NOTES = review_check("MISSING_SPEAKER_NOTES", "a slide has no speaker notes", 'add an <aside class="notes"> script to every slide', "missingSpeakerNotesWarning", 8)

SLIDE_RENDER_CHECKS = (SLIDE_BLANK, SAFE_MARGIN_INTRUSION, EDGE_CLIPPING, SLIDE_TOO_SPARSE, SLIDE_TOO_CROWDED, CONTENT_OVERFLOW, OUT_OF_FRAME, TEXT_OVERLAP, IMAGE_DISTORTED, GEOMETRY_NOT_MEASURED, FRAME_FIT_RISK, UNRELIABLE_VISUAL_EVIDENCE)
DESIGN_CHECKS = (
    WEAK_VISUAL_IDENTITY,
    MISSING_SLIDE_ROLE,
    SIDE_STRIPE,
    GHOST_CARD,
    TINY_TEXT,
    REPEATED_COMPOSITION,
    RAW_STRUCTURE_PATTERN,
    RAW_TABLE,
    BARE_LIST,
    TOPIC_TITLE,
    LANGUAGE_MISMATCH,
    UNSOURCED_CURRENT_DATE,
    VERTICAL_DEAD_ZONE,
    ABSOLUTE_FOOTER,
    EMOJI_ICON,
    MISSING_REQUIRED_TEXT,
    INCONSISTENT_FOOTER_BASELINE,
    UNPINNED_FOOTER,
    MISSING_SPEAKER_NOTES,
)
DESIGN_WARNING_WEIGHTS = {check.kind.code: check.weight for check in DESIGN_CHECKS}
REVIEW_ISSUE_KINDS = tuple(check.kind for check in SLIDE_RENDER_CHECKS + DESIGN_CHECKS)

SOURCE_NOT_HTML = IssueKind("SOURCE_NOT_HTML", ERROR, "the deck source is not an .html file", "write slides.html, or pass --source with an .html file")
NO_SLIDE_SECTIONS = IssueKind("NO_SLIDE_SECTIONS", ERROR, "the HTML has no <section> slides", "put each slide in its own <section>")
UNKNOWN_FORMAT = IssueKind("UNKNOWN_FORMAT", ERROR, "FORMATS names a format the build cannot write", "use html, pdf, pptx, notes, review, or all")
REVIEW_FAILED = IssueKind("REVIEW_FAILED", ERROR, "the slide review stopped before writing its report", "read the review's error output above the result")
BROWSER_RENDER_UNAVAILABLE = IssueKind("BROWSER_RENDER_UNAVAILABLE", WARNING, "no browser rendered the deck", "say that the PDF and screenshots are missing, or deliver from a host with a browser")
PPTX_WITHOUT_DESIGN = IssueKind("PPTX_WITHOUT_DESIGN", WARNING, "no browser rendered the deck, so the PPTX re-lays the slide text into stock layouts", "say the PPTX does not carry the deck's design, or build where a browser renders it")
FONT_NOT_EMBEDDED = IssueKind("FONT_NOT_EMBEDDED", WARNING, "the PPTX names a font it could not embed, so the recipient sees a substitute unless that font is installed", "use Paperlogy, or tell the recipient which font to install")
TEXT_KEPT_AS_PICTURE = IssueKind("TEXT_KEPT_AS_PICTURE", WARNING, "some slide text is drawn into the slide picture, so the recipient cannot edit it", "name that text when delivering; rotated, skewed, filtered, gradient-clipped and SVG text stays a picture")

LAYOUT_UNKNOWN = IssueKind("LAYOUT_UNKNOWN", ERROR, "a slide's data-layout is not one of the kit's layouts", "use a layout office guide deck lists")
LAYOUT_MISSING = IssueKind("LAYOUT_MISSING", ERROR, "a slide in a kit deck has no data-layout", "give every <section> a data-layout")
THEME_UNKNOWN = IssueKind("THEME_UNKNOWN", ERROR, "the body's data-theme is not one of the kit's themes", "use a theme office guide deck lists")
LAYOUT_PART_MISSING = IssueKind("LAYOUT_PART_MISSING", ERROR, "a slide lacks a part its layout needs, as a direct child of the <section>", "add the part the message names; office guide deck lists each layout's parts")
LAYOUT_PART_EXCESS = IssueKind("LAYOUT_PART_EXCESS", ERROR, "a slide holds more of one part than its layout can lay out", "split the slide in two, or move the detail to a table slide")
LAYOUT_REPEATED = IssueKind("LAYOUT_REPEATED", ERROR, "three slides in a row use the same layout", "change the middle slide to another layout that fits its content")
TOO_FEW_LAYOUTS = IssueKind("TOO_FEW_LAYOUTS", ERROR, "a deck of six or more slides uses fewer than three layouts", "pick each slide's layout from its content: one number, metrics, comparison, sequence, table or chart")
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
    REVIEW_FAILED,
    BROWSER_RENDER_UNAVAILABLE,
    PPTX_WITHOUT_DESIGN,
    FONT_NOT_EMBEDDED,
    TEXT_KEPT_AS_PICTURE,
)

SLIDE_EMPTY = IssueKind("SLIDE_EMPTY", WARNING, "a slide has no text", "check that the slide exported")
SLIDE_TITLE_MISSING = IssueKind("SLIDE_TITLE_MISSING", WARNING, "a slide has no title", "give every slide a title")
TOO_MANY_SHAPES = IssueKind("TOO_MANY_SHAPES", WARNING, "a slide has more than 40 shapes that hold text, pictures, tables or charts", "simplify the slide")
DEFAULT_FONT_REMAINS = IssueKind("DEFAULT_FONT_REMAINS", WARNING, "text still uses Aptos or Calibri", "set the deck's own font")
THEME_FONT_INHERITED = IssueKind("THEME_FONT_INHERITED", WARNING, "text runs inherit the theme font", "set the font on every run")
OVERLAY_WITHOUT_BACKGROUND = IssueKind("OVERLAY_WITHOUT_BACKGROUND", WARNING, "editable overlays have no hybrid background image", "add the background image or remove the overlays")
OVERLAY_OUT_OF_BOUNDS = IssueKind("OVERLAY_OUT_OF_BOUNDS", WARNING, "an editable overlay extends past the slide", "move the overlay inside the slide")

VALIDATE_ISSUE_KINDS = (SLIDE_EMPTY, SLIDE_TITLE_MISSING, TOO_MANY_SHAPES, DEFAULT_FONT_REMAINS, THEME_FONT_INHERITED, OVERLAY_WITHOUT_BACKGROUND, OVERLAY_OUT_OF_BOUNDS)

REVIEW_REPORT_MISSING = IssueKind("REVIEW_REPORT_MISSING", ERROR, "slide-review.json is absent from the review directory", "run office deck build first")
REVIEW_DECISION_MISSING = IssueKind("REVIEW_DECISION_MISSING", WARNING, "review-decision.json is absent", "attach the usable deck with the review report notes if the requested file exists")
CONTACT_SHEETS_NOT_INSPECTED = IssueKind("CONTACT_SHEETS_NOT_INSPECTED", WARNING, "inspectedEvidence omits contact sheets", "open every contact sheet and list it in inspectedEvidence")
WARNINGS_NOT_ADDRESSED = IssueKind("WARNINGS_NOT_ADDRESSED", WARNING, "review warnings are not addressed in the decision", "list them in acceptedWarnings, remainingNotes, or issues, or rebuild a clean deck")
DECISION_SUMMARY_MISSING = IssueKind("DECISION_SUMMARY_MISSING", WARNING, "the review decision has no summary", "write a one-line summary")
DECISION_FIELD_NOT_LIST = IssueKind("DECISION_FIELD_NOT_LIST", WARNING, "a review decision field is not a list", "write the field as a JSON array")

ACCEPT_ISSUE_KINDS = (REVIEW_REPORT_MISSING, REVIEW_DECISION_MISSING, CONTACT_SHEETS_NOT_INSPECTED, WARNINGS_NOT_ADDRESSED, DECISION_SUMMARY_MISSING, DECISION_FIELD_NOT_LIST)

IMAGE_SEARCH_FAILED = IssueKind("IMAGE_SEARCH_FAILED", ERROR, "the image search could not be reached", "skip imagery or try a simpler English query")
NO_IMAGE_FOUND = IssueKind("NO_IMAGE_FOUND", ERROR, "no usable public-domain image matched", "try a simpler English query or skip imagery")

IMAGE_ISSUE_KINDS = (IMAGE_SEARCH_FAILED, NO_IMAGE_FOUND)
LAYOUT_AUDIT_ISSUE_KINDS = (CONTENT_OVERFLOW.kind, OUT_OF_FRAME.kind, TEXT_OVERLAP.kind, IMAGE_DISTORTED.kind)

PICTURE_UNREADABLE = IssueKind("PICTURE_UNREADABLE", ERROR, "an image file given to an operation is not a PNG, JPEG or GIF picture", "pass the path of a PNG, JPEG or GIF file")
PPTX_NOT_RENDERED = IssueKind("PPTX_NOT_RENDERED", WARNING, "no image of the slides was drawn, so nobody looked at them", "say the slides were checked by measurement only and not seen")

APPLY_ISSUE_KINDS = (PICTURE_UNREADABLE,)
PPTX_CHECK_ISSUE_KINDS = (PPTX_NOT_RENDERED,)

@dataclass(frozen=True)
class LayoutPart:
    selector: str
    minimum: int = 1
    maximum: int | None = 1

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
    KitLayout("cards", "two to four parallel points, each a .card with an optional .label or .value, an <h3> and a <p>", (TITLE, LayoutPart(".card", 2, 4))),
    KitLayout("comparison", "two options side by side, each a .column with .label, <h3> and <ul>; .pick marks the recommended one", (TITLE, LayoutPart(".column", 2, 2))),
    KitLayout("timeline", "a sequence of three to six .step blocks, each with a .label date, <h3> and <p>; .done fills the dot", (TITLE, LayoutPart(".step", 3, 6))),
    KitLayout("table", "rows and columns the audience must read; numeric cells align right by themselves, tr.pick highlights a row", (TITLE, LayoutPart("table"))),
    KitLayout("chart", "a trend, ranking or share drawn from data attributes, with an optional .insight beside it", (TITLE, LayoutPart("figure[data-chart]"), LayoutPart(".insight", 0))),
    KitLayout("quote", "a customer's or expert's words in a <blockquote> with a .by line", (LayoutPart("blockquote"),)),
    KitLayout("image", "a photo that carries meaning on the left half, the text on the right", (TITLE, LayoutPart("img"))),
    KitLayout("closing", "the decision or next actions as .card blocks or an <ol>, on the deck's dark feature color", (TITLE, LayoutPart(".card", 0, 4))),
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
CHART_ATTRIBUTES = (
    "data-chart: " + ", ".join(chart_types()),
    "data-labels: category names separated by commas",
    "data-values: one number per label, for a single series",
    "data-series: \"name: 1, 2, 3; other: 4, 5, 6\" for several series, each with one number per label",
    "data-unit: text after every value, such as 억, %, 건",
    "data-highlight: one label drawn in the accent color while the others are muted (single series)",
    "data-center, data-center-label: the text in a donut's hole; default the first slice's share",
    "data-zero: true starts a line chart's axis at zero",
    "<figcaption>: the unit, period and source under the chart",
)


def kit_layout(name: str) -> KitLayout | None:
    return next((layout for layout in KIT_LAYOUTS if layout.name == name), None)


def part_label(part: LayoutPart) -> str:
    count = str(part.minimum) if part.maximum == part.minimum else f"{part.minimum}-{part.maximum}" if part.maximum else f"{part.minimum}+"
    return f"{part.selector.replace('|', ' or ')} x{count}"


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


def chart_lines() -> list[str]:
    return [f"  {attribute}" for attribute in CHART_ATTRIBUTES]


GUIDE_SECTIONS = (
    ("Themes (<body data-theme=\"...\">)", theme_lines),
    ("Layouts (<section data-layout=\"...\">; parts are direct children of the section)", layout_lines),
    ("Charts (<figure data-chart=\"...\"> in a chart slide)", chart_lines),
)

GUIDE_INPUTS = (
    ("deck apply <file.pptx> <ops.json>", ListOf(OPERATIONS, non_empty=True)),
    ("deck merge <template.pptx> <values.json> <output.pptx>: values", MERGE_VALUES),
)
GUIDE_INPUTS_ON_REQUEST = ("deck apply",)
GUIDE_ISSUES = (
    ("deck build", BUILD_ISSUE_KINDS + REVIEW_ISSUE_KINDS),
    ("deck validate", VALIDATE_ISSUE_KINDS),
    ("deck apply", OPERATION_ISSUE_KINDS + APPLY_ISSUE_KINDS + LAYOUT_AUDIT_ISSUE_KINDS),
    ("deck check", SOURCE_CHECK_ISSUE_KINDS + LAYOUT_AUDIT_ISSUE_KINDS + PPTX_CHECK_ISSUE_KINDS),
    ("deck merge", PACKAGE_MERGE_ISSUE_KINDS),
    ("deck restore", (NO_SLIDE_SECTIONS,)),
    ("deck accept", ACCEPT_ISSUE_KINDS),
    ("deck image", IMAGE_ISSUE_KINDS),
)
