from __future__ import annotations

import re

from deck_definitions import (
    LAYOUT_RENDER_SOURCE,
    ABSOLUTE_FOOTER,
    BARE_LIST,
    DESIGN_WARNING_WEIGHTS,
    GHOST_CARD,
    MISSING_SLIDE_ROLE,
    RAW_STRUCTURE_PATTERN,
    RAW_TABLE,
    REPEATED_COMPOSITION,
    SIDE_STRIPE,
    TOPIC_TITLE,
    UNRELIABLE_VISUAL_EVIDENCE,
    WEAK_VISUAL_IDENTITY,
)
from office_result import Issue


STRUCTURE_DOMINANCE_RATIO = 0.55
CLAIM_TITLE_WORD_MINIMUM = 5
DESIGN_DOCUMENT_BODY_MINIMUM_CHARACTERS = 80
KOREAN_SENTENCE_ENDINGS = ("다", "요", "까", "죠", "오")
LABEL_ONLY_SLIDE_ROLES = {"title", "cover", "divider", "section", "agenda", "quote"}


def slide_design_warnings(structure: dict[str, object]) -> list[Issue]:
    warnings = []
    if not structure["hasSlideRole"]:
        warnings.append(MISSING_SLIDE_ROLE.issue("slide lacks data-slide-role, so its job is not explicit"))
    if has_generic_topic_title(structure):
        warnings.append(TOPIC_TITLE.issue("title reads as a topic label rather than a claim with a conclusion"))
    if structure["kitLayout"]:
        return warnings
    if slide_is_table_dominated(structure):
        warnings.append(RAW_TABLE.issue("a raw table is the slide's primary composition"))
    if slide_is_list_dominated(structure):
        warnings.append(BARE_LIST.issue("a bare list is the slide's primary composition"))
    return warnings


def slide_is_table_dominated(structure: dict[str, object]) -> bool:
    return bool(structure["hasTable"]) and float(structure["tableTextRatio"]) >= STRUCTURE_DOMINANCE_RATIO


def slide_is_list_dominated(structure: dict[str, object]) -> bool:
    return bool(structure["hasList"]) and float(structure["listTextRatio"]) >= STRUCTURE_DOMINANCE_RATIO


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
    if not source_has_visual_identity(source_context):
        warnings.append(weak_visual_identity_warning(source_context))
    if int(source_context["missingSlideRoleCount"]) > 0:
        warnings.append(MISSING_SLIDE_ROLE.deck_issue("one or more slide sections lack data-slide-role"))
    if render_source != LAYOUT_RENDER_SOURCE:
        warnings.append(UNRELIABLE_VISUAL_EVIDENCE.deck_issue("review images were not drawn from the deck's layout"))
    return warnings + source_pattern_warnings(source_context) + composition_warnings(slides)


def weak_visual_identity_warning(source_context: dict[str, object]) -> Issue:
    missing_parts = []
    if not source_context["hasVisualSystemAttribute"]:
        missing_parts.append("a data-visual-system attribute in slides.html")
    if int(source_context["designDocumentBodyCharacterCount"]) < DESIGN_DOCUMENT_BODY_MINIMUM_CHARACTERS:
        missing_parts.append("a DESIGN.md body that describes the visual system")
    return WEAK_VISUAL_IDENTITY.deck_issue("deck lacks " + " and ".join(missing_parts))


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
    warnings = []
    repeated_composition_count = repeated_composition_slide_count(slides)
    if repeated_composition_count >= 3:
        warnings.append(REPEATED_COMPOSITION.deck_issue(
            f"{repeated_composition_count} slides share the same composition classes; vary slide composition"
        ))
    if sum(1 for slide in slides if slide_has_dominant_raw_structure(slide)) >= 2:
        warnings.append(RAW_STRUCTURE_PATTERN.deck_issue("multiple slides use a raw table or bare list as the primary composition"))
    return warnings


def source_has_visual_identity(source_context: dict[str, object]) -> bool:
    if source_context["usesDeckKit"]:
        return True
    return (
        bool(source_context["hasVisualSystemAttribute"])
        and int(source_context["designDocumentBodyCharacterCount"]) >= DESIGN_DOCUMENT_BODY_MINIMUM_CHARACTERS
    )


def slide_has_dominant_raw_structure(slide: dict[str, object]) -> bool:
    structure = slide["structure"]
    if structure["kitLayout"]:
        return False
    return slide_is_table_dominated(structure) or slide_is_list_dominated(structure)


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


def annotate_design_revision_need(slides: list[dict[str, object]]) -> None:
    for slide in slides:
        slide["needsDesignRevision"] = any(is_design_warning(warning) for warning in slide["warnings"])


def unique_design_warnings(slides: list[dict[str, object]]) -> list[Issue]:
    warnings = []
    for slide in slides:
        for warning in slide["warnings"]:
            if is_design_warning(warning) and all(existing.message != warning.message for existing in warnings):
                warnings.append(warning)
    return warnings


def calculate_visual_quality_score(design_warnings: list[Issue]) -> int:
    score = 100 - sum(DESIGN_WARNING_WEIGHTS[warning.kind.code] for warning in design_warnings)
    return max(0, min(100, score))


def is_design_warning(warning: Issue) -> bool:
    return warning.kind.code in DESIGN_WARNING_WEIGHTS
