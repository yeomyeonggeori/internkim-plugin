from __future__ import annotations

import hashlib
import json
from pathlib import Path

from deck.deck_decisions import read_state, write_state


REFUSALS_FILE = "deck-claim-refusals.json"


def is_deck(snapshot: dict) -> bool:
    return bool(snapshot.get("deck"))


def build_digest(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot.get("claims") or [], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def may_refuse(file_path: Path, snapshot: dict) -> bool:
    refusals = read_state(REFUSALS_FILE) or {}
    refused = refusals.get(str(snapshot["deck"]))
    if not isinstance(refused, dict):
        return True
    return refused.get("build") == build_digest(snapshot) and file_path.name not in (refused.get("files") or [])


def remember_refusal(file_path: Path, snapshot: dict) -> None:
    refusals = read_state(REFUSALS_FILE) or {}
    deck, build = str(snapshot["deck"]), build_digest(snapshot)
    refused = refusals.get(deck)
    files = (refused.get("files") or []) if isinstance(refused, dict) and refused.get("build") == build else []
    refusals[deck] = {"build": build, "files": [*files, file_path.name]}
    write_state(REFUSALS_FILE, refusals)
