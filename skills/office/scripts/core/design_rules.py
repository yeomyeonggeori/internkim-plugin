from __future__ import annotations

import json
import pathlib

from core.office_result import ERROR, WARNING, Issue, IssueKind


DESIGN_RULES_PATH = pathlib.Path(__file__).resolve().parents[2] / "assets" / "design-rules.json"
DESIGN_RULES = tuple(json.loads(DESIGN_RULES_PATH.read_text(encoding="utf-8"))["rules"])
RULES_BY_CODE = {rule["code"]: rule for rule in DESIGN_RULES}
DESIGN_RULE_KINDS = {rule["code"]: IssueKind(rule["code"], WARNING if rule.get("severity") == WARNING else ERROR, rule["meaning"], rule["suggestion"]) for rule in DESIGN_RULES}
FINDINGS_NAMED_PER_ISSUE = 3


def threshold_of(code: str) -> dict:
    return RULES_BY_CODE[code]["threshold"]


def render_rule_requests() -> list[dict]:
    return [{"code": rule["code"], "measure": rule["measure"], "threshold": rule["threshold"]} for rule in DESIGN_RULES]


def render_rule_issues(findings: list[dict], location: str) -> list[Issue]:
    issues = []
    for code, kind in DESIGN_RULE_KINDS.items():
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
