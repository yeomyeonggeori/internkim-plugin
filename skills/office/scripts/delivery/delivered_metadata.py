from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from delivery.claim_check import BLANKED, NO_REMAKE_COMMAND, NOT_EDITABLE, REFUSED, REMAKE_FAILED, SUPPORTED, UNREAD_SOURCES, ClaimCheck
from delivery.claim_kinds import ERROR, MISTAKE, Verdict
from schemas.blank_paths import WITHDRAWN, WITHDRAWN_SLIDE, WITHDRAWN_TEXT, WITHDRAWN_VALUE


METADATA_SUFFIX = ".meta.json"
CONTENT_FIELDS = ("schema", "given", "tables", "views", "charts", "slides")
COMPANION_FIELDS = ("blanks",)


def metadata_path_of(file_path: Path) -> Path:
    return file_path.with_name(file_path.name + METADATA_SUFFIX)


def write_metadata(file_path: Path, snapshot: dict, checks: list[ClaimCheck], leftover_slides: list[dict]) -> Path:
    refused = [check for check in checks if check.outcome == REFUSED]
    if refused:
        document = {"holds": {}, "notes": [], "refusal": refusal(file_path.name, refused)}
    else:
        notes = delivered_file_notes(file_path.name, snapshot_blanks(snapshot), checks, leftover_slides) + slide_count_notes(file_path.name, snapshot)
        document = {"holds": holds_of(snapshot), "notes": notes}
    path = metadata_path_of(file_path)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def refusal(filename: str, checks: list[ClaimCheck]) -> str:
    statements = "; ".join(unit_description(verdict) for check in checks for verdict in check.flagged)
    losing = ", ".join(slide["label"] for check in checks for slide in check.losing_slides)
    loss = f" Taking them out would leave nothing to show on {losing}, so the deck would lose that slide; keep the slide by giving it content the person did support." if losing else ""
    return (f"{filename} was not delivered. Its pages state what nothing the person gave supports: {statements}.{loss} "
            "Rewrite each page named here without these statements, recomposing the page so it still reads as finished, with no box, row, number or bullet left where a statement was, "
            "then build the deck again and deliver it. A statement only the person can supply stays out of the deck, and the final reply asks them for it. "
            "A deck delivered again still holding such a statement is delivered with the check taking it out of the file.")


def slide_count_notes(filename: str, snapshot: dict) -> list[str]:
    removed = [str(blank["label"]) for blank in snapshot_blanks(snapshot) if blank.get(WITHDRAWN) == WITHDRAWN_SLIDE]
    if not removed:
        return []
    count = len(snapshot.get("slides") or [])
    return [f"{filename}: the check took these slides out whole, because what they showed was taken out; the file has {count} slides, so the reply gives that count and never describes these slides as part of the file: {', '.join(removed)}"]


def holds_of(snapshot: dict) -> dict:
    held = {name: snapshot[name] for name in CONTENT_FIELDS if name in snapshot}
    if not held:
        return {}
    return held | {name: snapshot[name] for name in COMPANION_FIELDS if name in snapshot}


def snapshot_blanks(snapshot: dict) -> list[dict]:
    return [blank for blank in snapshot.get("blanks") or () if isinstance(blank, dict) and str(blank.get("label") or "").strip()]


def delivered_file_notes(filename: str, blanks: list[dict], checks: list[ClaimCheck], leftover_slides: list[dict]) -> list[str]:
    notes = []
    blanked = BlankedPlaces.of(blanks, checks)
    if blanked.never_given or blanked.taken_values:
        notes.append(f"{filename}: left blank, for the reply to offer to complete" + "".join(blank_clauses(blanked.never_given, blanked.taken_values)))
    if blanked.taken_text:
        notes.append(f"{filename}: text the check took out of these places; each place keeps whatever else it holds, so the reply says text was taken out of it, never that the place is empty or left blank, and never repeats what was there: {', '.join(blanked.taken_text)}")
    notes += left_in_file_notes(filename, checks)
    if leftover_slides:
        notes.append(f"{filename}: slides that still show a defect after the visual review, for the reply to say what remains: {leftover_slide_names(leftover_slides)}")
    return notes


def blank_clauses(never_given: list[str], taken_out: list[str]) -> list[str]:
    clauses = [f": {', '.join(never_given)}"] if never_given else []
    if taken_out:
        clauses.append(f"; taken out by the check, so the file no longer holds what these places said and the reply names each place and never repeats what was there: {', '.join(taken_out)}")
    return clauses


@dataclass(frozen=True)
class BlankedPlaces:
    never_given: list[str]
    taken_values: list[str]
    taken_text: list[str]

    @staticmethod
    def of(blanks: list[dict], checks: list[ClaimCheck]) -> "BlankedPlaces":
        flagged = {verdict.claim.path: verdict for check in checks if check.outcome == BLANKED for verdict in check.flagged}
        never_given, taken_values, taken_text = [], [], []
        for blank in blanks:
            if blank.get(WITHDRAWN) == WITHDRAWN_SLIDE:
                continue
            verdict = flagged.pop(str(blank.get("field") or ""), None)
            withdrawal = withdrawal_of(blank, verdict)
            if not withdrawal:
                never_given.append(str(blank["label"]))
                continue
            (taken_text if withdrawal == WITHDRAWN_TEXT else taken_values).append(taken_out_place(str(blank["label"]), verdict))
        taken_text += [taken_out_place(verdict.place, verdict) for verdict in flagged.values()]
        return BlankedPlaces(unique(never_given), unique(taken_values), unique(taken_text))


def withdrawal_of(blank: dict, verdict: Verdict | None) -> str:
    if blank.get(WITHDRAWN):
        return str(blank[WITHDRAWN])
    return WITHDRAWN_VALUE if verdict else ""


def taken_out_place(label: str, verdict: Verdict | None) -> str:
    return f"{label} ({flag_reason(verdict.defect)})" if verdict else label


def unique(names: list[str]) -> list[str]:
    return list(dict.fromkeys(names))


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
