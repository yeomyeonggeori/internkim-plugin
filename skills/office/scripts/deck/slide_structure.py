from __future__ import annotations

import html
import re

from deck.slide_source import normalize_structure_text, remove_invisible_markup, slide_layout, slide_role, slide_title, split_slide_sources


PREVIEW_CHARACTER_LIMIT = 180


def read_slide_texts(source_text: str, slide_count: int) -> list[dict[str, object]]:
    slide_sources = split_slide_sources(source_text)
    return [
        read_slide_text(index + 1, slide_sources[index] if index < len(slide_sources) else "")
        for index in range(slide_count)
    ]


def read_slide_text(index: int, slide_source: str) -> dict[str, object]:
    visible_text = visible_slide_text(slide_source) if slide_source else ""
    lines = [line for line in visible_text.splitlines() if line.strip()]
    return {
        "index": index,
        "expectedVisibleText": visible_text,
        "textCharacterCount": len(visible_text),
        "textLineCount": len(lines),
        "textPreview": preview_text(visible_text),
        "structure": inspect_slide_structure(slide_source),
    }


def visible_slide_text(slide_source: str) -> str:
    text = remove_invisible_markup(slide_source)
    text = convert_html_markup_to_text(text)
    return normalize_visible_text(html.unescape(text))


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


def inspect_slide_structure(slide_source: str) -> dict[str, object]:
    class_names = extract_class_names(slide_source)
    title = slide_title(slide_source)
    declared_role = slide_role(slide_source)
    return {
        "title": title,
        "normalizedTitle": normalize_structure_text(title),
        "slideRole": declared_role,
        "kitLayout": slide_layout(slide_source),
        "classNames": class_names,
    }


def extract_class_names(slide_source: str) -> list[str]:
    names = []
    for match in re.finditer(r"\bclass\s*=\s*([\"'])(.*?)\1", slide_source, flags=re.IGNORECASE | re.DOTALL):
        names.extend(value.strip().lower() for value in re.split(r"\s+", match.group(2)) if value.strip())
    return names
