from __future__ import annotations

import re

from core.office_result import ERROR, Issue, IssueKind


PLACEHOLDER_PATTERN = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|(?i:lorem ipsum)|\b(?:TODO|TBD|FIXME)\b|(?<![A-Za-z])X{2,}(?![A-Za-z])|○○|(?i:\[(?:insert|placeholder)[^\]]*\])")

REQUIRED_TEXT_MISSING = IssueKind("REQUIRED_TEXT_MISSING", ERROR, "a --required-text value does not appear in the file's visible text", "put the source fact in the visible content, then rebuild")
FORBIDDEN_TEXT_PRESENT = IssueKind("FORBIDDEN_TEXT_PRESENT", ERROR, "a --forbidden-text value appears in the file's visible text", "remove the unsupported text, then rebuild")
PLACEHOLDER_LEFT = IssueKind("PLACEHOLDER_LEFT", ERROR, "template placeholder syntax, a merge field, or draft text such as TODO or lorem ipsum is still in the text", "replace it with the real value")

TEXT_CHECK_ISSUE_KINDS = (REQUIRED_TEXT_MISSING, FORBIDDEN_TEXT_PRESENT)


def text_presence_issues(visible_text: str, required_text: list[str] | tuple[str, ...], forbidden_text: list[str] | tuple[str, ...]) -> list[Issue]:
    searched = comparable(visible_text)
    missing = [REQUIRED_TEXT_MISSING.issue(f"required text is missing: {value}", location=value) for value in required_text if not appears(value, searched)]
    present = [FORBIDDEN_TEXT_PRESENT.issue(f"forbidden text is present: {value}", location=value) for value in forbidden_text if appears(value, searched)]
    return missing + present


def comparable(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def appears(value: str, searched: str) -> bool:
    wanted = comparable(value)
    return wanted in searched or wanted.replace(" ", "") in searched.replace(" ", "")
