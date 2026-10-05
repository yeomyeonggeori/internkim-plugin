from __future__ import annotations

import json
import os
import pathlib
import re

from core.host_contract import HOST_CONTRACT, RUNTIME_CONTEXT_VARIABLE
from core.office_result import ERROR, Issue, IssueKind
from deck.deck_claims import deck_claims
from schemas.known_values import load_runtime_context


UNSUPPORTED_CLAIM = IssueKind("UNSUPPORTED_CLAIM", ERROR, "the draft holds a statement that neither the request, its attachments nor the facts the system knows support", "restate it from the request or its attachments, or drop it and let the slide hold what is given; the deck is checked once more when it is delivered")
REQUEST_FILE = HOST_CONTRACT["draftClaims"]["requestFile"]
REPORTED_FILE = HOST_CONTRACT["draftClaims"]["reportedFile"]
SLIDE_PATH = re.compile(r"slides\[(\d+)\]")


def context_directory() -> pathlib.Path:
    return pathlib.Path(os.environ[RUNTIME_CONTEXT_VARIABLE]).parent


def draft_claim_issues(source_text: str) -> list[Issue]:
    context = load_runtime_context()
    if context is None or not context.judges_draft_claims:
        return []
    claims = deck_claims(source_text)
    (context_directory() / REQUEST_FILE).write_text(json.dumps({"claims": claims}, ensure_ascii=False), encoding="utf-8")
    flagged = [unit for unit in (context.draft_claims or {}).get("unsupported", []) if unit.get("text")]
    refusable = unreported([claim for claim in claims if claim["text"] in {unit["text"] for unit in flagged}])
    remember(refusable)
    return [UNSUPPORTED_CLAIM.issue(f'"{claim["text"]}" is not supported by the request or its attachments', location_of(claim["path"])) for claim in refusable]


def unreported(claims: list[dict]) -> list[dict]:
    reported_path = context_directory() / REPORTED_FILE
    reported = set(json.loads(reported_path.read_text(encoding="utf-8"))) if reported_path.is_file() else set()
    return [claim for claim in claims if claim["text"] not in reported]


def remember(claims: list[dict]) -> None:
    if not claims:
        return
    reported_path = context_directory() / REPORTED_FILE
    reported = set(json.loads(reported_path.read_text(encoding="utf-8"))) if reported_path.is_file() else set()
    reported_path.write_text(json.dumps(sorted(reported | {claim["text"] for claim in claims}), ensure_ascii=False), encoding="utf-8")


def location_of(path: str) -> str | None:
    match = SLIDE_PATH.match(path)
    return f"slide {int(match.group(1)) + 1}" if match else None
