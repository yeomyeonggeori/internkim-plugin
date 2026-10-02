from __future__ import annotations

import datetime
import re

from deck.deck_definitions import EMOJI_ICON, LANGUAGE_MISMATCH, MISSING_SPEAKER_NOTES, UNSOURCED_CURRENT_DATE
from deck.review.design_warnings import LABEL_ONLY_SLIDE_ROLES, append_deck_warning
from deck.slide_source import SPEAKER_NOTES_CLASS_ATTRIBUTE_PATTERN, split_slide_sources
from core.text_script import hangul_count, has_hangul


LATIN_LETTER_PATTERN = re.compile(r"[A-Za-z]")
EMOJI_PATTERN = re.compile("[\U0001F000-\U0001FAFF✅❌❎❗❓⭐⚠⌚⏰️]")
SPEAKER_NOTES_PATTERN = re.compile(
    rf"<aside\b[^>]*(?:{SPEAKER_NOTES_CLASS_ATTRIBUTE_PATTERN}|role=[\"']note[\"'])|data-speaker-notes",
    flags=re.IGNORECASE,
)


def apply_language_mismatch_warning(slides: list[dict[str, object]], slide_texts: list[dict[str, object]]) -> None:
    deck_text = "\n".join(str(slide_text["expectedVisibleText"]) for slide_text in slide_texts)
    if not deck_text_is_korean(deck_text):
        return
    mismatched_indexes = [
        str(slide_text["index"])
        for slide_text in slide_texts
        if str(slide_text["structure"]["slideRole"]) not in LABEL_ONLY_SLIDE_ROLES
        and title_is_latin_only(str(slide_text["structure"]["title"]))
    ]
    if mismatched_indexes:
        append_deck_warning(
            slides,
            LANGUAGE_MISMATCH.deck_issue(
                "slide " + ", ".join(mismatched_indexes)
                + " titles are Latin-only while the deck text is Korean; write slide titles in the request language"
            ),
        )


def deck_text_is_korean(text: str) -> bool:
    hangul_total = hangul_count(text)
    latin_count = len(LATIN_LETTER_PATTERN.findall(text))
    return hangul_total >= 40 and hangul_total * 3 >= latin_count


def title_is_latin_only(title: str) -> bool:
    return len(LATIN_LETTER_PATTERN.findall(title)) >= 4 and not has_hangul(title)


def apply_unsourced_current_date_warning(
    slides: list[dict[str, object]],
    slide_texts: list[dict[str, object]],
    required_texts: tuple[str, ...],
) -> None:
    today = datetime.date.today()
    date_pattern = current_date_pattern(today)
    if any(date_pattern.search(text) for text in required_texts):
        return
    dated_indexes = [
        str(slide_text["index"])
        for slide_text in slide_texts
        if date_pattern.search(str(slide_text["expectedVisibleText"]))
    ]
    if dated_indexes:
        append_deck_warning(
            slides,
            UNSOURCED_CURRENT_DATE.deck_issue(
                "slide " + ", ".join(dated_indexes)
                + f" shows today's date {today.isoformat()}, which no --required-text names; only show dates from the source material"
            ),
        )


def apply_missing_speaker_notes_warning(slides: list[dict[str, object]], source_text: str) -> None:
    slide_sources = split_slide_sources(source_text)
    if not slide_sources:
        return
    missing_indexes = [
        str(index)
        for index, slide_source in enumerate(slide_sources, start=1)
        if not SPEAKER_NOTES_PATTERN.search(slide_source)
    ]
    if missing_indexes:
        append_deck_warning(
            slides,
            MISSING_SPEAKER_NOTES.deck_issue(
                "slide " + ", ".join(missing_indexes)
                + " lacks an <aside class=\"notes\"> speaker script the presenter can read aloud"
            ),
        )


def apply_emoji_icon_warning(slides: list[dict[str, object]], slide_texts: list[dict[str, object]]) -> None:
    emoji_indexes = [
        str(slide_text["index"])
        for slide_text in slide_texts
        if EMOJI_PATTERN.search(str(slide_text["expectedVisibleText"]))
    ]
    if emoji_indexes:
        append_deck_warning(
            slides,
            EMOJI_ICON.deck_issue(
                "slide " + ", ".join(emoji_indexes)
                + " uses emoji glyphs"
            ),
        )


def current_date_pattern(today: datetime.date) -> re.Pattern[str]:
    separator = r"\s*[.\-/년월]\s*"
    return re.compile(rf"(?<!\d){today.year}{separator}0?{today.month}{separator}0?{today.day}(?!\d)")
