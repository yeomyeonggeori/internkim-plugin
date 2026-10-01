from __future__ import annotations

import re

from office_result import ERROR, Issue, IssueKind


PLACEHOLDER_PATTERN = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")
DRAFT_PLACEHOLDER_PATTERN = re.compile(PLACEHOLDER_PATTERN.pattern + r"|(?i:lorem ipsum)|\b(?:TODO|TBD|FIXME)\b|(?<![A-Za-z])X{2,}(?![A-Za-z])|○○|(?i:\[(?:insert|placeholder)[^\]]*\])")

REQUIRED_TEXT_MISSING = IssueKind("REQUIRED_TEXT_MISSING", ERROR, "a --required-text value does not appear in the file's visible text", "put the source fact in the visible content, then rebuild")
FORBIDDEN_TEXT_PRESENT = IssueKind("FORBIDDEN_TEXT_PRESENT", ERROR, "a --forbidden-text value appears in the file's visible text", "remove the unsupported text, then rebuild")
PLACEHOLDER_LEFT = IssueKind("PLACEHOLDER_LEFT", ERROR, "template placeholder syntax or a merge field is still in the text", "replace it with the real value")

TEXT_CHECK_ISSUE_KINDS = (REQUIRED_TEXT_MISSING, FORBIDDEN_TEXT_PRESENT)


def text_presence_issues(visible_text: str, required_text: list[str], forbidden_text: list[str]) -> list[Issue]:
    missing = [REQUIRED_TEXT_MISSING.issue(f"required text is missing: {value}", location=value) for value in required_text if value not in visible_text]
    present = [FORBIDDEN_TEXT_PRESENT.issue(f"forbidden text is present: {value}", location=value) for value in forbidden_text if value in visible_text]
    return missing + present
