from __future__ import annotations

from dataclasses import dataclass
import json
import pathlib

from deck.deck_definitions import CHART_UNDERFILLED, DRAWING_DISTORTED, FOOTER_CROSSED, GRID_MISALIGNED, IMAGE_LOW_RESOLUTION, LABEL_TOO_LONG, REPEATED_FIGURE, TEXT_COVERED, TEXT_LOW_CONTRAST, TINY_TEXT, TITLE_TOO_LONG
from powerpoint.definitions import CONTENT_OVERFLOW, IMAGE_DISTORTED, OUT_OF_FRAME, TEXT_OVERLAP
from deck.deck_kit import kit_length, slide_size
from deck.review.kit_fixes import capacity_fix, photo_fix, placement_fix, size_fix, text_fix
from deck.layout_thresholds import LABEL_LINE_MAXIMUM, SMALLEST_TEXT_SHARE_OF_WIDTH, TITLE_LINE_MAXIMUM
from core.office_result import Issue


GEOMETRY_FILE_NAME = "geometry.json"
FINDINGS_NAMED_PER_ISSUE = 3
SLIDE_HEIGHT = slide_size()[1]
FOOTER_HEIGHT_RATIO = kit_length("footer-height") / SLIDE_HEIGHT
FOOTER_REACH_RATIO = 2 * FOOTER_HEIGHT_RATIO
SELF_EXPLAINED_CHECKS = (TITLE_TOO_LONG, LABEL_TOO_LONG, REPEATED_FIGURE, IMAGE_LOW_RESOLUTION, DRAWING_DISTORTED, CHART_UNDERFILLED, TEXT_LOW_CONTRAST, GRID_MISALIGNED)


@dataclass(frozen=True)
class ContentExtent:
    body_bottom_ratio: float
    unfilled_ratio: float
    has_footer: bool
    gap_under_title_ratio: float


def read_geometry(review_path: pathlib.Path) -> list[dict[str, object]] | None:
    geometry_path = review_path / GEOMETRY_FILE_NAME
    if not geometry_path.exists():
        return None
    return json.loads(geometry_path.read_text(encoding="utf-8"))["slides"]


def slide_geometry(geometry: list[dict[str, object]] | None, index: int) -> dict[str, object] | None:
    if geometry is None or index > len(geometry):
        return None
    return geometry[index - 1]


def content_extent(measured: dict[str, object] | None) -> ContentExtent | None:
    if measured is None or not measured["contentBands"]:
        return None
    bands, height = measured["contentBands"], measured["height"]
    footer_start = footer_start_index(bands, height)
    body_bottom = bands[footer_start - 1][1]
    has_footer = footer_start < len(bands)
    floor = bands[footer_start][0] if has_footer else height - bands[0][0]
    gap_under_title = bands[1][0] - bands[0][1] if footer_start >= 2 else 0.0
    return ContentExtent(body_bottom / height, max(0.0, floor - body_bottom) / height, has_footer, gap_under_title / height)


def footer_start_index(bands: list[list[float]], height: float) -> int:
    if bands[-1][1] < height * (1 - FOOTER_REACH_RATIO):
        return len(bands)
    start = len(bands)
    for index in range(len(bands) - 1, 0, -1):
        if bands[-1][1] - bands[index][0] > height * FOOTER_HEIGHT_RATIO:
            break
        start = index
    return start


def geometry_warnings(measured: dict[str, object] | None, kit_layout: str = "") -> list[Issue]:
    if measured is None:
        return []
    return [
        issue
        for check, key, describe, headline in GEOMETRY_FINDINGS
        for issue in finding_issues(check, measured.get(key, []), describe, headline, kit_suggestion(check, measured, kit_layout))
    ]


def finding_issues(check, findings: list[dict[str, object]], describe, headline: str, kit_fix) -> list[Issue]:
    if not findings:
        return []
    named = "; ".join(describe(finding) for finding in findings[:FINDINGS_NAMED_PER_ISSUE])
    remainder = len(findings) - FINDINGS_NAMED_PER_ISSUE
    more = f"; and {remainder} more" if remainder > 0 else ""
    return [check.issue(f"{headline.format(count=len(findings))}: {named}{more}", suggestion=kit_fix(findings[0]) if kit_fix else None)]


def kit_suggestion(check, measured: dict[str, object], kit_layout: str):
    if not kit_layout or check in SELF_EXPLAINED_CHECKS:
        return None
    if check is IMAGE_DISTORTED:
        return lambda finding: photo_fix(kit_layout)
    capacity = measured.get("capacity") or []
    if capacity:
        return lambda finding: capacity_fix(capacity, kit_layout)
    return UNCROWDED_KIT_FIXES[check]


def covered_fix(finding: dict[str, object]) -> str:
    return placement_fix(f"{element_label(finding['box'])} is drawn over {element_label(finding['text'])}")


def overlap_fix(finding: dict[str, object]) -> str:
    return placement_fix(f"{element_label(finding['first'])} and {element_label(finding['second'])} share one place")


def overflow_fix(finding: dict[str, object]) -> str:
    return text_fix(element_label(finding), len(finding["text"]), round(len(finding["text"]) * finding["clientHeight"] / max(finding["scrollHeight"], 1)))


UNCROWDED_KIT_FIXES = {
    CONTENT_OVERFLOW: overflow_fix,
    OUT_OF_FRAME: lambda finding: placement_fix(f"{element_label(finding)} lies off the slide"),
    TEXT_OVERLAP: overlap_fix,
    TEXT_COVERED: covered_fix,
    FOOTER_CROSSED: lambda finding: placement_fix(f"{element_label(finding)} reaches into the footer"),
    TINY_TEXT: lambda finding: size_fix(finding["minimum"]),
}


def element_label(element: dict[str, object]) -> str:
    text = element["text"]
    return f"{element['selector']} \"{text}\"" if text else str(element["selector"])


def describe_overflow(finding: dict[str, object]) -> str:
    return (
        f"{element_label(finding)} needs {finding['scrollWidth']}x{finding['scrollHeight']}px "
        f"in a {finding['clientWidth']}x{finding['clientHeight']}px box"
    )


def describe_out_of_frame(finding: dict[str, object]) -> str:
    rect = finding["rect"]
    return f"{element_label(finding)} spans x {rect['left']}-{rect['right']}, y {rect['top']}-{rect['bottom']} on the page"


def describe_overlap(finding: dict[str, object]) -> str:
    return f"{element_label(finding['first'])} and {element_label(finding['second'])} overlap by {finding['ratio']:.0%} of the smaller text"


def describe_covered_text(finding: dict[str, object]) -> str:
    return f"{element_label(finding['text'])} lies {finding['ratio']:.0%} under {element_label(finding['box'])}"


def describe_footer_crossing(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} ends at y {finding['bottom']}, below the footer's top at y {finding['footerTop']}"


def describe_long_title(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} wraps to {finding['lines']} lines; keep a title to {finding['maximum']}"


def describe_long_label(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} wraps to {finding['lines']} lines; keep a label to {finding['maximum']}"


def describe_repeated_figure(finding: dict[str, object]) -> str:
    return f"{finding['figure']} is shown {finding['count']} times, in {', '.join(finding['places'])}"


def describe_distorted_image(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} renders at ratio {finding['renderedRatio']} but is {finding['naturalRatio']}"


def describe_soft_image(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} is {finding['naturalWidth']}x{finding['naturalHeight']} pixels drawn at {finding['scale']} times that"


def describe_underfilled_chart(finding: dict[str, object]) -> str:
    measure = "its bars cover" if finding["kind"] == "bars" else "its ring spans"
    room = "of the plot's category axis" if finding["kind"] == "bars" else "of its slot's longer side"
    return f"{element_label(finding)}: {measure} {finding['share']:.0%} {room}, under the {finding['minimum']:.0%} minimum"


def describe_small_text(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} is {finding['fontSize']}px, below the {finding['minimum']}px minimum ({SMALLEST_TEXT_SHARE_OF_WIDTH:.2%} of the slide width)"


def describe_low_contrast(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} reads at {finding['ratio']:g}:1 against what is behind it, under {finding['minimum']:g}:1"


MISALIGNMENT_WORDING = {
    "row": "share neither a top edge nor a middle; their tops are {offset:g}px apart",
    "column": "share no left, center or right edge; they are {offset:g}px apart",
    "row spacing": "are {offset:g}px further apart than the closest pair in their row",
    "column spacing": "are {offset:g}px further apart than the closest pair in their column",
}


def describe_misaligned(finding: dict[str, object]) -> str:
    return f"{element_label(finding['first'])} and {element_label(finding['second'])} {MISALIGNMENT_WORDING[finding['axis']].format(offset=finding['offset'])}"


GEOMETRY_FINDINGS = (
    (CONTENT_OVERFLOW, "overflow", describe_overflow, "{count} elements hold more than their box shows"),
    (OUT_OF_FRAME, "outOfFrame", describe_out_of_frame, "{count} elements lie outside the slide"),
    (TEXT_OVERLAP, "overlaps", describe_overlap, "{count} pairs of text overlap"),
    (TEXT_COVERED, "coveredText", describe_covered_text, "{count} text elements are hidden under a box drawn over them"),
    (FOOTER_CROSSED, "footerCrossings", describe_footer_crossing, "{count} parts of the slide reach into the footer"),
    (TITLE_TOO_LONG, "longTitles", describe_long_title, f"{{count}} titles run past {TITLE_LINE_MAXIMUM} lines"),
    (LABEL_TOO_LONG, "longLabels", describe_long_label, f"{{count}} labels run past {LABEL_LINE_MAXIMUM} lines"),
    (REPEATED_FIGURE, "repeatedFigures", describe_repeated_figure, "{count} figures are repeated on the slide"),
    (IMAGE_DISTORTED, "distortedImages", describe_distorted_image, "{count} images are stretched"),
    (IMAGE_LOW_RESOLUTION, "softImages", describe_soft_image, "{count} photos are drawn larger than their pixels"),
    (DRAWING_DISTORTED, "distortedDrawings", describe_distorted_image, "{count} drawings are stretched out of their own proportions"),
    (CHART_UNDERFILLED, "underfilledCharts", describe_underfilled_chart, "{count} charts leave most of their room empty"),
    (TINY_TEXT, "smallText", describe_small_text, "{count} text elements are smaller than the slide can show legibly"),
    (TEXT_LOW_CONTRAST, "lowContrastText", describe_low_contrast, "{count} text elements are too faint to read on their background"),
    (GRID_MISALIGNED, "misalignedSiblings", describe_misaligned, "{count} pairs of parts are out of line with each other"),
)

