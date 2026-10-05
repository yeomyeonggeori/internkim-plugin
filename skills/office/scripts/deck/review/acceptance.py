from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import pathlib

from deck.deck_definitions import DRAWING_DISTORTED, IMAGE_DISTORTED, SLIDE_BLANK, TEXT_COVERED, TEXT_LOW_CONTRAST
from core.design_rules import DESIGN_RULE_KINDS
from core.office_result import Issue
from core.text_checks import REQUIRED_TEXT_MISSING
from powerpoint.definitions import CHART_POINT_OUTSIDE_AXIS, CHART_ZERO_MISALIGNED


FIX_ROUNDS_ALLOWED = 2
HISTORY_FILE_NAME = "build-history.json"
OBJECTIVE_DEFECT_CODES = frozenset(
    kind.code
    for kind in (
        TEXT_COVERED.kind,
        IMAGE_DISTORTED.kind,
        DRAWING_DISTORTED.kind,
        SLIDE_BLANK.kind,
        TEXT_LOW_CONTRAST.kind,
        CHART_POINT_OUTSIDE_AXIS.kind,
        CHART_ZERO_MISALIGNED.kind,
        REQUIRED_TEXT_MISSING,
        *DESIGN_RULE_KINDS.values(),
    )
)

WORDS_THE_HOST_CANNOT_REPAIR = frozenset({REQUIRED_TEXT_MISSING.code})


@dataclass(frozen=True)
class Acceptance:
    acceptable: bool
    defects: tuple[Issue, ...]
    fix_round: int
    deliverable: str
    repaired_by_host: bool = False

    @property
    def verdict(self) -> str:
        if self.acceptable and self.repaired_by_host:
            return f"ACCEPTABLE: deliver {self.deliverable}; the host reviews every render and repairs the slides it flags, so do not redesign slides"
        if self.acceptable:
            return f"ACCEPTABLE: deliver {self.deliverable}; the other issues are advice, so do not redesign clean slides"
        listed = "; ".join(f"{issue.kind.code} on {issue.location}" for issue in self.defects)
        if self.fix_round >= FIX_ROUNDS_ALLOWED:
            return f"STOP FIXING: {FIX_ROUNDS_ALLOWED} fix rounds are used; deliver {self.deliverable} and name what remains: {listed}"
        return f"FIX ROUND {self.fix_round + 1} OF {FIX_ROUNDS_ALLOWED}: fix only these defects in their page files, keeping the copy, facts, palette and composition, then build again: {listed}"

    def to_json(self) -> dict:
        return {
            "acceptable": self.acceptable,
            "verdict": self.verdict,
            "defects": [{"code": issue.kind.code, "location": issue.location} for issue in self.defects],
            "fixRound": self.fix_round,
            "fixRoundsAllowed": FIX_ROUNDS_ALLOWED,
            "deliverable": self.deliverable,
        }


def judge_build(build_path: pathlib.Path, source_text: str, issues: list[Issue], deliverable: str, repaired_by_host: bool = False) -> Acceptance:
    owned_codes = OBJECTIVE_DEFECT_CODES & WORDS_THE_HOST_CANNOT_REPAIR if repaired_by_host else OBJECTIVE_DEFECT_CODES
    defects = tuple(issue for issue in issues if issue.kind.code in owned_codes)
    acceptable = not defects
    fix_round = record_build(build_path / HISTORY_FILE_NAME, source_digest(source_text), acceptable)
    return Acceptance(acceptable, defects, fix_round, deliverable, repaired_by_host)


def source_digest(source_text: str) -> str:
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def read_history(history_path: pathlib.Path) -> list[dict]:
    if not history_path.exists():
        return []
    entries = json.loads(history_path.read_text(encoding="utf-8"))
    return [entry for entry in entries if isinstance(entry, dict)]


def next_fix_round(previous: dict | None) -> int:
    if previous is None or previous["acceptable"] or previous["fixRound"] >= FIX_ROUNDS_ALLOWED:
        return 0
    return previous["fixRound"] + 1


def record_build(history_path: pathlib.Path, digest: str, acceptable: bool) -> int:
    entries = read_history(history_path)
    position = next((index for index, entry in enumerate(entries) if entry["digest"] == digest), len(entries))
    previous = entries[position - 1] if position > 0 else None
    fix_round = next_fix_round(previous)
    entry = {"digest": digest, "acceptable": acceptable, "fixRound": fix_round}
    entries = entries[:position] + [entry] + entries[position + 1:]
    history_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return fix_round
