from __future__ import annotations

from dataclasses import dataclass, replace
import html
import pathlib

from deck.deck_claims import ROLE_NAMES, blank_labels, blanked_deck, deck_units, renumbered_path, renumbered_place
from deck.outline import OUTLINE_FILE_NAME, Outline, read_outline, write_outline
from deck.page_files import deck_language, lone_section, page_path, section_title, titled_section
from deck.slide_source import split_slide_sources
from schemas.blank_paths import WITHDRAWN, WITHDRAWN_SLIDE


@dataclass(frozen=True)
class PageBlanks:
    blanks: list[dict]
    recomposed: tuple[int, ...]
    removed: frozenset[int] = frozenset()

    def held_on_the_remade_deck(self, held: list[dict]) -> list[dict]:
        kept = []
        for blank in held:
            if blank.get(WITHDRAWN) == WITHDRAWN_SLIDE:
                kept.append(blank)
                continue
            field = str(blank.get("field") or "")
            path = renumbered_path(field, set(self.removed))
            if path is not None:
                kept.append(blank | {"field": path, "label": renumbered_place(str(blank.get("label") or ""), field, path)})
        return kept


def unscoped_deck(outline: Outline, sections: list[str], is_titled: bool = True) -> str:
    title = f"<title>{html.escape(outline.pages[0].title)}</title>" if is_titled and outline.pages else ""
    return f'<!doctype html><html lang="{deck_language(outline)}"><head>{title}</head><body>\n' + "\n".join(sections) + "\n</body></html>\n"


def on_slide(path: str, index: int) -> str | None:
    prefix = f"slides[{index}]."
    return path.replace(prefix, "slides[0].", 1) if path.startswith(prefix) else None


def blanked_section(outline: Outline, section: str, index: int, paths: list[str], replacements: dict[str, str]) -> str | None:
    own_paths = [moved for moved in (on_slide(path, index) for path in paths) if moved]
    own_replacements = {moved: text for path, text in replacements.items() if (moved := on_slide(path, index))}
    if not own_paths and not own_replacements:
        return section
    blanked = split_slide_sources(blanked_deck(unscoped_deck(outline, [section], is_titled=index == 0), own_paths, own_replacements))
    return blanked[0] if blanked else None


def blanked_texts(document: str, paths: list[str]) -> set[str]:
    units = {unit.path: unit.text for unit in deck_units(document)}
    return {units[path] for path in paths if path in units}


def names_any(line: str, texts: set[str]) -> bool:
    return any(text.casefold() in line.casefold() for text in texts)


def without_blanked_brief(outline: Outline, texts: set[str], removed: set[int]) -> Outline:
    pages = tuple(replace(page, brief=tuple(line for line in page.brief if not names_any(line, texts))) for index, page in enumerate(outline.pages) if index not in removed)
    return replace(outline, pages=pages)


def with_page_titles(outline: Outline, results: list[str | None]) -> Outline:
    titles = [section_title(result) if result is not None else None for result in results]
    return replace(outline, pages=tuple(page if title is None else replace(page, title=title) for page, title in zip(outline.pages, titles)))


def rewrite_pages(directory: pathlib.Path, sections: list[str], previous_count: int) -> None:
    for number, section in enumerate(sections, start=1):
        page_path(directory, number).write_text(section + "\n", encoding="utf-8")
    for number in range(len(sections) + 1, previous_count + 1):
        page_path(directory, number).unlink(missing_ok=True)


@dataclass(frozen=True)
class BlankPlan:
    outline: Outline
    sections: list[str]
    results: list[str | None]

    @property
    def document(self) -> str:
        return unscoped_deck(self.outline, self.sections)

    @property
    def removed(self) -> set[int]:
        return {index for index, result in enumerate(self.results) if result is None}

    def removed_slides(self) -> list[dict]:
        names = ROLE_NAMES[deck_language(self.outline)]
        return [{"field": f"slides[{index}]", "label": f"{names['slide']} \"{self.outline.pages[index].title}\"", WITHDRAWN: WITHDRAWN_SLIDE} for index in sorted(self.removed)]


def planned_blanks(directory: pathlib.Path, paths: list[str], replacements: dict[str, str]) -> BlankPlan | None:
    outline, _ = read_outline(directory / OUTLINE_FILE_NAME)
    if outline is None or not (paths or replacements):
        return None
    sections = [titled_section(lone_section(page_path(directory, number).read_text(encoding="utf-8")) or "", page.title) for number, page in enumerate(outline.pages, start=1)]
    return BlankPlan(outline, sections, [blanked_section(outline, section, index, paths, replacements) for index, section in enumerate(sections)])


def slides_a_blanking_removes(directory: pathlib.Path, paths: list[str]) -> list[dict]:
    plan = planned_blanks(directory, paths, {})
    return plan.removed_slides() if plan else []


def renumbered_blanks(plan: BlankPlan, paths: list[str]) -> list[dict]:
    blanks = []
    for blank in blank_labels(plan.document, paths):
        path = renumbered_path(blank["field"], plan.removed)
        if path is not None:
            blanks.append(blank | {"field": path, "label": renumbered_place(blank["label"], blank["field"], path)})
    return blanks + plan.removed_slides()


def blank_pages(directory: pathlib.Path, paths: list[str], replacements: dict[str, str]) -> PageBlanks:
    plan = planned_blanks(directory, paths, replacements)
    if plan is None:
        return PageBlanks([], ())
    removed = plan.removed
    write_outline(directory / OUTLINE_FILE_NAME, without_blanked_brief(with_page_titles(plan.outline, plan.results), blanked_texts(plan.document, paths), removed))
    rewrite_pages(directory, [result for result in plan.results if result is not None], len(plan.sections))
    changed = [index for index, result in enumerate(plan.results) if result is not None and result != plan.sections[index]]
    recomposed = tuple(index + 1 - sum(1 for gone in removed if gone < index) for index in changed)
    return PageBlanks(renumbered_blanks(plan, paths), recomposed, frozenset(removed))
