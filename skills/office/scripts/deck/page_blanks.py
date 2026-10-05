from __future__ import annotations

from dataclasses import dataclass, replace
import html
import pathlib

from deck.deck_claims import blank_labels, blanked_deck, deck_units
from deck.outline import OUTLINE_FILE_NAME, Outline, read_outline, write_outline
from deck.page_files import deck_language, lone_section, page_path
from deck.slide_source import split_slide_sources


@dataclass(frozen=True)
class PageBlanks:
    blanks: list[dict]
    recomposed: tuple[int, ...]


def unscoped_deck(outline: Outline, sections: list[str]) -> str:
    title = html.escape(outline.pages[0].title if outline.pages else "")
    return f'<!doctype html><html lang="{deck_language(outline)}"><head><title>{title}</title></head><body>\n' + "\n".join(sections) + "\n</body></html>\n"


def on_slide(path: str, index: int) -> str | None:
    prefix = f"slides[{index}]."
    return path.replace(prefix, "slides[0].", 1) if path.startswith(prefix) else None


def blanked_section(outline: Outline, section: str, index: int, paths: list[str], replacements: dict[str, str]) -> str | None:
    own_paths = [moved for moved in (on_slide(path, index) for path in paths) if moved]
    own_replacements = {moved: text for path, text in replacements.items() if (moved := on_slide(path, index))}
    if not own_paths and not own_replacements:
        return section
    blanked = split_slide_sources(blanked_deck(unscoped_deck(outline, [section]), own_paths, own_replacements))
    return blanked[0] if blanked else None


def blanked_texts(document: str, paths: list[str]) -> set[str]:
    units = {unit.path: unit.text for unit in deck_units(document)}
    return {units[path] for path in paths if path in units}


def without_blanked_brief(outline: Outline, texts: set[str], removed: set[int]) -> Outline:
    pages = tuple(replace(page, brief=tuple(line for line in page.brief if not any(text in line for text in texts))) for index, page in enumerate(outline.pages) if index not in removed)
    return replace(outline, pages=pages)


def rewrite_pages(directory: pathlib.Path, sections: list[str], previous_count: int) -> None:
    for number, section in enumerate(sections, start=1):
        page_path(directory, number).write_text(section + "\n", encoding="utf-8")
    for number in range(len(sections) + 1, previous_count + 1):
        page_path(directory, number).unlink(missing_ok=True)


def blank_pages(directory: pathlib.Path, paths: list[str], replacements: dict[str, str]) -> PageBlanks:
    outline, _ = read_outline(directory / OUTLINE_FILE_NAME)
    if outline is None or not (paths or replacements):
        return PageBlanks([], ())
    sections = [lone_section(page_path(directory, number).read_text(encoding="utf-8")) or "" for number in range(1, len(outline.pages) + 1)]
    document = unscoped_deck(outline, sections)
    results = [blanked_section(outline, section, index, paths, replacements) for index, section in enumerate(sections)]
    removed = {index for index, result in enumerate(results) if result is None}
    write_outline(directory / OUTLINE_FILE_NAME, without_blanked_brief(outline, blanked_texts(document, paths), removed))
    rewrite_pages(directory, [result for result in results if result is not None], len(sections))
    changed = [index for index, result in enumerate(results) if result is not None and result != sections[index]]
    return PageBlanks(blank_labels(document, paths), tuple(index + 1 - sum(1 for gone in removed if gone < index) for index in changed))
