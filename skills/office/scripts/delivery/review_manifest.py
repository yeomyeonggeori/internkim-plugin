from __future__ import annotations

from dataclasses import dataclass, field
import json

from host import script_host


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Question:
    instructions: str = ""
    options: dict = field(default_factory=dict)
    clean_option: str = ""

    def is_defect(self, option: str) -> bool:
        return option in self.options and option != self.clean_option

    def asked(self, instructions: str) -> dict:
        return script_host.choice_question(instructions, self.options)


@dataclass(frozen=True)
class Slide:
    number: int
    image: str = ""
    state: dict = field(default_factory=dict)
    section: str = ""
    source: str = ""
    recompose: bool = False
    measured: tuple = ()


@dataclass(frozen=True)
class Manifest:
    question: Question
    deck: Question
    threshold: float
    pattern_thresholds: dict
    rounds: int
    fixer_instructions: str
    source: str
    slides: tuple

    def threshold_for(self, option: str) -> float:
        return float(self.pattern_thresholds.get(option, self.threshold))

    def asks_about_the_deck(self) -> bool:
        return bool(self.deck.options)

    def is_defect_option(self, option: str) -> bool:
        return self.question.is_defect(option) or self.deck.is_defect(option)

    def sections_by_number(self) -> dict[int, str]:
        return {slide.number: slide.section for slide in self.slides}

    def slides_numbered(self, numbers) -> list[Slide]:
        return [slide for slide in self.slides if slide.number in numbers]

    def page_source(self, number: int) -> str:
        return next((slide.source for slide in self.slides if slide.number == number), "")

    def slides_to_recompose(self) -> set[int]:
        return {slide.number for slide in self.slides if slide.recompose}

    def has_deck_finding(self, findings: list[dict]) -> bool:
        return any(finding["kind"] in self.deck.options for finding in findings)


def parse_manifest(content: str | bytes) -> Manifest:
    try:
        document = json.loads(content)
    except json.JSONDecodeError as error:
        raise ManifestError(f"visual review manifest is not valid JSON: {error}") from error
    manifest = manifest_of(document)
    validate(manifest)
    return manifest


def question_of(document: object) -> Question:
    document = document if isinstance(document, dict) else {}
    return Question(instructions=str(document.get("instructions") or ""), options=dict(document.get("options") or {}), clean_option=str(document.get("cleanOption") or ""))


def slide_of(document: dict) -> Slide:
    return Slide(
        number=int(document.get("number") or 0),
        image=str(document.get("image") or ""),
        state=dict(document.get("state") or {}),
        section=str(document.get("section") or ""),
        source=str(document.get("source") or ""),
        recompose=document.get("recompose") is True,
        measured=tuple(dict(defect) for defect in document.get("measured") or ()),
    )


def manifest_of(document: dict) -> Manifest:
    return Manifest(
        question=question_of(document.get("question")),
        deck=question_of(document.get("deck")),
        threshold=float(document.get("threshold") or 0),
        pattern_thresholds={str(name): float(value) for name, value in (document.get("patternThresholds") or {}).items()},
        rounds=int(document.get("rounds") or 0),
        fixer_instructions=str((document.get("fixer") or {}).get("instructions") or ""),
        source=str(document.get("source") or ""),
        slides=tuple(slide_of(slide) for slide in document.get("slides") or () if isinstance(slide, dict)),
    )


def validate(manifest: Manifest) -> None:
    if manifest.question.clean_option not in manifest.question.options:
        raise ManifestError(f"visual review manifest: cleanOption {manifest.question.clean_option!r} is not one of the options")
    if not 0 < manifest.threshold < 1:
        raise ManifestError(f"visual review manifest: threshold {manifest.threshold} is not between 0 and 1")
    validate_deck_question(manifest)
    for option, threshold in manifest.pattern_thresholds.items():
        if not manifest.is_defect_option(option):
            raise ManifestError(f"visual review manifest: patternThresholds names {option!r}, which is not a defect option")
        if not 0 < threshold < 1:
            raise ManifestError(f"visual review manifest: patternThresholds[{option!r}] {threshold} is not between 0 and 1")
    if manifest.rounds < 0:
        raise ManifestError(f"visual review manifest: rounds {manifest.rounds} is negative")


def validate_deck_question(manifest: Manifest) -> None:
    if not manifest.asks_about_the_deck():
        return
    if manifest.deck.clean_option not in manifest.deck.options:
        raise ManifestError(f"visual review manifest: the deck question's cleanOption {manifest.deck.clean_option!r} is not one of its options")
    for option in manifest.deck.options:
        if option != manifest.deck.clean_option and manifest.question.is_defect(option):
            raise ManifestError(f"visual review manifest: option {option!r} is a defect of both the slide question and the deck question")

