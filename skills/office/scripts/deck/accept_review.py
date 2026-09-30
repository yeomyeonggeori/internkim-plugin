#!/usr/bin/env python3
from __future__ import annotations

import pathlib

from deck_definitions import (
    CONTACT_SHEETS_NOT_INSPECTED,
    DECISION_FIELD_NOT_LIST,
    DECISION_SUMMARY_MISSING,
    REVIEW_DECISION_MISSING,
    REVIEW_REPORT_MISSING,
    WARNINGS_NOT_ADDRESSED,
)
from office_result import Issue, OfficeArgumentParser, OfficeFailure, Result, read_json_file, run_command


def main() -> Result:
    arguments = parse_arguments()
    review_directory_path = pathlib.Path(arguments.review_directory)
    report_path = review_directory_path / "slide-review.json"
    if not report_path.exists():
        raise OfficeFailure(REVIEW_REPORT_MISSING.issue("slide-review.json is required", str(report_path)))
    slide_review = read_json_file(str(report_path))
    decision = read_optional_json(review_directory_path / "review-decision.json")
    issues = review_issues(slide_review, decision)
    summary = "review acceptance completed with warnings" if issues else "review acceptance passed"
    return Result(summary=summary, output_path=str(review_directory_path), issues=tuple(issues))


def read_optional_json(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    return read_json_file(str(path))


def review_issues(slide_review: dict, decision: dict) -> list[Issue]:
    if not decision:
        return [REVIEW_DECISION_MISSING.issue("review-decision.json is missing; attach the usable deck with the review report notes if the requested file exists")]
    inspected_evidence, issues = string_set_field(decision, "inspectedEvidence")
    required_evidence = {sheet.get("filename") for sheet in slide_review.get("contactSheets", []) if sheet.get("filename")}
    missing_evidence = sorted(required_evidence - inspected_evidence)
    if missing_evidence:
        issues.append(CONTACT_SHEETS_NOT_INSPECTED.issue("contact sheets were not inspected: " + ", ".join(missing_evidence)))
    accepted_warnings, accepted_warnings_issues = string_set_field(decision, "acceptedWarnings")
    remaining_notes, remaining_notes_issues = list_field(decision, "remainingNotes")
    decision_issues, decision_issues_issues = list_field(decision, "issues")
    issues.extend(accepted_warnings_issues + remaining_notes_issues + decision_issues_issues)
    if has_deterministic_warnings(slide_review) and not accepted_warnings and not remaining_notes and not decision_issues:
        issues.append(WARNINGS_NOT_ADDRESSED.issue("deterministic warnings were not addressed in acceptedWarnings, remainingNotes, issues, or a rebuilt clean deck"))
    if not str(decision.get("summary", "")).strip():
        issues.append(DECISION_SUMMARY_MISSING.issue("review decision summary is missing"))
    return issues


def string_set_field(document: dict, field_name: str) -> tuple[set[str], list[Issue]]:
    value = document.get(field_name, [])
    if value is None:
        return set(), []
    if isinstance(value, list):
        return {str(item) for item in value if str(item).strip()}, []
    if isinstance(value, str):
        text = value.strip()
        return ({text} if text else set()), [not_a_list(field_name, "accepted string value as one item")]
    return set(), [not_a_list(field_name, f"ignored {type(value).__name__} value")]


def list_field(document: dict, field_name: str) -> tuple[list, list[Issue]]:
    value = document.get(field_name, [])
    if value is None:
        return [], []
    if isinstance(value, list):
        return value, []
    if isinstance(value, str):
        return [value], [not_a_list(field_name, "accepted string value as one item")]
    return [], [not_a_list(field_name, f"ignored {type(value).__name__} value")]


def not_a_list(field_name: str, consequence: str) -> Issue:
    return DECISION_FIELD_NOT_LIST.issue(f"{field_name} should be a list; {consequence}", field_name)


def has_deterministic_warnings(slide_review: dict) -> bool:
    return any(slide.get("warnings") for slide in slide_review.get("slides", []))


def parse_arguments():
    parser = OfficeArgumentParser(description="Check review-decision.json against the deck review evidence.")
    parser.add_argument("review_directory", help="the build/review directory")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
