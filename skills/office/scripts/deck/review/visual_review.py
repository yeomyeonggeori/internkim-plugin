from __future__ import annotations

import json
import pathlib
import re

from core.design_rules import render_rule_issues
from core.office_result import Issue, OfficeFailure
from core.skill_paths import ASSETS_PATH
from deck.design_system import DESIGN_FILE_NAME, DesignSystem, design_tokens, read_design_system
from deck.deck_source import Element, find_all, normalized_text, parse_source, visible_text
from deck.review.slide_images import rendered_slide_image_paths
from deck.deck_html import measure_for_gate
from deck.slide_edits import Edit, slide_edits
from deck.slide_source import split_slide_sources


VISUAL_REVIEW_FILE_NAME = "visual-review.json"
REVIEW_DEFINITION = json.loads((ASSETS_PATH / "deck-kit" / "visual-review.json").read_text(encoding="utf-8"))
SHOWN_TOKENS = ("ground", "text", "muted", "accent", "secondary", "surface", "line")
ICON_NEIGHBOR_LENGTH = 60
EDITS_OFFERED_PER_SLIDE = 6
VARIANT_FILE_NAME = ".edit-variant.html"


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


def measured_defects(issues: list[Issue], defect_codes: frozenset[str], number: int) -> list[dict[str, str]]:
    location = f"slide {number}"
    return [{"code": issue.kind.code, "message": issue.message, "suggestion": issue.suggestion or ""} for issue in issues if issue.location == location and issue.kind.code in defect_codes]


def deck_title(root: Element) -> str:
    titles = find_all(root, "title")
    return normalized_text("".join(child for child in titles[0].children if isinstance(child, str))) if titles else ""


def replaced_sections(source_text: str, replacements: dict[int, str]) -> str:
    spans = list(re.finditer(r"<section\b[^>]*>.*?</section>", source_text, flags=re.IGNORECASE | re.DOTALL))
    pieces, cursor = [], 0
    for index, span in enumerate(spans):
        pieces.append(source_text[cursor:span.start()])
        pieces.append(replacements.get(index, span.group(0)))
        cursor = span.end()
    pieces.append(source_text[cursor:])
    return "".join(pieces)


def clean_slides(source_path: pathlib.Path, source_text: str, system, replacements: dict[int, str]) -> set[int]:
    variant_path = source_path.parent / VARIANT_FILE_NAME
    variant_path.write_text(replaced_sections(source_text, replacements), encoding="utf-8")
    try:
        slides = measure_for_gate(variant_path, system)
    finally:
        variant_path.unlink(missing_ok=True)
    return {index for index in replacements if not render_rule_issues(slides[index].get("designFindings", []), f"slide {index + 1}")}


def verified_edits(source_path: pathlib.Path, source_text: str, system, sources: list[str]) -> list[list[Edit]]:
    offered = [slide_edits(source)[:EDITS_OFFERED_PER_SLIDE] for source in sources]
    kept: list[list[Edit]] = [[] for _ in sources]
    try:
        for rank in range(max(map(len, offered), default=0)):
            replacements = {index: edits[rank].section for index, edits in enumerate(offered) if rank < len(edits)}
            for index in clean_slides(source_path, source_text, system, replacements):
                kept[index].append(offered[index][rank])
    except OfficeFailure:
        return [[] for _ in sources]
    return kept


def edit_record(edit: Edit) -> dict[str, str]:
    return {"id": edit.id, "operation": edit.operation, "description": edit.description, "section": edit.section}


def visual_review(source_path: pathlib.Path, review_path: pathlib.Path, deck_name: str, issues: list[Issue], defect_codes: frozenset[str]) -> dict:
    source_text = source_path.read_text(encoding="utf-8")
    root = parse_source(source_text)
    sections = find_all(root, "section")
    sources = split_slide_sources(source_text)
    images = rendered_slide_image_paths(review_path, deck_name)
    system = read_design_system(source_path.parent / DESIGN_FILE_NAME)[0]
    design = deck_design(system)
    edits = verified_edits(source_path, source_text, system, sources)
    title = deck_title(root)
    slides = [
        {
            "number": number,
            "image": str(images[number - 1].resolve()),
            "state": slide_state(title, design, section, number, len(sections)),
            "section": sources[number - 1],
            "measured": measured_defects(issues, defect_codes, number),
            "edits": [edit_record(edit) for edit in edits[number - 1]],
        }
        for number, section in enumerate(sections, start=1)
        if number <= len(images) and number <= len(sources)
    ]
    return {**REVIEW_DEFINITION, "source": str(source_path.resolve()), "slides": slides}


def write_visual_review(source_path: pathlib.Path, review_path: pathlib.Path, deck_name: str, issues: list[Issue], defect_codes: frozenset[str]) -> pathlib.Path:
    path = review_path / VISUAL_REVIEW_FILE_NAME
    path.write_text(json.dumps(visual_review(source_path, review_path, deck_name, issues, defect_codes), ensure_ascii=False, indent=1), encoding="utf-8")
    return path
