from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import pathlib

from deck.deck_definitions import (
    CHART_UNDERFILLED,
    DRAWING_DISTORTED,
    EMPTY_REGION,
    GRID_MISALIGNED,
    IMAGE_DISTORTED,
    OFF_PALETTE_COLOR,
    SLIDE_BLANK,
    TEXT_COVERED,
    TEXT_LOW_CONTRAST,
    TINY_TEXT,
    TITLE_TOO_LONG,
    VERTICAL_DEAD_ZONE,
)
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
        TITLE_TOO_LONG.kind,
        IMAGE_DISTORTED.kind,
        DRAWING_DISTORTED.kind,
        CHART_UNDERFILLED.kind,
        SLIDE_BLANK.kind,
        VERTICAL_DEAD_ZONE.kind,
        EMPTY_REGION.kind,
        TINY_TEXT.kind,
        TEXT_LOW_CONTRAST.kind,
        GRID_MISALIGNED.kind,
        CHART_POINT_OUTSIDE_AXIS.kind,
        CHART_ZERO_MISALIGNED.kind,
        REQUIRED_TEXT_MISSING,
        OFF_PALETTE_COLOR,
        *DESIGN_RULE_KINDS.values(),
    )
)


@dataclass(frozen=True)
class Acceptance:
    acceptable: bool
    defects: tuple[Issue, ...]
    fix_round: int
    deliverable: str

    @property
    def verdict(self) -> str:
        if self.acceptable:
            return f"ACCEPTABLE: deliver {self.deliverable}; the other issues are advice, so do not redesign clean slides"
        listed = "; ".join(f"{issue.kind.code} on {issue.location}" for issue in self.defects)
        if self.fix_round >= FIX_ROUNDS_ALLOWED:
            return f"STOP FIXING: {FIX_ROUNDS_ALLOWED} fix rounds are used; deliver {self.deliverable} and name what remains: {listed}"
        return f"FIX ROUND {self.fix_round + 1} OF {FIX_ROUNDS_ALLOWED}: fix only these defects in slides.html, then build again: {listed}"

    def to_json(self) -> dict:
        return {
            "acceptable": self.acceptable,
            "verdict": self.verdict,
            "defects": [{"code": issue.kind.code, "location": issue.location} for issue in self.defects],
            "fixRound": self.fix_round,
            "fixRoundsAllowed": FIX_ROUNDS_ALLOWED,
            "deliverable": self.deliverable,
        }


def judge_build(build_path: pathlib.Path, source_text: str, issues: list[Issue], deliverable: str) -> Acceptance:
    defects = tuple(issue for issue in issues if issue.kind.code in OBJECTIVE_DEFECT_CODES)
    acceptable = not defects
    fix_round = record_build(build_path / HISTORY_FILE_NAME, source_digest(source_text), acceptable)
    return Acceptance(acceptable, defects, fix_round, deliverable)


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
