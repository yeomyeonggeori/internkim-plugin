from __future__ import annotations

import hashlib
import json
import re

from core.office_result import ERROR, Issue, IssueKind
from deck.deck_claims import DECK_TITLE_PATH, deck_claims
from deck.deck_decisions import read_state, write_state
from deck.outline import Outline
from delivery.claim_check import claim_sources, is_remake
from delivery.claim_kinds import BLANK, Claim, judge
from host import script_host
from host.task_context import load_task_context


UNSUPPORTED_CLAIM = IssueKind("UNSUPPORTED_CLAIM", ERROR, "the draft holds a statement that neither the request, its attachments nor the facts the system knows support", "restate it from the request or its attachments, or drop it, in the place the message names; the deck is checked once more when it is delivered")
JUDGED_FILE = "draft-claims.json"
REPORTED_FILE = "draft-claims-reported.json"
SLIDE_PATH = re.compile(r"slides\[(\d+)\]")
OUTLINE_PAGE_PATH = re.compile(r"outline\.pages\[(\d+)\]")


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


def draft_claim_issues(claims: list[dict], may_ask: bool = True) -> list[Issue]:
    if not script_host.is_present() or load_task_context() is None or is_remake():
        return []
    units = unsupported_units(claims) if may_ask else last_unsupported_units()
    flagged = {unit["text"] for unit in units if unit.get("text")}
    refusable = unreported([claim for claim in claims if claim["text"] in flagged])
    remember(refusable)
    return [UNSUPPORTED_CLAIM.issue(f'"{claim["text"]}" is not supported by the request or its attachments', location_of(claim["path"])) for claim in refusable]


def unsupported_units(claims: list[dict]) -> list[dict]:
    digest = hashlib.sha256(request_content(claims)).hexdigest()
    judged = read_state(JUDGED_FILE)
    if isinstance(judged, dict) and judged.get("digest") == digest:
        return judged.get("unsupported") or []
    unsupported = judged_unsupported(claims)
    write_state(JUDGED_FILE, {"digest": digest, "unsupported": unsupported})
    return unsupported


def last_unsupported_units() -> list[dict]:
    judged = read_state(JUDGED_FILE)
    return (judged.get("unsupported") or []) if isinstance(judged, dict) else []


def judged_unsupported(claims: list[dict]) -> list[dict]:
    sources, is_every_source_read = claim_sources(load_task_context(), {})
    if not claims or not is_every_source_read:
        return []
    try:
        judgment = judge(sources, [Claim.from_json(claim) for claim in claims])
    except (script_host.HostFailure, script_host.HostUnavailable):
        return []
    return [verdict.claim.to_json() for verdict in judgment.treated(BLANK)]


def reported_texts() -> set[str]:
    reported = read_state(REPORTED_FILE)
    return set(reported.get("texts") or []) if isinstance(reported, dict) else set()


def unreported(claims: list[dict]) -> list[dict]:
    reported = reported_texts()
    return [claim for claim in claims if claim["text"] not in reported]


def remember(claims: list[dict]) -> None:
    if claims:
        write_state(REPORTED_FILE, {"texts": sorted(reported_texts() | {claim["text"] for claim in claims})})


def location_of(path: str) -> str | None:
    outline = OUTLINE_PAGE_PATH.match(path)
    if outline:
        return f"outline page {int(outline.group(1)) + 1}"
    if path.startswith("outline."):
        return "outline"
    slide = SLIDE_PATH.match(path)
    return f"page {int(slide.group(1)) + 1}" if slide else None
