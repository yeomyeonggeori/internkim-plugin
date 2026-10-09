from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys

from core.source_snapshot import SOURCE_SUFFIX, read_source
from delivery.claim_kinds import BLANK, REWRITE, AttachmentText, Claim, Sources, Verdict, judge
from delivery.claim_rewrites import Outcome, recompute, treat
from delivery.deck_refusal import is_deck, may_refuse, remember_refusal
from delivery.file_text import OFFICE_ENTRY, REMAKE_VARIABLE, blank_in_place, text_claims
from host import script_host
from host.task_context import TaskContext
from schemas.known_values import COMPANY_INFO_TOOL, COMPANY_PROFILE_FILE, DEFAULT_PROFILE_LANGUAGE, company_profile, company_profiles


SUPPORTED = "supported"
BLANKED = "blanked"
REWRITTEN = "rewritten"
REFUSED = "refused"
UNREAD_SOURCES = "not_enforced_unread_attachment"
JUDGE_FAILED = "judge_failed"
REMAKE_FAILED = "remake_failed"
NO_REMAKE_COMMAND = "no_remake_command"
NOT_EDITABLE = "not_editable"
RECORD_ANSWER_LIMIT = 4000
COMPANY_FILE_FIELDS = ("logoImage", "sealImage", "logoPath", "stampPath", "updatedAt", "language")

MAXIMUM_WITHDRAWAL_PASSES = 2
REMAKE_TIMEOUT_SECONDS = 180


@dataclass
class ClaimCheck:
    file: str
    asked: int = 0
    flagged: list = field(default_factory=list)
    hollow: list = field(default_factory=list)
    blanked: list = field(default_factory=list)
    outcome: str = ""
    detail: str = ""
    cost: float = 0.0
    calls: int = 0

    def to_json(self) -> dict:
        document = {"file": self.file, "asked": self.asked, "outcome": self.outcome, "calls": self.calls, "costUSD": round(self.cost, 6)}
        optional = {"flagged": [verdict.to_json() for verdict in self.flagged], "hollow": [verdict.to_json() for verdict in self.hollow], "blanked": self.blanked, "detail": self.detail}
        return document | {name: value for name, value in optional.items() if value}

    def add_cost(self, cost: float, calls: int) -> None:
        self.cost += cost
        self.calls += calls


def is_remake() -> bool:
    return os.environ.get(REMAKE_VARIABLE) == "1"


def snapshot_claims(snapshot: dict) -> list[Claim]:
    return [Claim.from_json(claim) for claim in snapshot.get("claims") or () if isinstance(claim, dict)]


def check_file(context: TaskContext, file_path: Path, claims: list[Claim]) -> ClaimCheck:
    check = ClaimCheck(file=file_path.name)
    snapshot = read_source(file_path)
    sources, is_every_source_read = claim_sources(context, snapshot)
    try:
        judgment = judge(sources, claims_marked_free(claims))
    except (script_host.HostFailure, script_host.HostUnavailable) as failure:
        check.outcome, check.detail = JUDGE_FAILED, str(failure)
        return check
    judgment = recomputed(check, sources, judgment)
    check.asked = judgment.asked()
    check.add_cost(judgment.cost, judgment.calls)
    check.hollow = judgment.treated(REWRITE)
    treated = treated_claims(check, sources, judgment)
    check.flagged = list(treated.blank)
    act_on_flagged(check, file_path, snapshot, treated, is_every_source_read)
    judge_what_the_blanks_left(check, file_path, sources, treated.blank + treated.removed)
    return check


def recomputed(check: ClaimCheck, sources: Sources, judgment):
    try:
        return recompute(sources, judgment)
    except script_host.HostUnavailable:
        return judgment
    except script_host.HostFailure as failure:
        check.detail = f"recompute_failed: {failure}"
        return judgment


def treated_claims(check: ClaimCheck, sources: Sources, judgment) -> Outcome:
    try:
        treated = treat(sources, judgment)
    except script_host.HostUnavailable:
        return Outcome(blank=judgment.treated(BLANK))
    except script_host.HostFailure as failure:
        check.detail = check.detail or f"rewrite_failed: {failure}"
        return Outcome(blank=judgment.treated(BLANK))
    check.add_cost(treated.cost, treated.calls)
    return treated


def act_on_flagged(check: ClaimCheck, file_path: Path, snapshot: dict, treated: Outcome, is_every_source_read: bool) -> None:
    if treated.changes_nothing():
        check.outcome = SUPPORTED
        return
    if not is_every_source_read:
        check.outcome = UNREAD_SOURCES
        return
    if treated.blank and is_deck(snapshot) and may_refuse(file_path, snapshot):
        remember_refusal(file_path, snapshot)
        check.outcome = REFUSED
        return
    paths = [verdict.claim.path for verdict in treated.blank + treated.removed]
    words = remake_words(snapshot, file_path, paths, treated.replaced)
    if words is None:
        check.outcome = NO_REMAKE_COMMAND
        return
    failure = run_remake(words)
    if failure:
        check.outcome, check.detail = REMAKE_FAILED, failure
        return
    check.outcome = BLANKED if paths else REWRITTEN
    check.blanked = [verdict.place for verdict in treated.blank]


def judge_what_the_blanks_left(check: ClaimCheck, file_path: Path, sources: Sources, newly_removed: list[Verdict]) -> None:
    removed = [verdict.claim for verdict in newly_removed]
    for _ in range(MAXIMUM_WITHDRAWAL_PASSES):
        if check.outcome != BLANKED or not newly_removed:
            return
        snapshot = read_source(file_path)
        neighbors = claims_marked_free(claims_sharing_a_parent(newly_removed, removed, snapshot_claims(snapshot)))
        if not neighbors:
            return
        try:
            judgment = judge(sources.with_removed(removed), neighbors)
        except (script_host.HostFailure, script_host.HostUnavailable) as failure:
            check.detail = f"the statements left beside the blanks were not re-judged: {failure}"
            return
        check.asked += judgment.asked()
        check.add_cost(judgment.cost, judgment.calls)
        newly_removed = judgment.treated(BLANK)
        if not newly_removed:
            return
        words = remake_words(snapshot, file_path, [verdict.claim.path for verdict in newly_removed], [])
        failure = "the file's snapshot names no command that remakes it" if words is None else run_remake(words)
        if failure:
            check.detail = f"the statements left beside the blanks could not be blanked: {failure}"
            return
        removed += [verdict.claim for verdict in newly_removed]
        check.flagged += newly_removed
        check.blanked += [verdict.place for verdict in newly_removed]


def claims_sharing_a_parent(newly_removed: list[Verdict], removed: list[Claim], remaining: list[Claim]) -> list[Claim]:
    parents = {parent_path(verdict.claim.path) for verdict in newly_removed}
    removed_keys = {(claim.path, claim.at, claim.text) for claim in removed}
    return [claim for claim in remaining if parent_path(claim.path) in parents and (claim.path, claim.at, claim.text) not in removed_keys]


def parent_path(path: str) -> str:
    without_piece = path.split("#", 1)[0]
    if "[" in without_piece:
        without_piece = without_piece[:without_piece.rindex("[")]
    return without_piece[:without_piece.rindex(".")] if "." in without_piece else ""


def claims_marked_free(claims: list[Claim]) -> list[Claim]:
    return [Claim(path=claim.path, text=claim.text, at=claim.at, is_free=is_sentence_path(claim.path)) for claim in claims]


def is_sentence_path(path: str) -> bool:
    _, separator, sentence = path.partition("#")
    return bool(separator) and sentence.isascii() and sentence.isdigit()


def claim_sources(context: TaskContext, snapshot: dict) -> tuple[Sources, bool]:
    facts = {"today": context.today.isoformat() if context.today else "", "requester": {"name": context.requester_name, "email": context.requester_email}}
    company = company_facts(context)
    if company:
        facts["company"] = company
    if snapshot.get("known"):
        facts["known"] = snapshot["known"]
    answered = [{"tool": record.tool, "result": bounded_result(record.result)} for record in context.records if record.result is not None]
    if answered:
        facts["recordAnswers"] = answered
    current = [attachment for attachment in context.attachments if attachment.is_current]
    attachments = tuple(AttachmentText(name=attachment.name, text=attachment.text) for attachment in current if attachment.text.strip())
    return Sources(request=context.request, attachments=attachments, runtime_facts=facts), len(attachments) == len(current)


def company_facts(context: TaskContext) -> dict:
    paths = company_profile_paths(context) or company_profile_paths_read_now()
    profiles = {language: stated_values(company_profile(path)) for language, path in paths.items()}
    return {language: profile for language, profile in profiles.items() if profile}


def company_profile_paths(context: TaskContext) -> dict:
    return {language: path for language, path in company_profiles(context).items() if path}


def company_profile_paths_read_now() -> dict:
    try:
        answer = script_host.call_tool(COMPANY_INFO_TOOL, {})
    except (script_host.HostFailure, script_host.HostUnavailable):
        return {}
    files = answer.get("files") if isinstance(answer, dict) else None
    paths = [str(file.get("path")) for file in files or () if isinstance(file, dict) and Path(str(file.get("path") or "")).name == COMPANY_PROFILE_FILE]
    return {DEFAULT_PROFILE_LANGUAGE: paths[0]} if paths else {}


def stated_values(profile: dict) -> dict:
    return {name: value.strip() for name, value in profile.items() if isinstance(value, str) and value.strip() and name not in COMPANY_FILE_FIELDS}


def bounded_result(result: object) -> object:
    encoded = json.dumps(result, ensure_ascii=False)
    return result if len(encoded) <= RECORD_ANSWER_LIMIT else encoded[:RECORD_ANSWER_LIMIT]


def check_text(context: TaskContext, file_path: Path, snapshot: dict) -> ClaimCheck:
    check = ClaimCheck(file=file_path.name, outcome=SUPPORTED)
    claims = text_claims(file_path)
    if not claims:
        return check
    sources, is_every_source_read = claim_sources(context, {})
    try:
        judgment = judge(sources, claims_marked_free(claims))
    except (script_host.HostFailure, script_host.HostUnavailable) as failure:
        check.outcome, check.detail = JUDGE_FAILED, str(failure)
        return check
    judgment = recomputed(check, sources, judgment)
    check.asked = judgment.asked()
    check.add_cost(judgment.cost, judgment.calls)
    check.flagged = judgment.treated(BLANK)
    if not check.flagged:
        return check
    if not is_every_source_read:
        check.outcome = UNREAD_SOURCES
    elif is_deck(snapshot) and may_refuse(file_path, snapshot):
        remember_refusal(file_path, snapshot)
        check.outcome = REFUSED
    elif blank_in_place(file_path, [verdict.claim for verdict in check.flagged]):
        check.outcome, check.blanked = BLANKED, [verdict.place for verdict in check.flagged]
    else:
        check.outcome = NOT_EDITABLE
    return check


def remake_words(snapshot: dict, file_path: Path, paths: list[str], replacements: list[Claim]) -> list[str] | None:
    source = str(file_path) + SOURCE_SUFFIX
    if snapshot.get("schema"):
        words = ["merge", str(snapshot["schema"]), source, str(file_path)]
    elif snapshot.get("declaration"):
        words = ["create", str(file_path), source]
    elif snapshot.get("deck"):
        words = ["create", str(file_path), str(snapshot["deck"])]
    else:
        return None
    for path in paths:
        words += ["--blank", path]
    for replacement in replacements:
        words += ["--replace", f"{replacement.path}={replacement.text}"]
    return words


def run_remake(words: list[str], directory: Path | None = None) -> str:
    environment = {**os.environ, REMAKE_VARIABLE: "1"}
    try:
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *words], capture_output=True, text=True, env=environment, timeout=REMAKE_TIMEOUT_SECONDS, cwd=directory)
    except subprocess.TimeoutExpired:
        return f"the remake took longer than {REMAKE_TIMEOUT_SECONDS} seconds"
    if completed.returncode == 0:
        return ""
    return remake_failure(completed)


def remake_failure(completed: subprocess.CompletedProcess) -> str:
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return (completed.stderr or completed.stdout or "the office command failed").strip()
    issues = result.get("issues") or []
    return "; ".join(str(issue.get("message")) for issue in issues if issue.get("severity") == "error") or str(result.get("summary") or "the office command failed")
