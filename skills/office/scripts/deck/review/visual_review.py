from __future__ import annotations

import json
import pathlib

from core.office_result import Issue
from core.skill_paths import ASSETS_PATH
from deck.design_system import DesignSystem, style_summary
from deck.deck_source import Element, find_all, normalized_text, parse_source, visible_text
from deck.outline import Outline
from deck.page_files import lone_section, page_path
from deck.review.slide_images import rendered_slide_image_paths


VISUAL_REVIEW_FILE_NAME = "visual-review.json"
REVIEW_DEFINITION = json.loads((ASSETS_PATH / "deck-kit" / "visual-review.json").read_text(encoding="utf-8"))
ICON_NEIGHBOR_LENGTH = 60


def slide_icons(section: Element) -> list[dict[str, str]]:
    return [
        {"icon": element.attributes["data-icon"].strip(), "beside": normalized_text(visible_text(element))[:ICON_NEIGHBOR_LENGTH]}
        for element in (section, *section.descendants())
        if "data-icon" in element.attributes
    ]


def measured_defects(issues: list[Issue], defect_codes: frozenset[str], number: int) -> list[dict[str, str]]:
    locations = {f"slide {number}", f"page {number}"}
    return [{"code": issue.kind.code, "message": issue.message, "suggestion": issue.suggestion or ""} for issue in issues if issue.location in locations and issue.kind.code in defect_codes]


def slide_state(outline: Outline, style: dict, number: int, section: str) -> dict:
    entry = outline.pages[number - 1]
    icons = slide_icons(find_all(parse_source(section), "section")[0])
    page = {"title": entry.title, "type": entry.type, "layout": entry.layout, "brief": list(entry.brief)}
    return {"deck": outline.pages[0].title, "slide": f"{number} of {len(outline.pages)}", "design": style, "page": page, **({"icons": icons} if icons else {})}


def slide_record(request, outline: Outline, style: dict, issues: list[Issue], defect_codes: frozenset[str], number: int, image: pathlib.Path) -> dict:
    path = page_path(request.deck.directory, number)
    section = lone_section(path.read_text(encoding="utf-8")) or ""
    record = {"number": number, "image": str(image.resolve()), "state": slide_state(outline, style, number, section), "section": section, "source": str(path.resolve()), "measured": measured_defects(issues, defect_codes, number)}
    return record | ({"recompose": True} if number in request.recomposed else {})


def visual_review(request, system: DesignSystem, outline: Outline, issues: list[Issue]) -> dict:
    from deck.review.acceptance import OBJECTIVE_DEFECT_CODES

    images = rendered_slide_image_paths(request.review_path, request.deck_name)
    style = style_summary(system)
    slides = [slide_record(request, outline, style, issues, OBJECTIVE_DEFECT_CODES, number, image) for number, image in enumerate(images[:len(outline.pages)], start=1)]
    return {**REVIEW_DEFINITION, "source": str(request.deck.directory), "slides": slides}


def write_visual_review(request, system: DesignSystem, outline: Outline, issues: list[Issue]) -> pathlib.Path:
    path = request.review_path / VISUAL_REVIEW_FILE_NAME
    path.write_text(json.dumps(visual_review(request, system, outline, issues), ensure_ascii=False, indent=1), encoding="utf-8")
    return path
