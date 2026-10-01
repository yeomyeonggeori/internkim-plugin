from __future__ import annotations

import re

from deck_definitions import (
    LAYOUT_RENDER_SOURCE,
    ABSOLUTE_FOOTER,
    GHOST_CARD,
    REPEATED_COMPOSITION,
    SIDE_STRIPE,
    TOPIC_TITLE,
    UNRELIABLE_VISUAL_EVIDENCE,
)
from office_result import Issue


CLAIM_TITLE_WORD_MINIMUM = 5
KOREAN_SENTENCE_ENDINGS = ("다", "요", "까", "죠", "오")
LABEL_ONLY_SLIDE_ROLES = {"title", "cover", "divider", "section", "agenda", "quote"}


def slide_design_warnings(structure: dict[str, object]) -> list[Issue]:
    if has_generic_topic_title(structure):
        return [TOPIC_TITLE.issue("title reads as a topic label rather than a claim with a conclusion")]
    return []


def has_generic_topic_title(structure: dict[str, object]) -> bool:
    if str(structure["slideRole"]) in LABEL_ONLY_SLIDE_ROLES:
        return False
    return title_reads_as_topic_label(str(structure["title"]))


def title_reads_as_topic_label(title: str) -> bool:
    stripped = strip_parenthetical(title).strip()
    if not stripped:
        return False
    if stripped[-1] in ".!?…":
        return False
    if stripped.rstrip("\"'」』 ").endswith(KOREAN_SENTENCE_ENDINGS):
        return False
    return len(stripped.split()) < CLAIM_TITLE_WORD_MINIMUM


def strip_parenthetical(title: str) -> str:
    return re.sub(r"\s*[(（][^)）]*[)）]\s*", " ", title).strip()


def apply_deck_design_warnings(slides: list[dict[str, object]], source_context: dict[str, object], render_source: str) -> None:
    for warning in deck_design_warnings(slides, source_context, render_source):
        append_deck_warning(slides, warning)


def deck_design_warnings(slides: list[dict[str, object]], source_context: dict[str, object], render_source: str) -> list[Issue]:
    warnings = []
    if render_source != LAYOUT_RENDER_SOURCE:
        warnings.append(UNRELIABLE_VISUAL_EVIDENCE.deck_issue("review images were not drawn from the deck's layout"))
    if source_context["usesDeckKit"]:
        return warnings
    return warnings + source_pattern_warnings(source_context) + composition_warnings(slides)


def source_pattern_warnings(source_context: dict[str, object]) -> list[Issue]:
    warnings = []
    if source_context["hasSideStripePattern"]:
        warnings.append(SIDE_STRIPE.deck_issue("thick left or right border accents are doing the visual-identity work"))
    if source_context["hasGhostCardPattern"]:
        warnings.append(GHOST_CARD.deck_issue("thin-bordered boxes with soft shadows read as a default template surface"))
    if int(source_context["absoluteTextFooterSlideCount"]) >= 2:
        warnings.append(ABSOLUTE_FOOTER.deck_issue(
            "an absolutely positioned bottom strip carries text on multiple slides and can overlap the body; make header, body, and footer sibling flow children"
        ))
    return warnings


def composition_warnings(slides: list[dict[str, object]]) -> list[Issue]:
    repeated_composition_count = repeated_composition_slide_count(slides)
    if repeated_composition_count < 3:
        return []
    return [REPEATED_COMPOSITION.deck_issue(f"{repeated_composition_count} slides share the same composition classes; vary slide composition")]


def repeated_composition_slide_count(slides: list[dict[str, object]]) -> int:
    if len(slides) < 3:
        return 0
    signatures = [frozenset(slide["structure"]["classNames"]) for slide in slides]
    universal_classes = frozenset.intersection(*signatures)
    distinctive_signatures = [signature - universal_classes for signature in signatures]
    counts: dict[frozenset, int] = {}
    for signature in distinctive_signatures:
        if signature:
            counts[signature] = counts.get(signature, 0) + 1
    return max(counts.values(), default=0)


def append_deck_warning(slides: list[dict[str, object]], warning: Issue) -> None:
    for slide in slides:
        if all(existing.message != warning.message for existing in slide["warnings"]):
            slide["warnings"].append(warning)
