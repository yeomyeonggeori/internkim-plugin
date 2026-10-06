from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from core.source_snapshot import SOURCE_SUFFIX
from delivery.claim_check import OFFICE_ENTRY, REMAKE_TIMEOUT_SECONDS, REMAKE_VARIABLE, remake_failure
from delivery.review_manifest import Manifest, ManifestError, parse_manifest


class RebuildError(Exception):
    pass


class OfficeDeck:
    def __init__(self, file_path: Path, snapshot: dict, office_entry: Path = OFFICE_ENTRY):
        self.file_path = file_path
        self.snapshot = snapshot
        self.office_entry = office_entry

    def manifest(self) -> Manifest:
        return parse_manifest(Path(self.snapshot["visualReview"]).read_text(encoding="utf-8"))

    def image(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def rebuild(self, replacements: dict[int, str]) -> Manifest:
        try:
            return self.rebuilt_with(replacements)
        except (ManifestError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as failure:
            raise RebuildError(str(failure)) from failure

    def rebuilt_with(self, replacements: dict[int, str]) -> Manifest:
        words = rebuild_words(self.snapshot)
        originals = self.write_pages(self.manifest(), replacements)
        try:
            failure = self.run_office(words)
        except subprocess.TimeoutExpired:
            restore_pages(originals)
            raise
        if failure:
            restore_pages(originals)
            raise RebuildError("the deck rebuild failed: " + failure)
        return self.rebuilt_manifest()

    def write_pages(self, manifest: Manifest, replacements: dict[int, str]) -> dict[Path, bytes]:
        originals: dict[Path, bytes] = {}
        try:
            for number, section in replacements.items():
                page = manifest.page_source(number)
                if not page:
                    raise RebuildError(f"slide {number} names no page file")
                originals[Path(page)] = Path(page).read_bytes()
                Path(page).write_text(section + "\n", encoding="utf-8")
        except (RebuildError, OSError) as failure:
            restore_pages(originals)
            raise RebuildError(str(failure)) from failure
        return originals

    def run_office(self, words: list[str]) -> str:
        environment = {**os.environ, REMAKE_VARIABLE: "1"}
        completed = subprocess.run([sys.executable, str(self.office_entry), *words], capture_output=True, text=True, env=environment, timeout=REMAKE_TIMEOUT_SECONDS)
        return "" if completed.returncode == 0 else remake_failure(completed)

    def rebuilt_manifest(self) -> Manifest:
        snapshot_path = self.file_path.with_name(self.file_path.name + SOURCE_SUFFIX)
        rebuilt = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if not rebuilt.get("visualReview"):
            raise RebuildError("the rebuilt deck names no visual review")
        self.snapshot = rebuilt
        return self.manifest()


def restore_pages(originals: dict[Path, bytes]) -> None:
    for page, original in originals.items():
        page.write_bytes(original)


def rebuild_words(snapshot: dict) -> list[str]:
    command = str(snapshot.get("command") or "").split()
    arguments = [str(argument) for argument in snapshot.get("arguments") or ()]
    if len(command) < 2 or command[0] != "office" or not arguments:
        raise RebuildError("the snapshot records no office command to rebuild the deck with")
    return [*command[1:], *arguments]
