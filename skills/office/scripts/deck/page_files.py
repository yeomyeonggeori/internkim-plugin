from __future__ import annotations

import html
import pathlib
import re

from deck.outline import PAGES_DIRECTORY_NAME, Outline


PAGE_FILE_PATTERN = re.compile(r"(\d+)\.html?$", re.IGNORECASE)
SECTION_PATTERN = re.compile(r"<section\b[^>]*>.*?</section\s*>", re.IGNORECASE | re.DOTALL)
OPENING_PATTERN = re.compile(r"<section\b([^>]*)>", re.IGNORECASE)
OWNED_ATTRIBUTE_PATTERN = re.compile(r"\s(?:id|data-type|data-layout|data-page)\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
STYLE_BLOCK_PATTERN = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>)", re.IGNORECASE | re.DOTALL)
COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)
DOCUMENT_SELECTOR_PATTERN = re.compile(r"(?::root|html|body)(?![-\w])")
SECTION_SELECTOR_PATTERN = re.compile(r"section(?![-\w])", re.IGNORECASE)
HANGUL_PATTERN = re.compile(r"[가-힣]")
NESTED_AT_RULES = ("@media", "@supports")


def page_path(deck_directory: pathlib.Path, number: int) -> pathlib.Path:
    return deck_directory / PAGES_DIRECTORY_NAME / f"{number:02d}.html"


def page_number(path: pathlib.Path) -> int | None:
    match = PAGE_FILE_PATTERN.fullmatch(path.name)
    return int(match.group(1)) if match and path.parent.name == PAGES_DIRECTORY_NAME else None


def page_identifier(number: int) -> str:
    return f"page-{number:02d}"


def lone_section(page_text: str) -> str | None:
    sections = SECTION_PATTERN.findall(page_text)
    if len(sections) != 1 or SECTION_PATTERN.sub("", page_text).strip():
        return None
    return sections[0]


def matching_brace(text: str, opening: int) -> int:
    depth = 0
    for position in range(opening, len(text)):
        if text[position] == "{":
            depth += 1
        elif text[position] == "}":
            depth -= 1
            if depth == 0:
                return position
    return len(text) - 1


def scoped_stylesheet(text: str, scope: str) -> str:
    text = COMMENT_PATTERN.sub("", text)
    pieces, position = [], 0
    while position < len(text):
        opening = text.find("{", position)
        if opening < 0:
            pieces.append(text[position:])
            break
        closing = matching_brace(text, opening)
        prelude, body = text[position:opening], text[opening + 1:closing]
        pieces.append(scoped_rule(prelude, body, scope))
        position = closing + 1
    return "".join(pieces)


def scoped_rule(prelude: str, body: str, scope: str) -> str:
    stripped = prelude.strip()
    if stripped.startswith(NESTED_AT_RULES):
        return f"{prelude}{{{scoped_stylesheet(body, scope)}}}"
    if stripped.startswith("@"):
        return f"{prelude}{{{body}}}"
    return f"{', '.join(scoped_selector(selector, scope) for selector in top_level_parts(stripped))} {{{body}}}"


def top_level_parts(selectors: str) -> list[str]:
    parts, depth, start = [], 0, 0
    for position, character in enumerate(selectors):
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(selectors[start:position])
            start = position + 1
    parts.append(selectors[start:])
    return [part.strip() for part in parts if part.strip()]


def scoped_selector(selector: str, scope: str) -> str:
    document = DOCUMENT_SELECTOR_PATTERN.match(selector)
    if document:
        rest = selector[document.end():].strip()
        return f"section#{scope} {rest}".strip()
    section = SECTION_SELECTOR_PATTERN.match(selector)
    if section:
        return f"section#{scope}{selector[section.end():]}"
    return f"#{scope} {selector}"


def scoped_section(section: str, number: int, page_type: str, layout: str) -> str:
    scope = page_identifier(number)
    opening = OPENING_PATTERN.match(section)
    attributes = OWNED_ATTRIBUTE_PATTERN.sub("", opening.group(1))
    owned = f' id="{scope}" data-page="{number}" data-type="{html.escape(page_type)}" data-layout="{html.escape(layout)}"'
    inner = STYLE_BLOCK_PATTERN.sub(lambda block: block.group(1) + scoped_stylesheet(block.group(2), scope) + block.group(3), section[opening.end():])
    return f"<section{owned}{attributes}>{inner}"


def deck_language(outline: Outline) -> str:
    texts = [outline.core_hook, *(text for page in outline.pages for text in (page.title, *page.brief))]
    return "ko" if any(HANGUL_PATTERN.search(text) for text in texts) else "en"


def assembled_deck(outline: Outline, sections: dict[int, str]) -> str:
    body = "\n".join(scoped_section(section, number, outline.pages[number - 1].type, outline.pages[number - 1].layout) for number, section in sorted(sections.items()))
    title = html.escape(outline.pages[0].title if outline.pages else "")
    return f'<!doctype html>\n<html lang="{deck_language(outline)}">\n<head>\n<meta charset="utf-8">\n<title>{title}</title>\n</head>\n<body>\n{body}\n</body>\n</html>\n'
