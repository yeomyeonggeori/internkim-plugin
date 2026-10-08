from __future__ import annotations


from fonts.registry import DECK, default_family
from deck.deck_guide import DESIGN_TOPIC, design_text, guide_preamble  # noqa: F401
from deck.deck_kit import chart_types, icon_names, kit_number
from deck.layout_thresholds import IMAGE_UPSCALE_MAXIMUM, LARGE_TEXT_CONTRAST_MINIMUM, TEXT_CONTRAST_MINIMUM
from core.office_commands import EVERY_KIND
from core.office_result import ERROR, WARNING, IssueKind
from powerpoint.definitions import CHART_POINT_OUTSIDE_AXIS, CHART_ZERO_MISALIGNED, IMAGE_DISTORTED, SLIDE_COUNT_MISMATCH, review_check
from core.design_rules import DESIGN_RULE_KINDS
from deck.design_system import DESIGN_ISSUE_KINDS
from deck.draft_claims import UNSUPPORTED_CLAIM
from deck.deck_html import RENDER_GATE_SKIPPED
from deck.composition import REPEATED_COMPOSITION
from deck.outline import OUTLINE_ISSUE_KINDS
from deck.page_checks import PAGE_CHECK_ISSUE_KINDS
from deck.check_deck import STAGE_ISSUE_KINDS
from render.renderer import RENDER_ISSUE_KINDS
from core.text_checks import PLACEHOLDER_LEFT, TEXT_CHECK_ISSUE_KINDS


SLIDE_BLANK = review_check("SLIDE_BLANK", "the slide render shows no content", "check that the slide's content is not hidden or outside the frame")
TEXT_COVERED = review_check("TEXT_COVERED", "a box painted over text hides part of it", "move the box or the text apart, or shorten the text so it fits beside the box")
IMAGE_LOW_RESOLUTION = review_check("IMAGE_LOW_RESOLUTION", f"a photo is drawn more than {IMAGE_UPSCALE_MAXIMUM:g} times its own pixel size, so it shows soft", "use a larger image of the same subject, or give this one a smaller frame")
DRAWING_DISTORTED = review_check("DRAWING_DISTORTED", "a drawing that must keep its proportions, such as a donut or pie chart, is stretched into another shape", "give the donut or pie a square slot; it is always drawn as a circle")
TEXT_LOW_CONTRAST = review_check("TEXT_LOW_CONTRAST", f"text is too close in color to what is drawn behind it: under {TEXT_CONTRAST_MINIMUM:g}:1, or {LARGE_TEXT_CONTRAST_MINIMUM:g}:1 for large text", "change the text color or what lies behind it until the text reads at the ratio the message names")
EMOJI_ICON = review_check("EMOJI_ICON", "a slide uses emoji glyphs", "use a word, or an icon from office guide slides, instead of the emoji glyph")
MISSING_SPEAKER_NOTES = review_check("MISSING_SPEAKER_NOTES", "a slide has no speaker notes", 'add an <aside class="notes"> script to every page')

SLIDE_RENDER_CHECKS = (SLIDE_BLANK, TEXT_COVERED, IMAGE_DISTORTED, IMAGE_LOW_RESOLUTION, DRAWING_DISTORTED, TEXT_LOW_CONTRAST, EMOJI_ICON, MISSING_SPEAKER_NOTES)
REVIEW_ISSUE_KINDS = tuple(check.kind for check in SLIDE_RENDER_CHECKS)

FONT_NOT_EMBEDDED = IssueKind("FONT_NOT_EMBEDDED", WARNING, "the PPTX names a font it could not embed, so the recipient sees a substitute unless that font is installed", f"use {default_family(DECK).name}, or tell the recipient which font to install")
TEXT_KEPT_AS_PICTURE = IssueKind("TEXT_KEPT_AS_PICTURE", WARNING, "some slide text is drawn into the slide picture, so the recipient cannot edit it", "name that text when delivering; rotated, skewed, filtered, gradient-clipped and SVG text stays a picture")
SOURCE_NOT_HTML = IssueKind("SOURCE_NOT_HTML", ERROR, "the deck source is not an .html file", "build the deck from its folder: office create build/<deck>.pptx .")
NO_SLIDE_SECTIONS = IssueKind("NO_SLIDE_SECTIONS", ERROR, "the HTML has no <section> slides", "write each page as one <section> in pages/NN.html")

CHECK_ISSUE_KINDS = (
    *STAGE_ISSUE_KINDS,
    *DESIGN_ISSUE_KINDS,
    *OUTLINE_ISSUE_KINDS,
    *PAGE_CHECK_ISSUE_KINDS,
    SLIDE_COUNT_MISMATCH,
    PLACEHOLDER_LEFT,
    *TEXT_CHECK_ISSUE_KINDS,
    UNSUPPORTED_CLAIM,
    *DESIGN_RULE_KINDS.values(),
    REPEATED_COMPOSITION,
    RENDER_GATE_SKIPPED,
)

BUILD_ISSUE_KINDS = (
    *RENDER_ISSUE_KINDS,
    SOURCE_NOT_HTML,
    NO_SLIDE_SECTIONS,
    FONT_NOT_EMBEDDED,
    TEXT_KEPT_AS_PICTURE,
    CHART_POINT_OUTSIDE_AXIS.kind,
    CHART_ZERO_MISALIGNED.kind,
)

IMAGE_SEARCH_FAILED = IssueKind("IMAGE_SEARCH_FAILED", ERROR, "the image search could not be reached", "skip imagery or try a simpler English query")
NO_IMAGE_FOUND = IssueKind("NO_IMAGE_FOUND", ERROR, "no usable public-domain image matched", "try a simpler English query or skip imagery")

IMAGE_ISSUE_KINDS = (IMAGE_SEARCH_FAILED, NO_IMAGE_FOUND)
DESIGN_TOKEN_NAMES = ("text", "accent", "secondary", "surface", "line", "ground", "muted", "text-soft", "on-accent", "size-display", "size-title", "size-body", "size-small", "radius")
CHART_ATTRIBUTES = (
    "data-chart: " + ", ".join(chart_types()),
    "data-labels: the labels of the page's outline figures it plots, separated by commas; data-values and data-series give those figures' values, and data-unit their unit",
    "data-values: one number per label, for a single series",
    "numbers are separated by a comma and a space, so \"1,200, 1,350\" is two numbers, and the unit goes in data-unit, never in the numbers",
    "data-series: \"name: 1, 2, 3; other: 4, 5, 6\" for several series, each with one number per label",
    f"combo: the last series is a line over the columns before it, on their axis; it gets its own axis on the right, zero level with theirs, when data-unit gives it another unit or the two differ more than {kit_number('separateAxisRatio')}-fold",
    "scatter: two series, the horizontal axis first and the vertical second; each label names one point",
    "stacked100: each column shows its series as shares of the column's total",
    "area: the series stacked as bands over the labels, a total over time and what it is made of",
    "data-unit: text after every value, such as M, % or a Korean number unit like 억; combo and scatter take one per axis, \"M, %\"",
    "data-highlight: one label drawn in the accent color while the others are muted (single series, or a scatter point)",
    "data-center, data-center-label: the text in a donut's hole; default the first slice's share",
    "data-zero: true starts a line chart's axis at zero",
    "<figcaption>: the unit and period under the chart, and a source only when the request names one",
    "the figure takes the width and height your CSS gives it, at least 320 by 240 px; colors come from the style sheet",
)


def canvas_lines() -> list[str]:
    return [
        "  a page is pages/NN.html: one <section> of 1600x900 px holding its own <style>; the build scopes that style to the page, so write plain selectors",
        "  the build gives the section the background its page type has in DESIGN.md; give a part another background only from the style sheet's colors",
        f"  tokens on :root: {', '.join('--' + name for name in DESIGN_TOKEN_NAMES)}; a hex value the style sheet names may be written as it is",
        "  the build sets every font; font-family in your CSS is dropped",
        "  <aside class=\"notes\">: the speaker notes of a page",
    ]


def font_lines() -> list[str]:
    from deck.typeface import TYPEFACE

    return [f"  {', '.join(pairing['display'] for pairing in TYPEFACE['types'].values())}: InternKim chooses one from the request; DESIGN.md may name another of these as type, and the PDF and PPTX carry it"]


def icon_lines() -> list[str]:
    return [
        "  <i data-icon=\"name\"></i> becomes a line icon in currentColor, as large as its font-size, a picture in the PPTX",
        f"  names: {', '.join(icon_names())}",
    ]


def chart_lines() -> list[str]:
    return [f"  {attribute}" for attribute in CHART_ATTRIBUTES]


def photo_lines() -> list[str]:
    return [
        "  office guide design lists the company logo and the photos you can use",
        "  <img src=\"<listed path>\"> with object-fit: cover in a frame of your own; the build sets each photo's focal point",
        "  the company logo is placed by the build on the cover and the closing page; write no <img data-logo>",
    ]


GUIDE_SECTIONS = (
    ("slides", "Pages", canvas_lines),
    ("slides", "Fonts", font_lines),
    ("slides", "Icons", icon_lines),
    ("slides", "Charts (<figure data-chart=\"...\">, drawn as native charts in the PPTX)", chart_lines),
    ("slides", "Photos and logo", photo_lines),
)

GUIDE_ISSUES = (
    ("create", "slides", CHECK_ISSUE_KINDS + BUILD_ISSUE_KINDS + REVIEW_ISSUE_KINDS),
    ("check", "slides", CHECK_ISSUE_KINDS),
    ("image", EVERY_KIND, IMAGE_ISSUE_KINDS),
)

GUIDE_TOPICS = {DESIGN_TOPIC: design_text}
