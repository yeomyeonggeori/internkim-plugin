from __future__ import annotations

import re

from deck.deck_definitions import LAYOUT_RENDER_SOURCE, TOPIC_TITLE, UNRELIABLE_VISUAL_EVIDENCE
from core.office_result import Issue


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


def apply_render_source_warning(slides: list[dict[str, object]], render_source: str) -> None:
    if render_source != LAYOUT_RENDER_SOURCE:
        append_deck_warning(slides, UNRELIABLE_VISUAL_EVIDENCE.deck_issue("review images were not drawn from the deck's layout"))


def append_deck_warning(slides: list[dict[str, object]], warning: Issue) -> None:
    for slide in slides:
        if all(existing.message != warning.message for existing in slide["warnings"]):
            slide["warnings"].append(warning)
