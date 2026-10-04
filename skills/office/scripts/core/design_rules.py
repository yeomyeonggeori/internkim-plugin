from __future__ import annotations

import json
import pathlib

from core.office_result import ERROR, Issue, IssueKind


DESIGN_RULES_PATH = pathlib.Path(__file__).resolve().parents[2] / "assets" / "design-rules.json"
DESIGN_RULES = tuple(json.loads(DESIGN_RULES_PATH.read_text(encoding="utf-8"))["rules"])
RULES_BY_CODE = {rule["code"]: rule for rule in DESIGN_RULES}
DESIGN_RULE_KINDS = {rule["code"]: IssueKind(rule["code"], ERROR, rule["meaning"], rule["suggestion"]) for rule in DESIGN_RULES}
TOKEN_STAGE = "tokens"
RENDER_STAGE = "render"
FINDINGS_NAMED_PER_ISSUE = 3


def threshold_of(code: str) -> dict:
    return RULES_BY_CODE[code]["threshold"]


def rules_for(stage: str) -> tuple[dict, ...]:
    return tuple(rule for rule in DESIGN_RULES if stage in rule["stages"])


def render_rule_requests() -> list[dict]:
    return [
        {"code": rule["code"], "measure": rule["measure"], "threshold": rule["threshold"]}
        for rule in rules_for(RENDER_STAGE)
    ]


def render_rule_issues(findings: list[dict], location: str) -> list[Issue]:
    issues = []
    for code, kind in DESIGN_RULE_KINDS.items():
        if RULES_BY_CODE[code].get("deck"):
            continue
        found = [finding for finding in findings if finding["code"] == code]
        if found:
            issues.append(kind.issue(f"{kind.meaning}: {named_findings(found)}", location))
    return issues


def named_findings(found: list[dict]) -> str:
    named = "; ".join(named_finding(finding) for finding in found[:FINDINGS_NAMED_PER_ISSUE])
    remainder = len(found) - FINDINGS_NAMED_PER_ISSUE
    return named + (f"; and {remainder} more" if remainder > 0 else "")


def named_finding(finding: dict) -> str:
    text = f' "{finding["text"]}"' if finding.get("text") else ""
    return f"{finding['selector']}{text}, {finding['detail']}"


def deck_rule_issues(slides_findings: list[list[dict]]) -> list[Issue]:
    issues = []
    for rule in (rule for rule in DESIGN_RULES if rule.get("deck")):
        signatures = [next((finding["detail"] for finding in findings if finding["code"] == rule["code"]), "") for findings in slides_findings]
        for start, length in runs_of_one_signature(signatures):
            if length > rule["threshold"]["maximumRun"]:
                last = start + length
                issues.append(DESIGN_RULE_KINDS[rule["code"]].issue(f"{rule['meaning']}: slides {start + 1} to {last} share a {signatures[start]} card arrangement", f"slide {start + 3}"))
    return issues


def runs_of_one_signature(signatures: list[str]) -> list[tuple[int, int]]:
    runs, start = [], 0
    for index in range(1, len(signatures) + 1):
        if index == len(signatures) or signatures[index] != signatures[start] or not signatures[start]:
            if signatures[start]:
                runs.append((start, index - start))
            start = index
    return runs
