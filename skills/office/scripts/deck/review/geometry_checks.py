from __future__ import annotations

import json
import pathlib

from deck.deck_definitions import DRAWING_DISTORTED, IMAGE_LOW_RESOLUTION, TEXT_COVERED, TEXT_LOW_CONTRAST
from powerpoint.definitions import IMAGE_DISTORTED
from core.office_result import Issue


GEOMETRY_FILE_NAME = "geometry.json"
FINDINGS_NAMED_PER_ISSUE = 3


def read_geometry(review_path: pathlib.Path) -> list[dict[str, object]] | None:
    geometry_path = review_path / GEOMETRY_FILE_NAME
    if not geometry_path.exists():
        return None
    return json.loads(geometry_path.read_text(encoding="utf-8"))["slides"]


def geometry_warnings(measured: dict[str, object] | None) -> list[Issue]:
    if measured is None:
        return []
    return [
        issue
        for check, key, describe, headline in GEOMETRY_FINDINGS
        for issue in finding_issues(check, measured.get(key, []), describe, headline)
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


def describe_covered_text(finding: dict[str, object]) -> str:
    return f"{element_label(finding['text'])} lies {finding['ratio']:.0%} under {element_label(finding['box'])}"


def describe_distorted_image(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} renders at ratio {finding['renderedRatio']} but is {finding['naturalRatio']}"


def describe_soft_image(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} is {finding['naturalWidth']}x{finding['naturalHeight']} pixels drawn at {finding['scale']} times that"


def describe_low_contrast(finding: dict[str, object]) -> str:
    return f"{element_label(finding)} reads at {finding['ratio']:g}:1 against what is behind it, under {finding['minimum']:g}:1"


GEOMETRY_FINDINGS = (
    (TEXT_COVERED, "coveredText", describe_covered_text, "{count} text elements are hidden under a box drawn over them"),
    (IMAGE_DISTORTED, "distortedImages", describe_distorted_image, "{count} images are stretched"),
    (IMAGE_LOW_RESOLUTION, "softImages", describe_soft_image, "{count} photos are drawn larger than their pixels"),
    (DRAWING_DISTORTED, "distortedDrawings", describe_distorted_image, "{count} drawings are stretched out of their own proportions"),
    (TEXT_LOW_CONTRAST, "lowContrastText", describe_low_contrast, "{count} text elements are too faint to read on their background"),
)

