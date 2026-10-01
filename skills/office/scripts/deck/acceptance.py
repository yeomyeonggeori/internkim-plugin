from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import pathlib

from deck_definitions import (
    CONTENT_OVERFLOW,
    IMAGE_DISTORTED,
    MISSING_REQUIRED_TEXT,
    OFF_PALETTE_COLOR,
    OUT_OF_FRAME,
    SLIDE_BLANK,
    TEXT_OVERLAP,
    TINY_TEXT,
)
from office_result import Issue
from text_checks import REQUIRED_TEXT_MISSING


FIX_ROUNDS_ALLOWED = 2
HISTORY_FILE_NAME = "build-history.json"
OBJECTIVE_DEFECT_CODES = frozenset(
    kind.code
    for kind in (
        CONTENT_OVERFLOW.kind,
        OUT_OF_FRAME.kind,
        TEXT_OVERLAP.kind,
        IMAGE_DISTORTED.kind,
        SLIDE_BLANK.kind,
        TINY_TEXT.kind,
        MISSING_REQUIRED_TEXT.kind,
        REQUIRED_TEXT_MISSING,
        OFF_PALETTE_COLOR,
    )
)


@dataclass(frozen=True)
class Acceptance:
    acceptable: bool
    defects: tuple[Issue, ...]
    fix_round: int
    deliverable: str
    measured: bool

    @property
    def verdict(self) -> str:
        if not self.measured:
            return f"NOT MEASURED: no browser rendered the deck, so there is no PDF and no layout check; deliver {self.deliverable} and say so"
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


def judge_build(build_path: pathlib.Path, source_text: str, issues: list[Issue], deliverable: str, measured: bool) -> Acceptance:
    defects = tuple(issue for issue in issues if issue.kind.code in OBJECTIVE_DEFECT_CODES)
    fix_round = record_source_version(build_path / HISTORY_FILE_NAME, source_digest(source_text))
    return Acceptance(measured and not defects, defects, fix_round, deliverable, measured)


def source_digest(source_text: str) -> str:
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def record_source_version(history_path: pathlib.Path, digest: str) -> int:
    versions = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    if digest not in versions:
        versions.append(digest)
        history_path.write_text(json.dumps(versions, indent=2) + "\n", encoding="utf-8")
    return versions.index(digest)
