#!/usr/bin/env python3
import json
import pathlib
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: accept_review.py <review-dir>", file=sys.stderr)
        return 2
    review_directory_path = pathlib.Path(sys.argv[1])
    try:
        slide_review = read_json(review_directory_path / "slide-review.json")
        decision = read_optional_json(review_directory_path / "review-decision.json")
        warnings = review_warnings(slide_review, decision)
    except ValueError as error:
        print(f"Review acceptance failed: {error}", file=sys.stderr)
        return 1
    if warnings:
        print("Review acceptance completed with warnings:")
        for warning in warnings:
            print(f"- {warning}")
        return 0
    print("Review acceptance passed.")
    return 0


def read_json(path: pathlib.Path) -> dict:
    if not path.exists():
        raise ValueError(f"{path.name} is required")
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def review_warnings(slide_review: dict, decision: dict) -> list[str]:
    warnings = []
    if not decision:
        warnings.append("review-decision.json is missing; attach the usable deck with the review report notes if the requested file exists")
        return warnings
    inspected_evidence, inspected_evidence_warning = string_set_field(decision, "inspectedEvidence")
    if inspected_evidence_warning:
        warnings.append(inspected_evidence_warning)
    required_evidence = {
        sheet.get("filename")
        for sheet in slide_review.get("contactSheets", [])
        if sheet.get("filename")
    }
    missing_evidence = sorted(required_evidence - inspected_evidence)
    if missing_evidence:
        warnings.append("contact sheets were not inspected: " + ", ".join(missing_evidence))

    deterministic_review_warnings = deterministic_warnings(slide_review)
    accepted_warnings, accepted_warnings_warning = string_set_field(decision, "acceptedWarnings")
    if accepted_warnings_warning:
        warnings.append(accepted_warnings_warning)
    remaining_notes, remaining_notes_warning = list_field(decision, "remainingNotes")
    if remaining_notes_warning:
        warnings.append(remaining_notes_warning)
    issues, issues_warning = list_field(decision, "issues")
    if issues_warning:
        warnings.append(issues_warning)
    if deterministic_review_warnings and not accepted_warnings and not remaining_notes and not issues:
        warnings.append("deterministic warnings were not addressed in acceptedWarnings, remainingNotes, issues, or a rebuilt clean deck")

    if not str(decision.get("summary", "")).strip():
        warnings.append("review decision summary is missing")
    return warnings


def string_set_field(document: dict, field_name: str) -> tuple[set[str], str]:
    value = document.get(field_name, [])
    if value is None:
        return set(), ""
    if isinstance(value, list):
        return {str(item) for item in value if str(item).strip()}, ""
    if isinstance(value, str):
        text = value.strip()
        return ({text} if text else set()), f"{field_name} should be a list; accepted string value as one item"
    return set(), f"{field_name} should be a list; ignored {type(value).__name__} value"


def list_field(document: dict, field_name: str) -> tuple[list, str]:
    value = document.get(field_name, [])
    if value is None:
        return [], ""
    if isinstance(value, list):
        return value, ""
    if isinstance(value, str):
        return [value], f"{field_name} should be a list; accepted string value as one item"
    return [], f"{field_name} should be a list; ignored {type(value).__name__} value"


def deterministic_warnings(slide_review: dict) -> list[str]:
    warnings = []
    for slide in slide_review.get("slides", []):
        for warning in slide.get("warnings", []):
            warnings.append(f"slide {slide.get('index')}: {warning}")
    return warnings


if __name__ == "__main__":
    raise SystemExit(main())
