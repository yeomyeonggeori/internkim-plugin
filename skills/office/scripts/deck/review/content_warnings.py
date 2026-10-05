from __future__ import annotations

import re

from core.office_result import Issue
from deck.deck_definitions import EMOJI_ICON, MISSING_SPEAKER_NOTES
from deck.slide_source import SPEAKER_NOTES_CLASS_ATTRIBUTE_PATTERN


EMOJI_PATTERN = re.compile("[\U0001F000-\U0001FAFF✅❌❎❗❓⭐⚠⌚⏰️]")
SPEAKER_NOTES_PATTERN = re.compile(rf"<aside\b[^>]*{SPEAKER_NOTES_CLASS_ATTRIBUTE_PATTERN}", flags=re.IGNORECASE)


def content_warnings(slide_sources: list[str], slide_texts: list[dict[str, object]]) -> list[Issue]:
    emoji = [str(text["index"]) for text in slide_texts if EMOJI_PATTERN.search(str(text["expectedVisibleText"]))]
    silent = [str(number) for number, source in enumerate(slide_sources, start=1) if not SPEAKER_NOTES_PATTERN.search(source)]
    warnings = [EMOJI_ICON.issue(f"slide {', '.join(emoji)} uses emoji glyphs", "deck")] if emoji else []
    return warnings + ([MISSING_SPEAKER_NOTES.issue(f"slide {', '.join(silent)} has no <aside class=\"notes\"> the presenter can read aloud", "deck")] if silent else [])
