from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
import html
import json
from pathlib import Path
import re
import time
from typing import Callable, Protocol

from delivery.office_deck import OfficeDeck, RebuildError
from delivery.review_images import IMAGE_MEDIA_TYPE, contact_sheet, fit_image
from delivery.review_manifest import Manifest, ManifestError, Question, Slide
from host import script_host


QUESTION_KEY = "visual_defect"
DECK_QUESTION_PREFIX = "slide_"
MAXIMUM_PARALLEL_CALLS = 16
MAXIMUM_REFUSAL_CHARACTERS = 1500
RECOMPOSE_ROUNDS = 1
SHEET_DESCRIPTION = "every slide of the deck at reduced size, in reading order from the top left; the number on each tile is the slide's number"

CLEAN = "clean"
FIXED = "fixed"
LEFTOVERS = "leftovers"
REVIEW_FAILED = "review_failed"
UNAVAILABLE = "unavailable"

REPAIR_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["section", "change"], "properties": {"section": {"type": "string"}, "change": {"type": "string"}}}

SECTION_OPENING = re.compile(r"<section[\s>]", re.IGNORECASE)
SECTION_CLOSING = re.compile(r"</section\s*>", re.IGNORECASE)
TABLE_PATTERN = re.compile(r"<table[\s>]", re.IGNORECASE)
IMAGE_PATTERN = re.compile(r"<img[\s>]", re.IGNORECASE)
CHART_PATTERN = re.compile(r'data-chart="([^"]*)"')
NOTES_PATTERN = re.compile(r'<aside\b[^>]*class="[^"]*\bnotes\b[^"]*"[^>]*>.*?</aside>', re.IGNORECASE | re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]*>", re.DOTALL)


class Deck(Protocol):
    def manifest(self) -> Manifest: ...

    def image(self, path: str) -> bytes: ...

    def rebuild(self, replacements: dict[int, str]) -> Manifest: ...


@dataclass
class Assessment:
    probabilities: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    measured: tuple = ()
    error: str = ""
    cost: float = 0.0
    is_asked: bool = False

    def is_flagged(self) -> bool:
        return bool(self.findings or self.measured)

    def kinds(self) -> list[str]:
        return [finding["kind"] for finding in self.findings]


@dataclass
class Attempt:
    section: str = ""
    change: str = ""
    problem: str = ""
    cost: float = 0.0
    is_asked: bool = False

    def is_accepted(self) -> bool:
        return not self.problem


@dataclass
class DeckReview:
    sheet: script_host.Image | None
    assessments: dict
    cost: float


@dataclass
class VisualReview:
    file: str
    rounds_used: int = 0
    fixed: list = field(default_factory=list)
    given_up: list = field(default_factory=list)
    leftovers: list = field(default_factory=list)
    text_changed: list = field(default_factory=list)
    cost: float = 0.0
    calls: int = 0
    outcome: str = ""
    detail: str = ""

    def to_json(self) -> dict:
        document = {"file": self.file, "roundsUsed": self.rounds_used, "costUSD": round(self.cost, 6), "calls": self.calls, "outcome": self.outcome}
        optional = {"fixed": self.fixed, "givenUp": self.given_up, "leftovers": self.leftovers, "textChanged": self.text_changed, "detail": self.detail}
        return document | {name: value for name, value in optional.items() if value}


def review_deck(file_path: Path, snapshot: dict, deadline: float, is_recompose_only: bool = False) -> VisualReview:
    return run_review(OfficeDeck(Path(file_path), snapshot), Path(file_path).name, deadline, is_recompose_only)


def run_review(deck: Deck, file_name: str, deadline: float, is_recompose_only: bool = False) -> VisualReview:
    review = VisualReview(file=file_name)
    loop = None
    try:
        loop = ReviewLoop(deck, is_recompose_only)
        loop.run(deadline)
    except script_host.HostUnavailable as unavailable:
        review.outcome, review.detail = UNAVAILABLE, str(unavailable)
        record_loop(review, loop)
        return review
    except (ManifestError, RebuildError, OSError) as failure:
        record_loop(review, loop)
        review.outcome, review.detail = REVIEW_FAILED, str(failure)
        return review
    record_loop(review, loop)
    review.outcome = LEFTOVERS if review.leftovers else FIXED if review.fixed else CLEAN
    return review


def record_loop(review: VisualReview, loop: "ReviewLoop | None") -> None:
    if loop is None:
        return
    report = loop.report()
    review.rounds_used = report["roundsUsed"]
    review.fixed = report["fixed"]
    review.given_up = report["givenUp"]
    review.text_changed = report["textChanged"]
    review.leftovers = report["leftovers"]
    review.cost, review.calls = loop.cost, loop.calls


class ReviewLoop:
    def __init__(self, deck: Deck, is_recompose_only: bool = False):
        self.deck = deck
        self.is_recompose_only = is_recompose_only
        self.manifest = deck.manifest()
        self.rounds = min(self.manifest.rounds, RECOMPOSE_ROUNDS) if is_recompose_only else self.manifest.rounds
        self.first_sections = self.manifest.sections_by_number()
        self.assessments: dict[int, Assessment] = {}
        self.fix_problems: dict[int, str] = {}
        self.changes: dict[int, str] = {}
        self.given_up: set[int] = set()
        self.refusals: dict[int, str] = {}
        self.recompose = self.manifest.slides_to_recompose()
        self.rounds_used = 0
        self.cost = 0.0
        self.calls = 0
        self.deck_sheet: script_host.Image | None = None
        self.deck_flagged: list[dict] = []
        self.deck_error = ""

    def run(self, deadline: float) -> None:
        reviewed = self.manifest.slides_numbered(self.recompose) if self.is_recompose_only else list(self.manifest.slides)
        self.record_reviews(review_slides(self.deck, self.manifest, reviewed))
        if not self.is_recompose_only:
            self.review_deck()
        while self.rounds_used < self.rounds and self.candidates() and time.monotonic() <= deadline:
            self.fix_round()

    def count(self, cost: float) -> None:
        self.cost += cost
        self.calls += 1

    def record_reviews(self, reviews: dict[int, Assessment]) -> None:
        for number, assessment in reviews.items():
            self.count_assessment(assessment)
            self.assessments[number] = assessment

    def count_assessment(self, assessment: Assessment) -> None:
        if assessment.is_asked:
            self.count(assessment.cost)

    def candidates(self) -> list[Slide]:
        return [slide for slide in self.manifest.slides if (self.assessment(slide.number).is_flagged() or slide.number in self.recompose) and slide.number not in self.given_up]

    def assessment(self, number: int) -> Assessment:
        return self.assessments.get(number) or Assessment()

    def fix_round(self) -> None:
        self.rounds_used += 1
        candidates = self.candidates()
        attempts = in_parallel(candidates, lambda slide: fix_slide(self.deck, self.manifest.fixer_instructions, slide, self.assessment(slide.number), self.sheet_for(slide.number), self.refusals.get(slide.number, "")))
        replacements = self.accepted_replacements(candidates, attempts)
        if not replacements:
            return
        previous = self.manifest
        rebuilt, applied = self.rebuilt_with(replacements)
        if not applied:
            return
        self.manifest = rebuilt
        reviews = review_slides(self.deck, rebuilt, rebuilt.slides_numbered(applied))
        if self.deck_sheet is not None:
            reviews = self.reviewed_against_deck(rebuilt, reviews)
        self.settle(previous, attempts, candidates, reviews)

    def accepted_replacements(self, candidates: list[Slide], attempts: list[Attempt]) -> dict[int, str]:
        replacements = {}
        for slide, attempt in zip(candidates, attempts):
            if attempt.is_asked:
                self.count(attempt.cost)
            self.fix_problems[slide.number] = attempt.problem
            if attempt.is_accepted():
                replacements[slide.number] = attempt.section
        return replacements

    def rebuilt_with(self, replacements: dict[int, str]) -> tuple[Manifest, dict[int, str]]:
        try:
            return self.deck.rebuild(replacements), replacements
        except RebuildError as refusal:
            if len(replacements) == 1:
                self.refuse(replacements, refusal)
                return self.manifest, {}
        applied, rebuilt = {}, self.manifest
        for number in sorted(replacements):
            single = {number: replacements[number]}
            try:
                rebuilt = self.deck.rebuild(single)
            except RebuildError as refusal:
                self.refuse(single, refusal)
                continue
            applied[number] = replacements[number]
        return rebuilt, applied

    def refuse(self, replacements: dict[int, str], refusal: Exception) -> None:
        text = str(refusal)[:MAXIMUM_REFUSAL_CHARACTERS]
        for number in replacements:
            self.fix_problems[number] = "the deck rebuild refused the rewrite: " + text
            self.refusals[number] = text

    def settle(self, previous: Manifest, attempts: list[Attempt], candidates: list[Slide], reviews: dict[int, Assessment]) -> None:
        changes = {slide.number: attempt.change for slide, attempt in zip(candidates, attempts)}
        previous_sections = previous.sections_by_number()
        restorations = {}
        for number, review in reviews.items():
            self.count_assessment(review)
            is_recomposed = number in self.recompose and is_no_worse(self.assessment(number), review)
            self.recompose.discard(number)
            if is_recomposed or is_improved(self.assessment(number), review):
                self.assessments[number] = review
                self.changes[number] = changes.get(number, "")
                continue
            restorations[number] = previous_sections[number]
            self.given_up.add(number)
        if not restorations:
            return
        try:
            self.manifest = self.deck.rebuild(restorations)
        except RebuildError as failure:
            raise RebuildError(f"restore the slides whose fix did not help: {failure}") from failure

    def review_deck(self) -> None:
        if not self.manifest.asks_about_the_deck():
            return
        try:
            review = review_deck_as_a_whole(self.deck, self.manifest)
        except (script_host.HostFailure, OSError, ValueError) as failure:
            self.deck_error = str(failure)
            return
        self.count(review.cost)
        self.deck_sheet = review.sheet
        self.deck_flagged = deck_flagged_slides(self.manifest, review.assessments)
        for flagged in self.deck_flagged:
            number = flagged["number"]
            self.assessments[number] = with_deck_assessment(self.assessment(number), review.assessments[number])

    def reviewed_against_deck(self, rebuilt: Manifest, reviews: dict[int, Assessment]) -> dict[int, Assessment]:
        try:
            review = review_deck_as_a_whole(self.deck, rebuilt)
            self.count(review.cost)
        except (script_host.HostFailure, OSError, ValueError) as failure:
            return {number: replace(assessment, error=f"the deck review after the fix failed: {failure}") for number, assessment in reviews.items()}
        return {number: with_deck_assessment(assessment, review.assessments.get(number) or Assessment()) for number, assessment in reviews.items()}

    def sheet_for(self, number: int) -> script_host.Image | None:
        return self.deck_sheet if self.manifest.has_deck_finding(self.assessment(number).findings) else None

    def report(self) -> dict:
        report = {"roundsUsed": self.rounds_used, "slides": [], "fixed": [], "givenUp": [], "leftovers": [], "textChanged": [], "deckFlagged": self.deck_flagged, "deckError": self.deck_error}
        for slide in self.manifest.slides:
            assessment = self.assessment(slide.number)
            report["slides"].append(slide_report(slide.number, assessment, self.fix_problems.get(slide.number, "")))
            if assessment.is_flagged():
                report["leftovers"].append(leftover_of(slide.number, assessment))
            if slide.number in self.given_up:
                report["givenUp"].append(slide.number)
            if slide.number in self.changes:
                report["fixed"].append({"number": slide.number, "change": self.changes[slide.number]})
            if visible_text(self.first_sections.get(slide.number, "")) != visible_text(slide.section):
                report["textChanged"].append(slide.number)
        return report


def slide_report(number: int, assessment: Assessment, fix_problem: str) -> dict:
    return {"number": number, "findings": assessment.findings, "measured": [defect.get("code", "") for defect in assessment.measured], "error": assessment.error or fix_problem}


def leftover_of(number: int, assessment: Assessment) -> dict:
    leftover = {"number": number}
    kinds = assessment.kinds()
    codes = [defect.get("code", "") for defect in assessment.measured]
    return leftover | ({"findings": kinds} if kinds else {}) | ({"measured": codes} if codes else {})


def is_improved(before: Assessment, after: Assessment) -> bool:
    if after.error or len(after.measured) > len(before.measured):
        return False
    if not before.findings:
        return len(after.measured) < len(before.measured)
    kinds = before.kinds()
    if has_new_kind(before, after):
        return False
    after_probability, before_probability = highest_probability(after.probabilities, kinds), highest_probability(before.probabilities, kinds)
    return after_probability < before_probability or len(after.measured) < len(before.measured) and after_probability <= before_probability


def is_no_worse(before: Assessment, after: Assessment) -> bool:
    return not after.error and len(after.measured) <= len(before.measured) and not has_new_kind(before, after)


def has_new_kind(before: Assessment, after: Assessment) -> bool:
    previous = set(before.kinds())
    return any(kind not in previous for kind in after.kinds())


def highest_probability(probabilities: dict, kinds: list[str]) -> float:
    return max((float(probabilities.get(kind) or 0.0) for kind in kinds), default=0.0)


def in_parallel(items: list, work: Callable) -> list:
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=MAXIMUM_PARALLEL_CALLS) as pool:
        return list(pool.map(work, items))


def review_slides(deck: Deck, manifest: Manifest, slides: list[Slide]) -> dict[int, Assessment]:
    assessments = in_parallel(slides, lambda slide: review_slide(deck, manifest, slide))
    return {slide.number: assessment for slide, assessment in zip(slides, assessments)}


def review_slide(deck: Deck, manifest: Manifest, slide: Slide) -> Assessment:
    try:
        image = fitted_render(deck, slide.image)
    except (OSError, ValueError) as failure:
        return Assessment(measured=slide.measured, error=str(failure))
    question = {QUESTION_KEY: manifest.question.asked(manifest.question.instructions)}
    try:
        response = script_host.decide(slide.state, question, [image])
    except script_host.HostFailure as failure:
        return Assessment(measured=slide.measured, error=f"decision model: {failure}", is_asked=True)
    answer = (response.get("answers") or {}).get(QUESTION_KEY)
    if not isinstance(answer, dict):
        return Assessment(measured=slide.measured, error=f"the decision model gave no answer for {QUESTION_KEY}", cost=script_host.cost_of(response), is_asked=True)
    probabilities = answer.get("probabilities") or {}
    return Assessment(probabilities=probabilities, findings=flagged_findings(manifest, manifest.question, probabilities), measured=slide.measured, cost=script_host.cost_of(response), is_asked=True)


def flagged_findings(manifest: Manifest, question: Question, probabilities: dict) -> list[dict]:
    findings = []
    for kind, meaning in question.options.items():
        probability = float(probabilities.get(kind) or 0.0)
        if kind != question.clean_option and probability >= manifest.threshold_for(kind):
            findings.append({"kind": kind, "probability": probability, "meaning": meaning})
    return sorted_by_probability(findings)


def sorted_by_probability(findings: list[dict]) -> list[dict]:
    return sorted(findings, key=lambda finding: (-finding["probability"], finding["kind"]))


def with_deck_assessment(assessment: Assessment, deck_assessment: Assessment) -> Assessment:
    return replace(assessment, probabilities={**assessment.probabilities, **deck_assessment.probabilities}, findings=sorted_by_probability([*assessment.findings, *deck_assessment.findings]))


def deck_flagged_slides(manifest: Manifest, reviews: dict[int, Assessment]) -> list[dict]:
    flagged = []
    for slide in manifest.slides:
        findings = [finding for finding in (reviews.get(slide.number) or Assessment()).findings if finding["kind"] in manifest.deck.options]
        if findings:
            flagged.append({"number": slide.number, "findings": findings})
    return flagged


def review_deck_as_a_whole(deck: Deck, manifest: Manifest) -> DeckReview:
    renders = [deck.image(slide.image) for slide in manifest.slides]
    sheet = contact_sheet(renders)
    questions = {deck_question_key(slide.number): manifest.deck.asked(f"{manifest.deck.instructions} Judge slide {slide.number}.") for slide in manifest.slides}
    response = script_host.decide({"slides": len(manifest.slides), "sheet": SHEET_DESCRIPTION}, questions, [sheet])
    answers = response.get("answers") or {}
    assessments = {}
    for slide in manifest.slides:
        answer = answers.get(deck_question_key(slide.number))
        if not isinstance(answer, dict):
            raise script_host.HostFailure(f"the decision model gave no answer for slide {slide.number} of the deck")
        probabilities = answer.get("probabilities") or {}
        assessments[slide.number] = Assessment(probabilities=probabilities, findings=flagged_findings(manifest, manifest.deck, probabilities))
    return DeckReview(sheet=sheet, assessments=assessments, cost=script_host.cost_of(response))


def deck_question_key(number: int) -> str:
    return f"{DECK_QUESTION_PREFIX}{number}"


def fix_slide(deck: Deck, instructions: str, slide: Slide, assessment: Assessment, sheet: script_host.Image | None, refusal: str) -> Attempt:
    try:
        render = deck.image(slide.image)
    except OSError as failure:
        return Attempt(problem=f"read the render: {failure}")
    images = [script_host.Image(IMAGE_MEDIA_TYPE, render), *([sheet] if sheet is not None else [])]
    try:
        response = script_host.generate(repair_prompt(slide, assessment, refusal), REPAIR_SCHEMA, system=instructions, images=images)
    except (script_host.HostFailure, script_host.HostUnavailable) as failure:
        return Attempt(problem=f"language model: {failure}", is_asked=True)
    repair = response.get("answer")
    cost = script_host.cost_of(response)
    if not isinstance(repair, dict) or not isinstance(repair.get("section"), str) or not isinstance(repair.get("change"), str):
        return Attempt(problem=f"the repair is not the requested JSON: {repair!r}", cost=cost, is_asked=True)
    return Attempt(section=repair["section"], change=repair["change"], problem=rejection_reason(slide.section, repair["section"]), cost=cost, is_asked=True)


def repair_prompt(slide: Slide, assessment: Assessment, refusal: str) -> str:
    payload = {"facts": slide.state}
    if slide.recompose:
        payload["recompose"] = True
    payload |= {"reviewerFindings": assessment.findings, "measuredDefects": list(assessment.measured), "section": slide.section}
    if refusal:
        payload["refusedLastTime"] = refusal
    return json.dumps(payload, ensure_ascii=False)


def rejection_reason(original: str, rewrite: str) -> str:
    if not is_one_section(rewrite):
        return "the rewrite is not exactly one section element"
    if rewrite.strip() == original.strip():
        return "the rewrite changes nothing"
    if content_kinds(original) != content_kinds(rewrite):
        return "the rewrite does not keep the original's tables, images and charts"
    return ""


def is_one_section(source: str) -> bool:
    trimmed = source.strip()
    opening = list(SECTION_OPENING.finditer(trimmed))
    closing = list(SECTION_CLOSING.finditer(trimmed))
    return len(opening) == 1 and len(closing) == 1 and opening[0].start() == 0 and closing[0].end() == len(trimmed)


def content_kinds(section: str) -> dict[str, int]:
    kinds = {"table": len(TABLE_PATTERN.findall(section)), "image": len(IMAGE_PATTERN.findall(section))}
    for chart in CHART_PATTERN.findall(section):
        kinds["chart:" + chart] = kinds.get("chart:" + chart, 0) + 1
    return kinds


def visible_text(section: str) -> str:
    without_tags = TAG_PATTERN.sub(" ", NOTES_PATTERN.sub(" ", section))
    return " ".join(html.unescape(without_tags).split())


def fitted_render(deck: Deck, path: str) -> script_host.Image:
    try:
        render = deck.image(path)
    except OSError as failure:
        raise OSError(f"read the render: {failure}") from failure
    try:
        return fit_image(render)
    except ValueError as failure:
        raise ValueError(f"fit the render: {failure}") from failure
