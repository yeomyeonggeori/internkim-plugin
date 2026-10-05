from __future__ import annotations

import html
import re

from deck.slide_source import SPEAKER_NOTES_BLOCK_PATTERN, remove_invisible_markup, split_slide_sources


PREVIEW_CHARACTER_LIMIT = 180


def read_slide_texts(source_text: str, slide_count: int) -> list[dict[str, object]]:
    slide_sources = split_slide_sources(source_text)
    return [
        read_slide_text(index + 1, slide_sources[index] if index < len(slide_sources) else "")
        for index in range(slide_count)
    ]


def read_slide_text(index: int, slide_source: str) -> dict[str, object]:
    visible_text = visible_slide_text(slide_source) if slide_source else ""
    return {
        "index": index,
        "expectedVisibleText": visible_text,
        "textPreview": preview_text(visible_text),
    }


def visible_slide_text(slide_source: str) -> str:
    text = remove_invisible_markup(slide_source)
    text = convert_html_markup_to_text(text)
    return normalize_visible_text(html.unescape(text))


def extract_notes(slide_source: str) -> str:
    notes = re.findall(SPEAKER_NOTES_BLOCK_PATTERN, slide_source, flags=re.IGNORECASE | re.DOTALL)
    return "\n".join(text for text in map(visible_slide_text, notes) if text)


def convert_html_markup_to_text(text: str) -> str:
    return re.sub(r"<[^>]+>", "\n", text)


def normalize_visible_text(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def preview_text(text: str) -> str:
    compact_text = re.sub(r"\s+", " ", text).strip()
    if len(compact_text) <= PREVIEW_CHARACTER_LIMIT:
        return compact_text
    return compact_text[:PREVIEW_CHARACTER_LIMIT - 3].rstrip() + "..."
