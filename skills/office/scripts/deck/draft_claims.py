from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re

from core.host_contract import HOST_CONTRACT, RUNTIME_CONTEXT_VARIABLE
from core.office_result import ERROR, Issue, IssueKind
from deck.deck_claims import DECK_TITLE_PATH, deck_claims
from deck.outline import Outline
from schemas.known_values import load_runtime_context


UNSUPPORTED_CLAIM = IssueKind("UNSUPPORTED_CLAIM", ERROR, "the draft holds a statement that neither the request, its attachments nor the facts the system knows support", "restate it from the request or its attachments, or drop it, in the place the message names; the deck is checked once more when it is delivered")
REQUEST_FILE = HOST_CONTRACT["draftClaims"]["requestFile"]
REPORTED_FILE = HOST_CONTRACT["draftClaims"]["reportedFile"]
SLIDE_PATH = re.compile(r"slides\[(\d+)\]")
OUTLINE_PAGE_PATH = re.compile(r"outline\.pages\[(\d+)\]")


def context_directory() -> pathlib.Path:
    return pathlib.Path(os.environ[RUNTIME_CONTEXT_VARIABLE]).parent


def outline_claims(outline: Outline) -> list[dict]:
    claims = [{"path": "outline.core_hook", "at": "outline core hook", "text": outline.core_hook}] if outline.core_hook else []
    for index, page in enumerate(outline.pages):
        claims.append({"path": f"outline.pages[{index}].title", "at": f"outline page {index + 1} title", "text": page.title})
        claims += [{"path": f"outline.pages[{index}].brief[{line}]", "at": f"outline page {index + 1} brief", "text": text} for line, text in enumerate(page.brief)]
        claims += [{"path": f"outline.pages[{index}].figures[{number}]", "at": f"outline page {index + 1} figure", "text": figure.shown()} for number, figure in enumerate(page.figures)]
    return [claim for claim in claims if claim["text"]]


def draft_claims(outline: Outline, assembled_pages: str) -> list[dict]:
    return outline_claims(outline) + [claim for claim in deck_claims(assembled_pages) if claim["path"] != DECK_TITLE_PATH]


def request_content(claims: list[dict]) -> bytes:
    return json.dumps({"claims": claims}, ensure_ascii=False).encode("utf-8")


def draft_claim_issues(claims: list[dict]) -> tuple[list[Issue], bool]:
    context = load_runtime_context()
    if context is None or not context.judges_draft_claims:
        return [], True
    content = request_content(claims)
    (context_directory() / REQUEST_FILE).write_bytes(content)
    verdict = context.draft_claims or {}
    flagged = {unit["text"] for unit in verdict.get("unsupported", []) if unit.get("text")}
    refusable = unreported([claim for claim in claims if claim["text"] in flagged])
    remember(refusable)
    issues = [UNSUPPORTED_CLAIM.issue(f'"{claim["text"]}" is not supported by the request or its attachments', location_of(claim["path"])) for claim in refusable]
    return issues, verdict.get("digest") == hashlib.sha256(content).hexdigest()


def reported_texts() -> set[str]:
    reported_path = context_directory() / REPORTED_FILE
    return set(json.loads(reported_path.read_text(encoding="utf-8"))) if reported_path.is_file() else set()


def unreported(claims: list[dict]) -> list[dict]:
    reported = reported_texts()
    return [claim for claim in claims if claim["text"] not in reported]


def remember(claims: list[dict]) -> None:
    if claims:
        (context_directory() / REPORTED_FILE).write_text(json.dumps(sorted(reported_texts() | {claim["text"] for claim in claims}), ensure_ascii=False), encoding="utf-8")


def location_of(path: str) -> str | None:
    outline = OUTLINE_PAGE_PATH.match(path)
    if outline:
        return f"outline page {int(outline.group(1)) + 1}"
    if path.startswith("outline."):
        return "outline"
    slide = SLIDE_PATH.match(path)
    return f"page {int(slide.group(1)) + 1}" if slide else None
