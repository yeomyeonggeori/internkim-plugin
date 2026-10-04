from __future__ import annotations

from collections import Counter

from deck.deck_definitions import TITLE_STYLE_INCONSISTENT
from deck.layout_thresholds import PIXEL_TOLERANCE


FEATURE_LAYOUTS = frozenset({"section", "closing"})
OWN_TITLE_LAYOUTS = frozenset({"cover", "statement", "quote", "image"})
COMPARED_PROPERTIES = (("fontFamily", "typeface"), ("fontWeight", "weight"), ("color", "color"), ("textAlign", "alignment"))
SMALLEST_COMPARED_GROUP = 3


def title_family(layout: str) -> str | None:
    if layout in OWN_TITLE_LAYOUTS:
        return None
    return "feature" if layout in FEATURE_LAYOUTS else "content"


def titled_slides(slides: list[dict]) -> dict[str, list[tuple[dict, dict]]]:
    families: dict[str, list[tuple[dict, dict]]] = {}
    for slide in slides:
        family = title_family(str(slide["structure"].get("kitLayout") or ""))
        title = (slide.get("geometry") or {}).get("titleStyle")
        if family and title:
            families.setdefault(family, []).append((slide, title))
    return families


def usual_value(values: list[object]) -> object | None:
    value, count = Counter(values).most_common(1)[0]
    return value if count * 2 > len(values) else None


def usual_indent(indents: list[float]) -> float | None:
    for candidate in indents:
        if sum(abs(indent - candidate) <= PIXEL_TOLERANCE for indent in indents) * 2 > len(indents):
            return candidate
    return None


def title_differences(title: dict, usual: dict[str, object]) -> list[str]:
    differences = [f"{name} {title[key]} where the others use {usual[key]}" for key, name in COMPARED_PROPERTIES if usual[key] is not None and title[key] != usual[key]]
    indent = usual["textLeft"]
    if indent is not None and title["textLeft"] is not None and abs(title["textLeft"] - indent) > PIXEL_TOLERANCE:
        differences.append(f"indent {title['textLeft']:g}px where the others start at {indent:g}px")
    return differences


def apply_title_consistency_warning(slides: list[dict]) -> None:
    for members in titled_slides(slides).values():
        if len(members) < SMALLEST_COMPARED_GROUP:
            continue
        titles = [title for _, title in members]
        usual = {key: usual_value([title[key] for title in titles]) for key, _ in COMPARED_PROPERTIES}
        usual["textLeft"] = usual_indent([title["textLeft"] for title in titles if title["textLeft"] is not None])
        for slide, title in members:
            differences = title_differences(title, usual)
            if differences:
                slide["warnings"].append(TITLE_STYLE_INCONSISTENT.issue(f"the title \"{title['text']}\" has {'; '.join(differences)}"))
