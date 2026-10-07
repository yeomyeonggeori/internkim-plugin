from __future__ import annotations

from dataclasses import dataclass, field, replace
import json

from delivery.claim_kinds import BLANK, COMPACT_PROFILE, DERIVED, ERROR, REWRITE, Claim, Judgment, Profile, Sources, Verdict, batch_state, judge
from host import script_host


RECOMPUTE_SCHEMA = {
    "type": "object",
    "properties": {"checks": {"type": "array", "items": {"type": "object", "properties": {
        "key": {"type": "string"},
        "working": {"type": "string", "description": "the recomputation from the sources' values, step by step, ending in your result"},
        "isWrong": {"type": "boolean", "description": "true only when your result differs from the unit's stated value"},
    }, "required": ["key", "working", "isWrong"], "additionalProperties": False}}},
    "required": ["checks"],
    "additionalProperties": False,
}

REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string", "description": "the rewritten unit, nothing else"}},
    "required": ["text"],
    "additionalProperties": False,
}


@dataclass
class Outcome:
    blank: list = field(default_factory=list)
    replaced: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    kept: list = field(default_factory=list)
    cost: float = 0.0
    calls: int = 0

    def changes_nothing(self) -> bool:
        return not (self.blank or self.removed or self.replaced)


def sources_state(sources: Sources) -> str:
    state = batch_state(COMPACT_PROFILE, sources, [])
    del state["claims"], state["kinds"]
    return json.dumps(state, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def recompute(sources: Sources, judgment: Judgment, profile: Profile = COMPACT_PROFILE) -> Judgment:
    derived = derived_units(judgment)
    if not derived:
        return judgment
    answer = script_host.generate(recompute_prompt(sources, derived), RECOMPUTE_SCHEMA)
    verdicts = with_wrong_derivations(judgment.verdicts, derived, wrong_keys(answer.get("answer")), profile)
    return Judgment(verdicts=verdicts, cost=judgment.cost + script_host.cost_of(answer), calls=judgment.calls + 1)


def with_wrong_derivations(verdicts: list[Verdict], derived: dict[str, Verdict], wrong: set[str], profile: Profile) -> list[Verdict]:
    rechecked = list(verdicts)
    for index, verdict in enumerate(rechecked):
        key = verdict_key(index)
        if key in wrong and key in derived and derived[key].claim.text == verdict.claim.text:
            rechecked[index] = replace(verdict, defect=ERROR, treatment=profile.treatments.get(ERROR, ""))
    return rechecked


def verdict_key(index: int) -> str:
    return f"claim{index}"


def derived_units(judgment: Judgment) -> dict[str, Verdict]:
    return {verdict_key(index): verdict for index, verdict in enumerate(judgment.verdicts) if verdict.kind == DERIVED and not verdict.defect and not verdict.is_copied}


def wrong_keys(answer: object) -> set[str]:
    if not isinstance(answer, dict) or not isinstance(answer.get("checks"), list):
        raise script_host.HostFailure(f"recompute: the answer {answer!r} does not fit the schema")
    return {str(check.get("key")) for check in answer["checks"] if isinstance(check, dict) and check.get("isWrong") is True}


def recompute_prompt(sources: Sources, derived: dict[str, Verdict]) -> str:
    units = json.dumps({key: ({"at": verdict.claim.at} if verdict.claim.at else {}) | {"text": verdict.claim.text} for key, verdict in derived.items()}, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return ("Each unit below was written into a business document as following from the sources by arithmetic, the calendar or plain reasoning. "
            "Recompute each one from the values the sources give, step by step in your head, and mark a unit wrong only when your result differs from its stated figure, date or conclusion. "
            "Do not list a unit because it is brief, incomplete or worded differently, or because you cannot find its inputs. "
            "Check every unit in checks, with your working before your verdict.\nSources: " + sources_state(sources) + "\nUnits: " + units)


def treat(sources: Sources, judgment: Judgment, profile: Profile = COMPACT_PROFILE) -> Outcome:
    outcome = Outcome(blank=judgment.treated(BLANK))
    rewrites, rewritten = rewritten_units(outcome, profile, sources, judgment.treated(REWRITE))
    if not rewrites:
        return outcome
    rechecked = judge(sources, rewrites, profile)
    outcome.cost += rechecked.cost
    outcome.calls += rechecked.calls
    for original, rewrite in zip(rewritten, rechecked.verdicts):
        place(outcome, original, rewrite)
    return outcome


def place(outcome: Outcome, original: Verdict, rewrite: Verdict) -> None:
    if rewrite.defect:
        outcome.kept.append(original)
    elif rewrite.claim.text.strip():
        outcome.replaced.append(rewrite.claim)
    elif original.claim.is_free:
        outcome.removed.append(original)
    else:
        outcome.kept.append(original)


def rewritten_units(outcome: Outcome, profile: Profile, sources: Sources, verdicts: list[Verdict]) -> tuple[list[Claim], list[Verdict]]:
    rewrites, rewritten = [], []
    for verdict in verdicts:
        try:
            answer = script_host.generate(rewrite_prompt(profile, sources, verdict), REWRITE_SCHEMA)
        except script_host.HostFailure:
            outcome.kept.append(verdict)
            continue
        outcome.cost += script_host.cost_of(answer)
        outcome.calls += 1
        text = (answer.get("answer") or {}).get("text") if isinstance(answer.get("answer"), dict) else None
        if not isinstance(text, str):
            outcome.kept.append(verdict)
            continue
        rewrites.append(Claim(path=verdict.claim.path, at=verdict.claim.at, text=text.strip(), is_free=verdict.claim.is_free))
        rewritten.append(verdict)
    return rewrites, rewritten


def rewrite_prompt(profile: Profile, sources: Sources, verdict: Verdict) -> str:
    return (f"You rewrite one unit of a business document. {profile.rewrites.get(verdict.defect, '')}\nSources: {sources_state(sources)}\nUnit: {verdict.claim.text}\n"
            "Answer with the rewritten unit as the text field. Keep every fact, number and name the unit already has, and add none.")
