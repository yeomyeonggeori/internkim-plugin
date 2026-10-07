from __future__ import annotations

import json
from pathlib import Path

from delivery.claim_check import BLANKED, NO_REMAKE_COMMAND, NOT_EDITABLE, REMAKE_FAILED, SUPPORTED, UNREAD_SOURCES, ClaimCheck
from delivery.claim_kinds import ERROR, MISTAKE, Verdict


METADATA_SUFFIX = ".meta.json"
CONTENT_FIELDS = ("schema", "given", "tables", "views", "charts", "slides")
COMPANION_FIELDS = ("blanks",)


def metadata_path_of(file_path: Path) -> Path:
    return file_path.with_name(file_path.name + METADATA_SUFFIX)


def write_metadata(file_path: Path, snapshot: dict, checks: list[ClaimCheck], leftover_slides: list[dict]) -> Path:
    document = {"holds": holds_of(snapshot), "notes": delivered_file_notes(file_path.name, blank_labels(snapshot), checks, leftover_slides)}
    path = metadata_path_of(file_path)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def holds_of(snapshot: dict) -> dict:
    held = {name: snapshot[name] for name in CONTENT_FIELDS if name in snapshot}
    if not held:
        return {}
    return held | {name: snapshot[name] for name in COMPANION_FIELDS if name in snapshot}


def blank_labels(snapshot: dict) -> list[str]:
    labels = []
    for blank in snapshot.get("blanks") or ():
        label = str(blank.get("label") or "") if isinstance(blank, dict) else ""
        if label and label not in labels:
            labels.append(label)
    return labels


def delivered_file_notes(filename: str, labels: list[str], checks: list[ClaimCheck], leftover_slides: list[dict]) -> list[str]:
    notes = []
    blanks = blank_descriptions(labels, checks)
    if blanks:
        notes.append(f"{filename}: left blank, for the reply to offer to complete; the file no longer holds what these places said, so the reply names each place and never repeats what was there: {', '.join(blanks)}")
    notes += left_in_file_notes(filename, checks)
    if leftover_slides:
        notes.append(f"{filename}: slides that still show a defect after the visual review, for the reply to say what remains: {leftover_slide_names(leftover_slides)}")
    return notes


def blank_descriptions(labels: list[str], checks: list[ClaimCheck]) -> list[str]:
    flagged = [verdict for check in checks if check.outcome == BLANKED for verdict in check.flagged]
    described_places = {verdict.place for verdict in flagged}
    descriptions = list(dict.fromkeys(f"{verdict.place} ({flag_reason(verdict.defect)})" for verdict in flagged))
    return descriptions + [label for label in dict.fromkeys(labels) if label.strip() and label not in described_places]


def flag_reason(defect: str) -> str:
    if defect == MISTAKE:
        return "it differs from what the person gave: ask them to confirm the right value"
    if defect == ERROR:
        return "it does not follow from what the person gave, or contradicts another part of the document: ask them to confirm"
    return "nothing the person gave supports it"


def left_in_file_notes(filename: str, checks: list[ClaimCheck]) -> list[str]:
    notes = []
    for check in checks:
        if check.outcome in (BLANKED, SUPPORTED) or not check.flagged:
            continue
        units = "; ".join(unit_description(verdict) for verdict in check.flagged)
        notes.append(f"{filename}: could not be blanked ({left_in_file_cause(check)}), so these are still in the file and the reply must say so and offer to fix them: {units}")
    return notes


def unit_description(verdict: Verdict) -> str:
    return f"{verdict.place} (it says {json.dumps(verdict.claim.text, ensure_ascii=False)}, {flag_reason(verdict.defect)})"


def left_in_file_cause(check: ClaimCheck) -> str:
    if check.outcome == REMAKE_FAILED:
        return f"the remake failed: {check.detail}"
    if check.outcome == NO_REMAKE_COMMAND:
        return "the file's snapshot names no command that remakes it"
    if check.outcome == NOT_EDITABLE:
        return "this kind of file cannot be edited in place and no snapshot remakes it as it is"
    if check.outcome == UNREAD_SOURCES:
        return "an attachment was not read, so the check was not enforced"
    return check.outcome


def leftover_slide_names(leftover_slides: list[dict]) -> str:
    names = []
    for leftover in leftover_slides:
        kinds = [*leftover.get("findings", ()), *leftover.get("measured", ())]
        names.append(f"slide {leftover['number']}" + (f" ({', '.join(kinds)})" if kinds else ""))
    return ", ".join(names)
