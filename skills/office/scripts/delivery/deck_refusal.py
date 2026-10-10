from __future__ import annotations

import hashlib
import json
from pathlib import Path

from deck.deck_decisions import read_state, write_state


REFUSALS_FILE = "deck-claim-refusals.json"
PRESENTATION_EXTENSION = ".pptx"


def is_deck(file_path: Path, snapshot: dict) -> bool:
    return bool(snapshot.get("deck")) or file_path.suffix.lower() == PRESENTATION_EXTENSION


def deck_key(file_path: Path, snapshot: dict) -> str:
    return str(snapshot.get("deck") or file_path.resolve())


def build_digest(file_path: Path, snapshot: dict) -> str:
    if not snapshot.get("deck"):
        return hashlib.sha256(file_path.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(snapshot.get("claims") or [], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def deck_refusals(file_path: Path, snapshot: dict) -> dict:
    refused = (read_state(REFUSALS_FILE) or {}).get(deck_key(file_path, snapshot))
    return refused if isinstance(refused, dict) else {}


def may_refuse(file_path: Path, snapshot: dict, is_losing_slides: bool) -> bool:
    refused = deck_refusals(file_path, snapshot)
    builds = refused.get("builds") or {}
    files = builds.get(build_digest(file_path, snapshot))
    if files is not None:
        return file_path.name not in files
    return not builds or (is_losing_slides and not refused.get("refusedSlideLoss"))


def remember_refusal(file_path: Path, snapshot: dict, is_losing_slides: bool) -> None:
    refusals = read_state(REFUSALS_FILE) or {}
    refused = deck_refusals(file_path, snapshot)
    builds = refused.get("builds") or {}
    build = build_digest(file_path, snapshot)
    builds[build] = [*builds.get(build, []), file_path.name]
    refusals[deck_key(file_path, snapshot)] = {"builds": builds, "refusedSlideLoss": bool(refused.get("refusedSlideLoss")) or is_losing_slides}
    write_state(REFUSALS_FILE, refusals)
