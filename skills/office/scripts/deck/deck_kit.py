from __future__ import annotations

import functools
import json
import pathlib
import re


KIT_PATH = pathlib.Path(__file__).resolve().parents[2] / "assets" / "deck-kit"
KIT_STYLESHEET_PATH = KIT_PATH / "deck-kit.css"
KIT_SCRIPT_PATH = KIT_PATH / "deck-kit.js"
ICONS_PATH = KIT_PATH / "icons"
KIT_MARKER = "data-internkim-deck-kit"
DEFAULT_THEME = "editorial"
KIT_BLOCK_PATTERNS = (
    rf"\s*<style\b(?=[^>]*\b{KIT_MARKER}\b)[^>]*>.*?</style>\s*",
    rf"\s*<script\b(?=[^>]*\b{KIT_MARKER}\b)[^>]*>.*?</script>\s*",
)
LAYOUT_ATTRIBUTE_PATTERN = re.compile(r"<section\b[^>]*\bdata-layout\s*=", re.IGNORECASE)
THEME_ATTRIBUTE_PATTERN = re.compile(r"<body\b[^>]*\bdata-theme\s*=", re.IGNORECASE)
THEME_BLOCK_PATTERN = re.compile(r"((?::root,\s*)?\[data-theme=\"([a-z]+)\"\])\s*\{([^}]*)\}")
COLOR_TOKEN_PATTERN = re.compile(r"--([a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{3,8})\s*;")
CHART_RENDERERS_PATTERN = re.compile(r"const chartRenderers = \{(.*?)\n  \};", re.DOTALL)
CHART_TYPE_PATTERN = re.compile(r"^\s{4}([a-z0-9]+):", re.MULTILINE)
ICON_USE_PATTERN = re.compile(r"\bdata-icon\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
SVG_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
SVG_ROOT_PATTERN = re.compile(r"<svg\b[^>]*>")
SVG_SIZING_PATTERN = re.compile(r'\s(?:class|width|height)="[^"]*"')
SPACE_BETWEEN_TAGS_PATTERN = re.compile(r"\s*(/?>)\s*")
STRING_LIST_PATTERN = r"const {name} = (\[[^\]]*\]);"
SLIDE_SIZE_PATTERN = re.compile(r"section\[data-layout\] \{[^}]*?\bwidth: (\d+)px;\s*height: (\d+)px;")


def uses_deck_kit(source_text: str) -> bool:
    return bool(LAYOUT_ATTRIBUTE_PATTERN.search(source_text) or THEME_ATTRIBUTE_PATTERN.search(source_text))


def strip_deck_kit(source_text: str) -> str:
    for block_pattern in KIT_BLOCK_PATTERNS:
        source_text = re.sub(block_pattern, "\n", source_text, flags=re.IGNORECASE | re.DOTALL)
    return source_text


def inject_deck_kit(source_text: str) -> str:
    source_text = strip_deck_kit(source_text)
    if not uses_deck_kit(source_text):
        return source_text
    kit_markup = (
        f"<style {KIT_MARKER}>\n{KIT_STYLESHEET_PATH.read_text(encoding='utf-8')}</style>\n"
        f"{icon_script(source_text)}"
        f"<script {KIT_MARKER}>\n{KIT_SCRIPT_PATH.read_text(encoding='utf-8')}</script>\n"
    )
    head_match = re.search(r"<head\b[^>]*>", source_text, flags=re.IGNORECASE)
    if head_match:
        return source_text[:head_match.end()] + "\n" + kit_markup + source_text[head_match.end():]
    return kit_markup + source_text


@functools.lru_cache(maxsize=None)
def kit_stylesheet() -> str:
    return KIT_STYLESHEET_PATH.read_text(encoding="utf-8")


def slide_size() -> tuple[int, int]:
    width, height = SLIDE_SIZE_PATTERN.search(kit_stylesheet()).groups()
    return int(width), int(height)


def kit_length(token: str) -> int:
    return int(re.search(rf"--{token}:\s*(\d+)px;", kit_stylesheet()).group(1))


@functools.lru_cache(maxsize=None)
def kit_script() -> str:
    return KIT_SCRIPT_PATH.read_text(encoding="utf-8")


def kit_number(name: str) -> int:
    return int(re.search(rf"const {name} = (\d+);", kit_script()).group(1))


def theme_palettes() -> dict[str, dict[str, str]]:
    palettes = {}
    for match in THEME_BLOCK_PATTERN.finditer(kit_stylesheet()):
        palettes[match.group(2)] = {name: value.upper() for name, value in COLOR_TOKEN_PATTERN.findall(match.group(3))}
    return palettes


def theme_names() -> tuple[str, ...]:
    return tuple(theme_palettes())


def chart_types() -> tuple[str, ...]:
    renderers = CHART_RENDERERS_PATTERN.search(kit_script())
    return tuple(CHART_TYPE_PATTERN.findall(renderers.group(1))) if renderers else ()


def kit_names(name: str) -> tuple[str, ...]:
    return tuple(json.loads(re.search(STRING_LIST_PATTERN.format(name=name), kit_script()).group(1)))


@functools.lru_cache(maxsize=None)
def icon_names() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in ICONS_PATH.glob("*.svg")))


def icon_markup(name: str) -> str:
    text = SVG_COMMENT_PATTERN.sub("", (ICONS_PATH / f"{name}.svg").read_text(encoding="utf-8"))
    text = SVG_ROOT_PATTERN.sub(lambda root: SVG_SIZING_PATTERN.sub("", root.group(0)), text, count=1)
    return SPACE_BETWEEN_TAGS_PATTERN.sub(r"\1", " ".join(text.split()))


def used_icon_names(source_text: str) -> tuple[str, ...]:
    written = {name.strip() for name in ICON_USE_PATTERN.findall(source_text)}
    return tuple(name for name in icon_names() if name in written)


def icon_script(source_text: str) -> str:
    icons = {name: icon_markup(name) for name in used_icon_names(source_text)}
    if not icons:
        return ""
    return f"<script {KIT_MARKER}>\nwindow.deckKitIcons = {json.dumps(icons, ensure_ascii=False)};\n</script>\n"
