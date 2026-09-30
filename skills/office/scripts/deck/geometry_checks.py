import json
import pathlib

from deck_definitions import CONTENT_OVERFLOW, GEOMETRY_NOT_MEASURED, IMAGE_DISTORTED, OUT_OF_FRAME, TEXT_OVERLAP
from design_warnings import append_deck_warning
from office_result import Issue


GEOMETRY_FILE_NAME = "geometry.json"
FINDINGS_NAMED_PER_ISSUE = 3


def read_geometry(review_path: pathlib.Path) -> list[dict[str, object]] | None:
    geometry_path = review_path / GEOMETRY_FILE_NAME
    if not geometry_path.exists():
        return None
    return json.loads(geometry_path.read_text(encoding="utf-8"))["slides"]


def slide_geometry(geometry: list[dict[str, object]] | None, index: int) -> dict[str, object] | None:
    if geometry is None or index > len(geometry):
        return None
    return geometry[index - 1]


def geometry_warnings(measured: dict[str, object] | None) -> list[Issue]:
    if measured is None:
        return []
    return [
        *finding_issues(CONTENT_OVERFLOW, measured["overflow"], describe_overflow, "{count} elements hold more than their box shows"),
        *finding_issues(OUT_OF_FRAME, measured["outOfFrame"], describe_out_of_frame, "{count} elements lie outside the slide"),
        *finding_issues(TEXT_OVERLAP, measured["overlaps"], describe_overlap, "{count} pairs of text overlap"),
        *finding_issues(IMAGE_DISTORTED, measured["distortedImages"], describe_distorted_image, "{count} images are stretched"),
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


def describe_distorted_image(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} renders at ratio {finding['renderedRatio']} but is {finding['naturalRatio']}"


def apply_geometry_not_measured_warning(slides: list[dict[str, object]], geometry: list[dict[str, object]] | None) -> None:
    if geometry is None:
        append_deck_warning(slides, GEOMETRY_NOT_MEASURED.deck_issue("no geometry.json was written, so the layout was not measured"))
