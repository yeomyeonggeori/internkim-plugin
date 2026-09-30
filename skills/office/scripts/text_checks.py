from __future__ import annotations

import re

from office_result import ERROR, Issue, IssueKind


PLACEHOLDER_PATTERN = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")
KOREAN_FONT_NAME_FRAGMENTS = (
    "noto",
    "nanum",
    "malgun",
    "apple sd",
    "applegothic",
    "arialunicode",
    "arial unicode",
    "gothic",
    "myeongjo",
    "cjk",
    "kr",
    "맑은",
    "고딕",
)

REQUIRED_TEXT_MISSING = IssueKind("REQUIRED_TEXT_MISSING", ERROR, "a --required-text value does not appear in the file's visible text", "put the source fact in the visible content, then rebuild")
FORBIDDEN_TEXT_PRESENT = IssueKind("FORBIDDEN_TEXT_PRESENT", ERROR, "a --forbidden-text value appears in the file's visible text", "remove the unsupported text, then rebuild")
PLACEHOLDER_LEFT = IssueKind("PLACEHOLDER_LEFT", ERROR, "template placeholder syntax or a merge field is still in the text", "replace it with the real value")
KOREAN_FONT_MISSING = IssueKind("KOREAN_FONT_MISSING", ERROR, "the file has Korean text but names no Korean-capable font", "set a Korean-capable font such as Nanum Gothic or Noto Sans CJK")

TEXT_CHECK_ISSUE_KINDS = (REQUIRED_TEXT_MISSING, FORBIDDEN_TEXT_PRESENT, KOREAN_FONT_MISSING)


def text_presence_issues(visible_text: str, required_text: list[str], forbidden_text: list[str]) -> list[Issue]:
    missing = [REQUIRED_TEXT_MISSING.issue(f"required text is missing: {value}", location=value) for value in required_text if value not in visible_text]
    present = [FORBIDDEN_TEXT_PRESENT.issue(f"forbidden text is present: {value}", location=value) for value in forbidden_text if value in visible_text]
    return missing + present


def korean_font_issues(visible_text: str, font_names: list[str]) -> list[Issue]:
    if not contains_korean(visible_text) or names_korean_capable_font(font_names):
        return []
    return [KOREAN_FONT_MISSING.issue("the file contains Korean text but no Korean-capable font name was detected")]


def contains_korean(text: str) -> bool:
    return any("가" <= character <= "힣" for character in text)


def names_korean_capable_font(font_names: list[str]) -> bool:
    normalized_names = " ".join(font_name.lower() for font_name in font_names)
    return any(fragment in normalized_names for fragment in KOREAN_FONT_NAME_FRAGMENTS)
