from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import time

from core.office_result import Result
from core.source_snapshot import DELIVERABLE_EXTENSIONS, read_source
from delivery.claim_check import ClaimCheck, check_file, is_remake, snapshot_claims
from delivery.claim_kinds import Claim
from delivery.delivered_metadata import write_metadata
from host import script_host
from host.task_context import TaskContext, load_task_context


CHECKED_VERBS = ("merge", "create")
DESCRIBED_VERBS = (*CHECKED_VERBS, "apply")
REVIEW_BUDGET_SECONDS = 75


def finished(result: Result) -> Result:
    file_path = finishable_path(result)
    context = load_task_context() if file_path else None
    if file_path is None or context is None:
        return result
    checks, review = finish_file(context, file_path) if command_verb() in CHECKED_VERBS else ([], None)
    snapshot = read_source(file_path)
    write_metadata(file_path, snapshot, checks, review.leftovers if review else [])
    return with_finishing(result, snapshot, checks, review)


def command_verb() -> str:
    return os.environ.get("OFFICE_COMMAND", "").removeprefix("office ").strip()


def finishable_path(result: Result) -> Path | None:
    if result.status == "error" or is_remake() or command_verb() not in DESCRIBED_VERBS or not result.output_path:
        return None
    file_path = Path(result.output_path).expanduser()
    if file_path.suffix.lower() not in DELIVERABLE_EXTENSIONS or not read_source(file_path):
        return None
    return file_path


def finish_file(context: TaskContext, file_path: Path):
    if not script_host.is_present():
        return [], None
    deadline = time.monotonic() + REVIEW_BUDGET_SECONDS
    checks = []
    claims = snapshot_claims(read_source(file_path))
    if claims:
        checks.append(check_file(context, file_path, claims))
    review = None
    before = read_source(file_path)
    if before.get("visualReview"):
        from delivery.visual_review import review_deck

        review = review_deck(file_path, before, deadline)
        checks += rechecked_claims(context, file_path, before, review)
    return checks, review


def rechecked_claims(context: TaskContext, file_path: Path, before: dict, review) -> list[ClaimCheck]:
    if not review.text_changed:
        return []
    changed = new_or_changed_claims(snapshot_claims(before), snapshot_claims(read_source(file_path)))
    return [check_file(context, file_path, changed)] if changed else []


def new_or_changed_claims(before: list[Claim], after: list[Claim]) -> list[Claim]:
    known = {(claim.path, claim.text) for claim in before}
    return [claim for claim in after if (claim.path, claim.text) not in known]


def with_finishing(result: Result, snapshot: dict, checks: list[ClaimCheck], review) -> Result:
    details = dict(result.details or {})
    if checks:
        details["claimCheck"] = [check.to_json() for check in checks]
    if review is not None:
        details["visualReview"] = review.to_json()
    if "blanks" in snapshot:
        details["blanks"] = snapshot["blanks"]
    return replace(result, summary=result.summary + finishing_summary(checks), details=details)


def finishing_summary(checks: list[ClaimCheck]) -> str:
    blanked = [place for check in checks for place in check.blanked]
    if not blanked:
        return ""
    return f" The claim check left {len(blanked)} values the sources do not support blank: {', '.join(blanked)}."
