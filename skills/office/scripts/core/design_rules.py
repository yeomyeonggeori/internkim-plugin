from __future__ import annotations

import json
import pathlib

from core.office_result import ERROR, WARNING, Issue, IssueKind


DESIGN_RULES_PATH = pathlib.Path(__file__).resolve().parents[2] / "assets" / "design-rules.json"
DESIGN_RULE_DOCUMENT = json.loads(DESIGN_RULES_PATH.read_text(encoding="utf-8"))
DESIGN_RULES = tuple(DESIGN_RULE_DOCUMENT["rules"])
DECK_RULES = tuple(DESIGN_RULE_DOCUMENT["deckRules"])
RULES_BY_CODE = {rule["code"]: rule for rule in DESIGN_RULES + DECK_RULES}


def rule_kind(rule: dict) -> IssueKind:
    return IssueKind(rule["code"], WARNING if rule.get("severity") == WARNING else ERROR, rule["meaning"], rule["suggestion"])


DESIGN_RULE_KINDS = {rule["code"]: rule_kind(rule) for rule in DESIGN_RULES}
DECK_RULE_KINDS = {rule["code"]: rule_kind(rule) for rule in DECK_RULES}
FINDINGS_NAMED_PER_ISSUE = 3


def threshold_of(code: str) -> dict:
    return RULES_BY_CODE[code]["threshold"]


def render_rule_requests() -> list[dict]:
    return [{"code": rule["code"], "measure": rule["measure"], "threshold": rule["threshold"], "supersedes": rule.get("supersedes", [])} for rule in DESIGN_RULES]


def deck_rule_requests() -> dict[str, dict]:
    return {rule["measure"]: rule["threshold"] for rule in DECK_RULES}


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
