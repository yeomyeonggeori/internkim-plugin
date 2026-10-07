from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path
import time

from core.office_result import Result
from core.source_snapshot import DELIVERABLE_EXTENSIONS, read_source, write_source
from delivery.claim_check import is_remake
from host import script_host
from host.task_context import load_task_context


MAKING_VERBS = ("merge", "create")
MADE_KEY = "made"
LEFTOVERS_KEY = "reviewLeftovers"
REVIEW_BUDGET_SECONDS = 75


def finished(result: Result) -> Result:
    file_path = made_path(result)
    if file_path is None:
        return result
    review = reviewed_deck(file_path)
    snapshot = read_source(file_path) | {MADE_KEY: file_digest(file_path)}
    if review is not None:
        snapshot[LEFTOVERS_KEY] = review.leftovers
    write_source(file_path, snapshot)
    if review is None:
        return result
    return replace(result, details=dict(result.details or {}) | {"visualReview": review.to_json()})


def made_path(result: Result) -> Path | None:
    if result.status == "error" or os.environ.get("OFFICE_COMMAND", "").removeprefix("office ").strip() not in MAKING_VERBS or not result.output_path:
        return None
    file_path = Path(result.output_path).expanduser()
    if file_path.suffix.lower() not in DELIVERABLE_EXTENSIONS or not read_source(file_path):
        return None
    return file_path


def reviewed_deck(file_path: Path):
    snapshot = read_source(file_path)
    if is_remake() or not snapshot.get("visualReview") or not script_host.is_present() or load_task_context() is None:
        return None
    from delivery.visual_review import review_deck

    return review_deck(file_path, snapshot, time.monotonic() + REVIEW_BUDGET_SECONDS)


def file_digest(file_path: Path) -> str:
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def is_as_made(file_path: Path, snapshot: dict) -> bool:
    return bool(snapshot.get(MADE_KEY)) and snapshot[MADE_KEY] == file_digest(file_path)
