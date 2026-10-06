from __future__ import annotations

from dataclasses import dataclass, field, replace

from host import script_host


CLAIM_THRESHOLD = 0.5
CLAIMS_PER_CALL = 60
ATTACHMENT_MAXIMUM_CHARACTERS = 6000

SOURCE = "source"
DERIVED = "derived"
EXPRESSION = "expression"
CLAIM = "claim"
MISTAKE = "mistake"
ERROR = "error"
HOLLOW = "hollow"

BLANK = "blank"
REWRITE = "rewrite"

ABOUT = ("The sources are request (the requester's own words), attachments (the text of the files they attached) "
         "and runtimeFacts (what the system knew when it made the document: today, the requester, the document number and the company profile). "
         "Each claim is one value the writer put into a delivered document; at says where it sits. All claims belong to one document, so a claim can be checked against the others. "
         "removed, when present, lists values that were taken out of the document because the sources did not support them; the document no longer holds them.")

SOURCE_KIND = "says what the request, attachments or runtimeFacts say, in other words, shortened or merged, with the same values, owners and status; a figure credited to an origin the sources name as its origin is source"
DERIVED_KIND = "follows correctly from the sources by arithmetic or the calendar (a total, a share, a multiple, a duration, a weekday), is a heading or label naming what the sources hold, or summarizes them adding nothing"
EXPRESSION_KIND = ("a unit with a relational role: a greeting, thanks, an apology, sympathy, an invitation to get in touch, a closing wish; a formulaic line that does a social or legal job "
                   "(a business-letter greeting or closing, a contract recital, an agreement preamble, an offer-letter welcome, a proposal closing); or emphasis on, or an interpretation of, "
                   "this document's own facts that adds no fact of its own (growth called fast when the sources give the figures, demand called proven when the sources show it). "
                   "A line that does none of these jobs and only sounds weighty is hollow")

ORIGIN_GUARD = ("A credit to an origin, such as a Source line, is judged on its own: choose claim when the sources do not name that origin, even when the figures beside it are in the sources; "
                "a heading or label that names what the sources hold without crediting an origin is not claim. ")

GUARD_TODAY = ("Wording, tone, emphasis and formatting are never claim, and whether the tone suits the kind of document is not this question. "
               + ORIGIN_GUARD + "Choose claim only for content the sources do not hold, or hold with a weaker status.")

GUARD_KINDS = ("Wording, tone, emphasis, formatting and where a value sits in a list are never a defect: choose source, derived or expression when the claim says what the sources say, however differently. "
               "Choose claim for content the sources do not hold, and do not require a unit to be wrong to be a claim. " + ORIGIN_GUARD
               + "Choose mistake or error only when you can name the exact source value or other claim it conflicts with; do not add a requirement the sources do not state.")

INVENTED_FRAMING = ("an origin named as where a figure comes from (a source line, a report, survey, dataset, internal system or metrics) that the sources do not state as that figure's origin, "
                    "even when the figure itself is in the sources: a figure the request gives has no origin unless the request names one; "
                    "a slogan or tagline presented as the company's or product's own that the sources do not state; ")

REMOVED_REFERENCE = "a count, total, ordinal or reference that includes or names a value listed under removed, since the document no longer holds that value"

CLAIM_KIND = ("a specific, checkable fact, number, name, customer, ranking, date, promise, condition, cause or availability that no source holds and that no source contradicts; "
              + INVENTED_FRAMING + "a new obligation; an evaluation of a person or of a quality stated as attested fact; or " + REMOVED_REFERENCE)

HOLLOW_KIND = ("a unit that spends the reader's attention and trust while giving nothing back: it conveys none of this document's facts, grounds for judgment, requests or relational gestures, "
               "and instead asserts a vague value or significance that cannot be checked, or manufactures weight through rhetorical form alone. "
               "Such text dilutes the real information, reads as machine-written so that the reader trusts even the true facts less, and signals that the writer did not think about this reader and situation. "
               "It is hollow only if all three hold: (1) interchangeable: with only the names swapped it would fit any other document unchanged; "
               "(2) functionless: removing it loses the reader nothing; "
               "(3) uncheckable weight: it asserts an evaluation that cannot be verified, or its form is the message. "
               "For a borderline unit ask: without this unit, would the document read as more trustworthy and faster to the reader? If yes, it is hollow. "
               "If removing it makes the document colder or impolite (greetings, thanks, a formal letter's conventions), it is expression, not hollow. "
               "A specific checkable fact with no source is claim, and a real fact of this document restated wrongly or with its status changed is mistake. "
               "Never choose hollow for tone, length, style or formality, or for any reason outside these criteria.")


@dataclass(frozen=True)
class Profile:
    name: str
    kinds: dict
    guard: str
    treatments: dict
    rewrites: dict = field(default_factory=dict)

    def defect_of(self, probabilities: dict, threshold: float) -> str:
        total, strongest, strongest_kind = 0.0, 0.0, ""
        for kind in sorted(self.treatments):
            probability = float(probabilities.get(kind) or 0.0)
            total += probability
            if probability > strongest:
                strongest, strongest_kind = probability, kind
        return strongest_kind if total >= threshold else ""

    def verdict_for(self, claim: "Claim", choice: str, probabilities: dict) -> "Verdict":
        defect = self.defect_of(probabilities, CLAIM_THRESHOLD)
        return Verdict(claim=claim, kind=choice, probabilities=probabilities, defect=defect, treatment=self.treatments.get(defect, ""))


TODAY_PROFILE = Profile(
    name="today",
    kinds={
        SOURCE: SOURCE_KIND,
        DERIVED: DERIVED_KIND,
        EXPRESSION: EXPRESSION_KIND,
        CLAIM: ("anything else: a fact, number, name, customer, ranking, date, promise, condition, cause or availability the sources lack; "
                "a source fact stated with a stronger status (a forecast or target as achieved or confirmed, some as all, planned as done, an estimate or average as exact or guaranteed); "
                + INVENTED_FRAMING + "a new obligation; an evaluation of a person or of a quality stated as attested fact; or " + REMOVED_REFERENCE),
    },
    guard=GUARD_TODAY,
    treatments={CLAIM: BLANK},
)

COMPACT_PROFILE = Profile(
    name="compact",
    kinds={
        SOURCE: SOURCE_KIND,
        DERIVED: DERIVED_KIND,
        EXPRESSION: EXPRESSION_KIND,
        CLAIM: CLAIM_KIND,
        MISTAKE: ("restates something the sources give but gets it wrong: a number, date, name, amount, owner or party that differs from the source, "
                  "or a status or scope the source does not give (a forecast stated as fact, a plan as done, some as all, an estimate as exact)"),
        ERROR: ("derives or reasons from the sources and gets it wrong: a sum, share, date offset, unit conversion or conclusion that does not follow from the values the sources give, "
                "or a claim that cannot be true together with another claim of the same document"),
        HOLLOW: HOLLOW_KIND,
    },
    guard=GUARD_KINDS,
    treatments={CLAIM: BLANK, MISTAKE: BLANK, ERROR: BLANK, HOLLOW: REWRITE},
    rewrites={HOLLOW: "Replace it with this document's own facts that the sources give, stated plainly, or answer with an empty text when none fits. Never add plausible-sounding new content: no number, name, date or specific the sources do not hold."},
)


@dataclass(frozen=True)
class Claim:
    path: str
    text: str
    at: str = ""
    is_free: bool = False

    def to_json(self) -> dict:
        return {"path": self.path, "text": self.text} | ({"at": self.at} if self.at else {})

    @staticmethod
    def from_json(document: dict) -> "Claim":
        return Claim(path=str(document.get("path") or ""), text=str(document.get("text") or ""), at=str(document.get("at") or ""))


@dataclass(frozen=True)
class Verdict:
    claim: Claim
    kind: str
    probabilities: dict = field(default_factory=dict)
    defect: str = ""
    treatment: str = ""
    is_copied: bool = False

    @property
    def place(self) -> str:
        return self.claim.at or self.claim.path

    def to_json(self) -> dict:
        document = self.claim.to_json() | {"kind": self.kind}
        return document | ({"defect": self.defect, "treatment": self.treatment} if self.defect else {})


@dataclass(frozen=True)
class AttachmentText:
    name: str
    text: str


@dataclass(frozen=True)
class Sources:
    request: tuple = ()
    attachments: tuple = ()
    runtime_facts: dict = field(default_factory=dict)
    removed: tuple = ()

    def with_removed(self, removed: list[Claim]) -> "Sources":
        return replace(self, removed=tuple(removed))


@dataclass
class Judgment:
    verdicts: list = field(default_factory=list)
    cost: float = 0.0
    calls: int = 0

    def flagged(self) -> list[Verdict]:
        return [verdict for verdict in self.verdicts if verdict.defect]

    def treated(self, treatment: str) -> list[Verdict]:
        return [verdict for verdict in self.flagged() if verdict.treatment == treatment]

    def asked(self) -> int:
        return sum(1 for verdict in self.verdicts if not verdict.is_copied)


def judge(sources: Sources, claims: list[Claim], profile: Profile = COMPACT_PROFILE) -> Judgment:
    judgment = Judgment()
    copies = copy_sources(sources)
    asked = []
    for claim in claims:
        if is_copied_from(claim.text, copies):
            judgment.verdicts.append(Verdict(claim=claim, kind=SOURCE, is_copied=True))
        else:
            asked.append(claim)
    for start in range(0, len(asked), CLAIMS_PER_CALL):
        verdicts, cost = judge_batch(profile, sources, asked[start:start + CLAIMS_PER_CALL])
        judgment.verdicts += verdicts
        judgment.cost += cost
        judgment.calls += 1
    return judgment


def judge_batch(profile: Profile, sources: Sources, claims: list[Claim]) -> tuple[list[Verdict], float]:
    answer = script_host.decide(batch_state(profile, sources, claims), batch_questions(profile, len(claims)))
    answers = answer.get("answers") or {}
    verdicts = []
    for index, claim in enumerate(claims):
        given = answers.get(question_key(index))
        if not isinstance(given, dict):
            raise script_host.HostFailure(f"the decision model gave no answer for {question_key(index)}")
        verdicts.append(profile.verdict_for(claim, str(given.get("choice") or ""), given.get("probabilities") or {}))
    return verdicts, script_host.cost_of(answer)


def batch_state(profile: Profile, sources: Sources, claims: list[Claim]) -> dict:
    state = {"about": ABOUT, "kinds": profile.kinds, "request": "\n\n".join(sources.request), "claims": {question_key(index): shown(claim) for index, claim in enumerate(claims)}}
    if sources.removed:
        state["removed"] = [shown(claim) for claim in sources.removed]
    if sources.runtime_facts:
        state["runtimeFacts"] = sources.runtime_facts
    attachments = bounded_attachments(sources.attachments)
    if attachments:
        state["attachments"] = attachments
    return state


def shown(claim: Claim) -> dict:
    return ({"at": claim.at} if claim.at else {}) | {"text": claim.text}


def batch_questions(profile: Profile, count: int) -> dict:
    options = {name: name for name in profile.kinds}
    return {
        question_key(index): script_host.choice_question(
            f"Which kind of value is claims.{question_key(index)}? {profile.guard} Judge only claims.{question_key(index)}. The kinds are defined in kinds.", options)
        for index in range(count)
    }


def question_key(index: int) -> str:
    return f"claim{index}"


def bounded_attachments(attachments: tuple) -> list[dict]:
    return [{"name": attachment.name, "text": attachment.text[:ATTACHMENT_MAXIMUM_CHARACTERS]} for attachment in attachments if attachment.text.strip()]


def copy_sources(sources: Sources) -> list[str]:
    return [*sources.request, *(attachment.text for attachment in sources.attachments), *string_values(sources.runtime_facts)]


def is_copied_from(text: str, sources: list[str]) -> bool:
    wanted = collapsed_space(text)
    return not wanted or any(wanted in collapsed_space(source) for source in sources)


def collapsed_space(text: str) -> str:
    return " ".join(text.split())


def string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in string_values(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in string_values(item)]
    return []
