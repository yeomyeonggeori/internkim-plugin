from __future__ import annotations

import pathlib
import re


KIT_PATH = pathlib.Path(__file__).resolve().parents[2] / "assets" / "deck-kit"
KIT_STYLESHEET_PATH = KIT_PATH / "deck-kit.css"
KIT_SCRIPT_PATH = KIT_PATH / "deck-kit.js"
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
GROUPED_NUMBER_PATTERN = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")
SPACED_SEPARATOR_PATTERN = re.compile(r",\s")


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
        f"<script {KIT_MARKER}>\n{KIT_SCRIPT_PATH.read_text(encoding='utf-8')}</script>\n"
    )
    head_match = re.search(r"<head\b[^>]*>", source_text, flags=re.IGNORECASE)
    if head_match:
        return source_text[:head_match.end()] + "\n" + kit_markup + source_text[head_match.end():]
    return kit_markup + source_text


def theme_palettes() -> dict[str, dict[str, str]]:
    palettes = {}
    for match in THEME_BLOCK_PATTERN.finditer(KIT_STYLESHEET_PATH.read_text(encoding="utf-8")):
        palettes[match.group(2)] = {name: value.upper() for name, value in COLOR_TOKEN_PATTERN.findall(match.group(3))}
    return palettes


def theme_names() -> tuple[str, ...]:
    return tuple(theme_palettes())


def chart_types() -> tuple[str, ...]:
    renderers = CHART_RENDERERS_PATTERN.search(KIT_SCRIPT_PATH.read_text(encoding="utf-8"))
    return tuple(CHART_TYPE_PATTERN.findall(renderers.group(1))) if renderers else ()


def split_chart_list(text: str) -> list[str]:
    separator = r",\s+" if SPACED_SEPARATOR_PATTERN.search(text) else ","
    return [value.strip() for value in re.split(separator, text) if value.strip()]


def chart_number(text: str) -> float | None:
    compact = re.sub(r"\s", "", text).replace("−", "-")
    if GROUPED_NUMBER_PATTERN.match(compact):
        compact = compact.replace(",", "")
    try:
        return float(compact)
    except ValueError:
        return None
