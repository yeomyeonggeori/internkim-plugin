import datetime
import re

from design_warnings import LABEL_ONLY_SLIDE_ROLES, append_deck_warning
from slide_source import split_slide_sources


HANGUL_PATTERN = re.compile(r"[가-힣]")
LATIN_LETTER_PATTERN = re.compile(r"[A-Za-z]")
EMOJI_PATTERN = re.compile("[\U0001F000-\U0001FAFF✅❌❎❗❓⭐⚠⌚⏰️]")
SPEAKER_NOTES_PATTERN = re.compile(
    r"<aside\b[^>]*(?:class=[\"'][^\"']*notes[^\"']*[\"']|role=[\"']note[\"'])|data-speaker-notes",
    flags=re.IGNORECASE,
)
REQUIRED_TEXT_PREVIEW_LINE_COUNT = 4


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
            "languageMismatchWarning: slide " + ", ".join(mismatched_indexes)
            + " titles are Latin-only while the deck text is Korean; write slide titles in the request language",
        )


def deck_text_is_korean(text: str) -> bool:
    hangul_count = len(HANGUL_PATTERN.findall(text))
    latin_count = len(LATIN_LETTER_PATTERN.findall(text))
    return hangul_count >= 40 and hangul_count * 3 >= latin_count


def title_is_latin_only(title: str) -> bool:
    return len(LATIN_LETTER_PATTERN.findall(title)) >= 4 and not HANGUL_PATTERN.search(title)


def apply_unsourced_current_date_warning(
    slides: list[dict[str, object]],
    slide_texts: list[dict[str, object]],
    required_text_ledger: str,
) -> None:
    today = datetime.date.today()
    date_pattern = current_date_pattern(today)
    if date_pattern.search(required_text_ledger):
        return
    dated_indexes = [
        str(slide_text["index"])
        for slide_text in slide_texts
        if date_pattern.search(str(slide_text["expectedVisibleText"]))
    ]
    if dated_indexes:
        append_deck_warning(
            slides,
            "unsourcedCurrentDateWarning: slide " + ", ".join(dated_indexes)
            + f" shows today's date {today.isoformat()}, which is not in required-visible-text.txt; only show dates from the source material",
        )


def apply_missing_required_text_warning(
    slides: list[dict[str, object]],
    slide_texts: list[dict[str, object]],
    required_text_ledger: str,
) -> None:
    ledger_lines = [line.strip() for line in required_text_ledger.splitlines() if line.strip()]
    if not ledger_lines:
        return
    deck_text = normalize_for_coverage("\n".join(str(slide_text["expectedVisibleText"]) for slide_text in slide_texts))
    spaceless_deck_text = deck_text.replace(" ", "")
    missing_lines = [
        line
        for line in ledger_lines
        if normalize_for_coverage(line) not in deck_text
        and normalize_for_coverage(line).replace(" ", "") not in spaceless_deck_text
    ]
    if missing_lines:
        preview = "; ".join(missing_lines[:REQUIRED_TEXT_PREVIEW_LINE_COUNT]) + (" ..." if len(missing_lines) > REQUIRED_TEXT_PREVIEW_LINE_COUNT else "")
        append_deck_warning(
            slides,
            f"missingRequiredTextWarning: {len(missing_lines)} of {len(ledger_lines)} required-visible-text.txt lines are not visible in the deck: {preview}",
        )


def normalize_for_coverage(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


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
            "missingSpeakerNotesWarning: slide " + ", ".join(missing_indexes)
            + " lacks an <aside class=\"notes\"> speaker script the presenter can read aloud",
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
            "emojiIconWarning: slide " + ", ".join(emoji_indexes)
            + " uses emoji glyphs; use text labels, CSS markers, or inline SVG instead",
        )


def current_date_pattern(today: datetime.date) -> re.Pattern[str]:
    separator = r"\s*[.\-/년월]\s*"
    return re.compile(rf"(?<!\d){today.year}{separator}0?{today.month}{separator}0?{today.day}(?!\d)")
