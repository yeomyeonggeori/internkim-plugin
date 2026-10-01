from __future__ import annotations

from dataclasses import dataclass
import json
import pathlib

from deck_definitions import CONTENT_OVERFLOW, FOOTER_CROSSED, GEOMETRY_NOT_MEASURED, IMAGE_DISTORTED, OUT_OF_FRAME, TEXT_COVERED, TEXT_OVERLAP, TINY_TEXT, TITLE_TOO_LONG
from design_warnings import append_deck_warning
from office_result import Issue


GEOMETRY_FILE_NAME = "geometry.json"
FINDINGS_NAMED_PER_ISSUE = 3
FOOTER_HEIGHT_RATIO = 0.08
FOOTER_BOTTOM_RATIO = 0.85


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
    if bands[-1][1] < height * FOOTER_BOTTOM_RATIO:
        return len(bands)
    start = len(bands)
    for index in range(len(bands) - 1, 0, -1):
        if bands[-1][1] - bands[index][0] > height * FOOTER_HEIGHT_RATIO:
            break
        start = index
    return start


def geometry_warnings(measured: dict[str, object] | None) -> list[Issue]:
    if measured is None:
        return []
    return [
        *finding_issues(CONTENT_OVERFLOW, measured["overflow"], describe_overflow, "{count} elements hold more than their box shows"),
        *finding_issues(OUT_OF_FRAME, measured["outOfFrame"], describe_out_of_frame, "{count} elements lie outside the slide"),
        *finding_issues(TEXT_OVERLAP, measured["overlaps"], describe_overlap, "{count} pairs of text overlap"),
        *finding_issues(TEXT_COVERED, measured.get("coveredText", []), describe_covered_text, "{count} text elements are hidden under a box drawn over them"),
        *finding_issues(FOOTER_CROSSED, measured.get("footerCrossings", []), describe_footer_crossing, "{count} parts of the slide reach into the footer"),
        *finding_issues(TITLE_TOO_LONG, measured.get("longTitles", []), describe_long_title, "{count} titles run past three lines"),
        *finding_issues(IMAGE_DISTORTED, measured["distortedImages"], describe_distorted_image, "{count} images are stretched"),
        *finding_issues(TINY_TEXT, measured.get("smallText", []), describe_small_text, "{count} text elements are smaller than the slide can show legibly"),
    ]


def finding_issues(check, findings: list[dict[str, object]], describe, headline: str) -> list[Issue]:
    if not findings:
        return []
    named = "; ".join(describe(finding) for finding in findings[:FINDINGS_NAMED_PER_ISSUE])
    remainder = len(findings) - FINDINGS_NAMED_PER_ISSUE
    more = f"; and {remainder} more" if remainder > 0 else ""
    return [check.issue(f"{headline.format(count=len(findings))}: {named}{more}")]


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


def describe_distorted_image(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} renders at ratio {finding['renderedRatio']} but is {finding['naturalRatio']}"


def describe_small_text(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} is {finding['fontSize']}px, below the {finding['minimum']}px minimum (1% of the slide width)"


def apply_geometry_not_measured_warning(slides: list[dict[str, object]], geometry: list[dict[str, object]] | None) -> None:
    if geometry is None:
        append_deck_warning(slides, GEOMETRY_NOT_MEASURED.deck_issue("no geometry.json was written, so the layout was not measured"))
