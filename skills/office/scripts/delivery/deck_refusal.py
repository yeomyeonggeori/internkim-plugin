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


def refused_builds(file_path: Path, snapshot: dict) -> dict:
    refused = (read_state(REFUSALS_FILE) or {}).get(deck_key(file_path, snapshot))
    if not isinstance(refused, dict):
        return {}
    return refused.get("builds") or {}


def may_refuse(file_path: Path, snapshot: dict, is_losing_slides: bool) -> bool:
    builds = refused_builds(file_path, snapshot)
    files = builds.get(build_digest(file_path, snapshot))
    if files is not None:
        return file_path.name not in files
    return not builds or is_losing_slides


def remember_refusal(file_path: Path, snapshot: dict) -> None:
    refusals = read_state(REFUSALS_FILE) or {}
    builds = refused_builds(file_path, snapshot)
    build = build_digest(file_path, snapshot)
    builds[build] = [*builds.get(build, []), file_path.name]
    refusals[deck_key(file_path, snapshot)] = {"builds": builds}
    write_state(REFUSALS_FILE, refusals)
