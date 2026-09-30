import html
import re

from slide_source import remove_invisible_markup, slide_title, split_slide_sources


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
    slide_role = extract_section_attribute(slide_source, "data-slide-role")
    visual_system = extract_section_attribute(slide_source, "data-visual-system")
    return {
        "title": title,
        "normalizedTitle": normalize_structure_text(title),
        "slideRole": slide_role,
        "visualSystem": visual_system,
        "hasSlideRole": bool(slide_role),
        "hasVisualSystem": bool(visual_system),
        "classNames": class_names,
        "hasTable": has_tag(slide_source, "table"),
        "hasList": has_tag(slide_source, "ul") or has_tag(slide_source, "ol"),
        "tableTextRatio": tag_text_ratio(slide_source, r"<table\b.*?</table>"),
        "listTextRatio": tag_text_ratio(slide_source, r"<[ou]l\b.*?</[ou]l>"),
    }


def tag_text_ratio(slide_source: str, tag_pattern: str) -> float:
    body_source = re.sub(r"<h[1-3]\b[^>]*>.*?</h[1-3]>", " ", slide_source, flags=re.DOTALL | re.IGNORECASE)
    body_characters = len(visible_slide_text(body_source).replace("\n", ""))
    if body_characters == 0:
        return 0.0
    tagged_characters = sum(
        len(visible_slide_text(match).replace("\n", ""))
        for match in re.findall(tag_pattern, body_source, flags=re.DOTALL | re.IGNORECASE)
    )
    return round(min(1.0, tagged_characters / body_characters), 3)


def extract_class_names(slide_source: str) -> list[str]:
    names = []
    for match in re.finditer(r"\bclass\s*=\s*([\"'])(.*?)\1", slide_source, flags=re.IGNORECASE | re.DOTALL):
        names.extend(value.strip().lower() for value in re.split(r"\s+", match.group(2)) if value.strip())
    return names


def extract_section_attribute(slide_source: str, attribute_name: str) -> str:
    section_match = re.search(r"<section\b[^>]*>", slide_source, flags=re.IGNORECASE | re.DOTALL)
    if not section_match:
        return ""
    attribute_pattern = rf"\b{re.escape(attribute_name)}\s*=\s*([\"'])(.*?)\1"
    attribute_match = re.search(attribute_pattern, section_match.group(0), flags=re.IGNORECASE | re.DOTALL)
    if not attribute_match:
        return ""
    return normalize_structure_text(html.unescape(attribute_match.group(2)))


def normalize_structure_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def has_tag(slide_source: str, tag_name: str) -> bool:
    return re.search(rf"<{tag_name}\b", slide_source, flags=re.IGNORECASE) is not None
