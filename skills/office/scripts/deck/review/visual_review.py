from __future__ import annotations

import json
import pathlib

from core.office_result import Issue
from core.skill_paths import ASSETS_PATH
from deck.deck_definitions import GUIDE_SECTIONS
from deck.design_system import DESIGN_FILE_NAME, DesignSystem, design_tokens, read_design_system
from deck.deck_source import Element, find_all, normalized_text, parse_source, visible_text
from deck.review.slide_images import rendered_slide_image_paths
from deck.slide_source import split_slide_sources


VISUAL_REVIEW_FILE_NAME = "visual-review.json"
REVIEW_DEFINITION = json.loads((ASSETS_PATH / "deck-kit" / "visual-review.json").read_text(encoding="utf-8"))
FIXER_GUIDE_SECTIONS = ("Canvas", "Charts", "Icons", "Photos")
SHOWN_TOKENS = ("ground", "text", "muted", "accent", "secondary", "surface", "line")
ICON_NEIGHBOR_LENGTH = 60


def deck_design(system: DesignSystem | None) -> dict:
    if system is None:
        return {}
    tokens = design_tokens(system)
    return {"colors": {name: tokens[name] for name in SHOWN_TOKENS}, "fonts": {"display": tokens["font-display"], "body": tokens["font-body"]}}


def slide_icons(section: Element) -> list[dict[str, str]]:
    return [
        {"icon": element.attributes["data-icon"].strip(), "beside": normalized_text(visible_text(element))[:ICON_NEIGHBOR_LENGTH]}
        for element in (section, *section.descendants())
        if "data-icon" in element.attributes
    ]


def slide_title(section: Element) -> str:
    headings = [child for child in section.child_elements() if child.tag in ("h1", "h2")]
    return normalized_text(visible_text(headings[0])) if headings else ""


def slide_state(deck_title: str, design: dict, section: Element, number: int, count: int) -> dict:
    icons = slide_icons(section)
    return {"deck": deck_title, "slide": f"{number} of {count}", "design": design, **({"icons": icons} if icons else {})}


def fixer_guide() -> str:
    return "\n".join(
        f"{heading}\n" + "\n".join(lines())
        for _, heading, lines in GUIDE_SECTIONS
        if heading.startswith(FIXER_GUIDE_SECTIONS)
    )


def measured_defects(issues: list[Issue], defect_codes: frozenset[str], number: int) -> list[dict[str, str]]:
    location = f"slide {number}"
    return [{"code": issue.kind.code, "message": issue.message, "suggestion": issue.suggestion or ""} for issue in issues if issue.location == location and issue.kind.code in defect_codes]


def deck_title(root: Element) -> str:
    titles = find_all(root, "title")
    return normalized_text("".join(child for child in titles[0].children if isinstance(child, str))) if titles else ""


def visual_review(source_path: pathlib.Path, review_path: pathlib.Path, deck_name: str, issues: list[Issue], defect_codes: frozenset[str]) -> dict:
    source_text = source_path.read_text(encoding="utf-8")
    root = parse_source(source_text)
    sections = find_all(root, "section")
    sources = split_slide_sources(source_text)
    images = rendered_slide_image_paths(review_path, deck_name)
    design = deck_design(read_design_system(source_path.parent / DESIGN_FILE_NAME)[0])
    title = deck_title(root)
    slides = [
        {
            "number": number,
            "image": str(images[number - 1].resolve()),
            "state": slide_state(title, design, section, number, len(sections)),
            "section": sources[number - 1],
            "measured": measured_defects(issues, defect_codes, number),
        }
        for number, section in enumerate(sections, start=1)
        if number <= len(images) and number <= len(sources)
    ]
    return {**REVIEW_DEFINITION, "fixer": {**REVIEW_DEFINITION["fixer"], "kitGuide": fixer_guide()}, "source": str(source_path.resolve()), "slides": slides}


def write_visual_review(source_path: pathlib.Path, review_path: pathlib.Path, deck_name: str, issues: list[Issue], defect_codes: frozenset[str]) -> pathlib.Path:
    path = review_path / VISUAL_REVIEW_FILE_NAME
    path.write_text(json.dumps(visual_review(source_path, review_path, deck_name, issues, defect_codes), ensure_ascii=False, indent=1), encoding="utf-8")
    return path
