from __future__ import annotations


from fonts.registry import DECK, default_family
from deck.deck_guide import DESIGN_TOPIC, design_text, guide_preamble  # noqa: F401
from deck.deck_kit import chart_types, icon_names, kit_number, slide_size
from deck.layout_thresholds import EMPTY_REGION_SHARE_MAXIMUM, IMAGE_UPSCALE_MAXIMUM, LABEL_LINE_MAXIMUM, LARGE_TEXT_CONTRAST_MINIMUM, MARK_BREADTH_MINIMUM, REPEATED_FIGURE_MINIMUM, ROUND_SLOT_MINIMUM, SMALLEST_TEXT_SHARE_OF_WIDTH, TEXT_CONTRAST_MINIMUM, TITLE_LINE_MAXIMUM
from core.office_commands import EVERY_KIND
from core.office_result import ERROR, WARNING, IssueKind
from powerpoint.definitions import CHART_POINT_OUTSIDE_AXIS, CHART_ZERO_MISALIGNED, CONTENT_OVERFLOW, IMAGE_DISTORTED, OUT_OF_FRAME, SLIDE_COUNT_MISMATCH, TEXT_OVERLAP, review_check
from core.design_rules import DESIGN_RULE_KINDS
from deck.design_system import DESIGN_ISSUE_KINDS
from deck.deck_html import RENDER_GATE_SKIPPED
from render.renderer import RENDER_ISSUE_KINDS
from core.text_checks import PLACEHOLDER_LEFT, TEXT_CHECK_ISSUE_KINDS


SLIDE_BLANK = review_check("SLIDE_BLANK", "the slide render shows no content", "check that the slide's content is not hidden or outside the frame")
TEXT_COVERED = review_check("TEXT_COVERED", "a box painted over text hides part of it", "follow the suggestion, which names the cause: rows, items or text that do not fit, or a custom style that moves a part over another")
TITLE_TOO_LONG = review_check("TITLE_TOO_LONG", f"a slide title runs past {TITLE_LINE_MAXIMUM} lines", "state the conclusion in one short sentence and move the detail into the body or the speaker notes")
LABEL_TOO_LONG = review_check("LABEL_TOO_LONG", f"a .label wraps past {LABEL_LINE_MAXIMUM} lines", "shorten the label to the name of the measure and put the detail in a line under it or in the speaker notes")
REPEATED_FIGURE = review_check("REPEATED_FIGURE", f"one slide shows the same figure, a number with its unit, {REPEATED_FIGURE_MINIMUM} or more times", "show each figure once where it carries the point: give the other places a different fact, such as the change or the comparison, or set a donut's data-center to another number")
TINY_TEXT = review_check("TINY_TEXT", f"rendered text is smaller than {SMALLEST_TEXT_SHARE_OF_WIDTH * slide_size()[0]:g}px on a {slide_size()[0]}px slide ({SMALLEST_TEXT_SHARE_OF_WIDTH:.2%} of its width)", "shorten or split the slide so its text stays at 18px or larger")
CHART_UNDERFILLED = review_check("CHART_UNDERFILLED", f"a chart's marks fill too little of the room it is given: bars cover less than {MARK_BREADTH_MINIMUM:.0%} of their axis, or a donut or pie is under {ROUND_SLOT_MINIMUM:.0%} of its slot's longer side", "give the chart's figure a larger width and height, or fewer margins around it; two or three values read best beside a sentence that names the point")
IMAGE_LOW_RESOLUTION = review_check("IMAGE_LOW_RESOLUTION", f"a photo is drawn more than {IMAGE_UPSCALE_MAXIMUM:g} times its own pixel size, so it shows soft", "use a larger image of the same subject, or move this one where its frame is smaller, such as a cover's panel instead of the whole slide")
DRAWING_DISTORTED = review_check("DRAWING_DISTORTED", "a drawing that must keep its proportions, such as a donut or pie chart, is stretched into another shape", "give the donut or pie a square slot; it is always drawn as a circle")
TEXT_LOW_CONTRAST = review_check("TEXT_LOW_CONTRAST", f"text is too close in color to what is drawn behind it: under {TEXT_CONTRAST_MINIMUM:g}:1, or {LARGE_TEXT_CONTRAST_MINIMUM:g}:1 for large text", "change the text color or what lies behind it until the text reads at the ratio the message names")
GRID_MISALIGNED = review_check("GRID_MISALIGNED", "parts of one kind that sit side by side share neither a top edge nor a middle, parts stacked in a column share no left, center or right edge, or the gaps between parts in one row or column differ", "align the part the message names with its siblings, with one top edge, one center or one gap")
TITLE_STYLE_INCONSISTENT = review_check("TITLE_STYLE_INCONSISTENT", "a slide's title differs in typeface, weight, color, alignment or indent from the titles of the deck's other slides of its kind", "give this title the typeface, weight and alignment the other titles share, or leave it when the difference is deliberate")

TOPIC_TITLE = review_check("TOPIC_TITLE", "the title is a topic label, not a claim", "write the title as the slide's conclusion")
LANGUAGE_MISMATCH = review_check("LANGUAGE_MISMATCH", "slide titles are Latin-only in a Korean deck", "write the titles in the request language")
UNSOURCED_CURRENT_DATE = review_check("UNSOURCED_CURRENT_DATE", "a slide shows today's date that the source does not", "show only dates from the source material")
VERTICAL_DEAD_ZONE = review_check("VERTICAL_DEAD_ZONE", "an empty band spans much of the slide height, between content, under the body or inside a card", "resize, re-place or re-space the parts so the content uses the frame; add no words of your own")
EMPTY_REGION = review_check("EMPTY_REGION", f"an empty rectangle inside the content takes {EMPTY_REGION_SHARE_MAXIMUM:.0%} or more of its area, such as a half-width box with nothing beside it or a card that stops halfway down its chart; space split evenly around a part is centring and does not count", "resize or re-place the parts so the space is used; add no words of your own")
EMOJI_ICON = review_check("EMOJI_ICON", "a slide uses emoji glyphs", "use a word, or an icon from office guide slides, instead of the emoji glyph")
MISSING_SPEAKER_NOTES = review_check("MISSING_SPEAKER_NOTES", "a slide has no speaker notes", 'add an <aside class="notes"> script to every slide')

SLIDE_RENDER_CHECKS = (SLIDE_BLANK, CONTENT_OVERFLOW, OUT_OF_FRAME, TEXT_OVERLAP, TEXT_COVERED, TITLE_TOO_LONG, LABEL_TOO_LONG, REPEATED_FIGURE, IMAGE_DISTORTED, IMAGE_LOW_RESOLUTION, DRAWING_DISTORTED, CHART_UNDERFILLED, TINY_TEXT, TEXT_LOW_CONTRAST, GRID_MISALIGNED, TITLE_STYLE_INCONSISTENT)
DESIGN_CHECKS = (
    TOPIC_TITLE,
    LANGUAGE_MISMATCH,
    UNSOURCED_CURRENT_DATE,
    VERTICAL_DEAD_ZONE,
    EMPTY_REGION,
    EMOJI_ICON,
    MISSING_SPEAKER_NOTES,
)
REVIEW_ISSUE_KINDS = tuple(check.kind for check in SLIDE_RENDER_CHECKS + DESIGN_CHECKS)

SOURCE_NOT_HTML = IssueKind("SOURCE_NOT_HTML", ERROR, "the deck source is not an .html file", "write slides.html, or pass --source with an .html file")
NO_SLIDE_SECTIONS = IssueKind("NO_SLIDE_SECTIONS", ERROR, "the HTML has no <section> slides", "put each slide in its own <section>")
FONT_NOT_EMBEDDED = IssueKind("FONT_NOT_EMBEDDED", WARNING, "the PPTX names a font it could not embed, so the recipient sees a substitute unless that font is installed", f"use {default_family(DECK).name}, or tell the recipient which font to install")
TEXT_KEPT_AS_PICTURE = IssueKind("TEXT_KEPT_AS_PICTURE", WARNING, "some slide text is drawn into the slide picture, so the recipient cannot edit it", "name that text when delivering; rotated, skewed, filtered, gradient-clipped and SVG text stays a picture")

SLIDE_WITHOUT_CONTENT = IssueKind("SLIDE_WITHOUT_CONTENT", ERROR, "a slide has no visible text, image or chart", "give the slide its content or delete it")
CHART_DATA_INVALID = IssueKind("CHART_DATA_INVALID", ERROR, "a chart's data attributes do not parse or do not line up", "give data-labels and data-values (or data-series) the same number of plain numbers")
IMAGE_NOT_FOUND = IssueKind("IMAGE_NOT_FOUND", ERROR, "an image is remote or its file does not exist, so the slide would show an empty box", "point src at an image office guide design lists, or remove the image")
ICON_UNKNOWN = IssueKind("ICON_UNKNOWN", ERROR, "a data-icon names an icon the kit does not ship", "use a name office guide slides lists under Icons, or drop the data-icon")
OFF_PALETTE_COLOR = IssueKind("OFF_PALETTE_COLOR", WARNING, "the source uses colors outside the DESIGN.md palette", "use the tokens such as var(--accent) and var(--text), or name the color in DESIGN.md colors")

SOURCE_CHECK_ISSUE_KINDS = (
    SOURCE_NOT_HTML,
    NO_SLIDE_SECTIONS,
    SLIDE_COUNT_MISMATCH,
    SLIDE_WITHOUT_CONTENT,
    CHART_DATA_INVALID,
    ICON_UNKNOWN,
    IMAGE_NOT_FOUND,
    PLACEHOLDER_LEFT,
    *TEXT_CHECK_ISSUE_KINDS,
    OFF_PALETTE_COLOR,
    *DESIGN_ISSUE_KINDS,
    *DESIGN_RULE_KINDS.values(),
    RENDER_GATE_SKIPPED,
)

BUILD_ISSUE_KINDS = (
    *RENDER_ISSUE_KINDS,
    FONT_NOT_EMBEDDED,
    TEXT_KEPT_AS_PICTURE,
    CHART_POINT_OUTSIDE_AXIS.kind,
    CHART_ZERO_MISALIGNED.kind,
)

IMAGE_SEARCH_FAILED = IssueKind("IMAGE_SEARCH_FAILED", ERROR, "the image search could not be reached", "skip imagery or try a simpler English query")
NO_IMAGE_FOUND = IssueKind("NO_IMAGE_FOUND", ERROR, "no usable public-domain image matched", "try a simpler English query or skip imagery")

IMAGE_ISSUE_KINDS = (IMAGE_SEARCH_FAILED, NO_IMAGE_FOUND)
DESIGN_TOKEN_NAMES = ("ground", "text", "text-soft", "muted", "line", "surface", "accent", "secondary", "on-accent", "size-display", "size-title", "size-body", "size-small", "radius", "border", "shadow", "margin", "gap")
CHART_ATTRIBUTES = (
    "data-chart: " + ", ".join(chart_types()),
    "data-labels: category names separated by commas",
    "data-values: one number per label, for a single series",
    "numbers are separated by a comma and a space, so \"1,200, 1,350\" is two numbers, and the unit goes in data-unit, never in the numbers",
    "data-series: \"name: 1, 2, 3; other: 4, 5, 6\" for several series, each with one number per label",
    f"combo: the last series is a line over the columns before it, on their axis; it gets its own axis on the right, zero level with theirs, when data-unit gives it another unit or the two differ more than {kit_number('separateAxisRatio')}-fold",
    "scatter: two series, the horizontal axis first and the vertical second; each label names one point",
    "stacked100: each column shows its series as shares of the column's total",
    "area: the series stacked as bands over the labels, a total over time and what it is made of",
    "data-unit: text after every value, such as M, % or a Korean number unit like \uc5b5; combo and scatter take one per axis, \"M, %\"",
    "data-highlight: one label drawn in the accent color while the others are muted (single series, or a scatter point)",
    "data-center, data-center-label: the text in a donut's hole; default the first slice's share",
    "data-zero: true starts a line chart's axis at zero",
    "<figcaption>: the unit, period and source under the chart, one unit and one source per chart",
    "the figure takes the width and height your CSS gives it; colors come from the tokens",
)


def canvas_lines() -> list[str]:
    return [
        "  each slide is a <section> of exactly 1600x900 px; write one <style> in <head> and lay every slide out yourself",
        "  DESIGN.md beside slides.html names the palette and the few other choices in its front matter; run office check DESIGN.md before any slide, then office check slides.html",
        f"  the build puts the tokens on :root, so write var(--accent) and the rest, never a color of your own: {', '.join('--' + name for name in DESIGN_TOKEN_NAMES)}",
        "  body text is 28px or larger and captions 20px or larger, and text reads at 4.5:1 on its background, or 3:1 from 24px; office create measures both. The build sets every font; font-family in your CSS is dropped",
        "  <aside class=\"notes\">: the speaker notes of a slide",
    ]


def font_lines() -> list[str]:
    from deck.deck_design import DESIGN

    return [f"  {', '.join(pairing['display'] for pairing in DESIGN['types'].values())}: DESIGN.md names one as type, and the PDF and PPTX carry it"]


def icon_lines() -> list[str]:
    return [
        "  <i data-icon=\"name\"></i> becomes a line icon in currentColor, as large as its font-size, on a line of its own or as an item in a flex row, a picture in the PPTX",
        f"  names: {', '.join(icon_names())}",
    ]


def chart_lines() -> list[str]:
    return [f"  {attribute}" for attribute in CHART_ATTRIBUTES]


def photo_lines() -> list[str]:
    return [
        "  office guide design lists the company logo and the photos you can use",
        "  <img src=\"<listed path>\"> with object-fit: cover in a frame of your own; the build sets each photo's focal point",
        "  the company logo is placed by the build on the cover and the closing slide; write no <img data-logo>",
    ]


GUIDE_SECTIONS = (
    ("slides", "Canvas and design system", canvas_lines),
    ("slides", "Fonts", font_lines),
    ("slides", "Icons", icon_lines),
    ("slides", "Charts (<figure data-chart=\"...\">, drawn as native charts in the PPTX)", chart_lines),
    ("slides", "Photos and logo", photo_lines),
)

GUIDE_ISSUES = (
    ("create", "slides", SOURCE_CHECK_ISSUE_KINDS + BUILD_ISSUE_KINDS + REVIEW_ISSUE_KINDS),
    ("check", "slides", SOURCE_CHECK_ISSUE_KINDS),
    ("image", EVERY_KIND, IMAGE_ISSUE_KINDS),
)

GUIDE_TOPICS = {DESIGN_TOPIC: design_text}
