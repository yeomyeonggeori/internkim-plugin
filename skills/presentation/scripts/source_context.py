import re

from slide_source import split_slide_sources
from slide_structure import extract_section_attribute, visible_slide_text


TINY_FONT_SIZE_PIXELS = 16
SIDE_STRIPE_MINIMUM_PIXELS = 2


def read_design_tokens(text: str) -> dict[str, str]:
    tokens = {}
    if not text.startswith("---"):
        return tokens
    parts = text.split("---", 2)
    if len(parts) < 3:
        return tokens
    section = ""
    for raw_line in parts[1].splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1].strip()
            continue
        if not section or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key and value:
            tokens[section + "." + key] = value
    return tokens


def design_document_body(design_document_text: str) -> str:
    if not design_document_text.startswith("---"):
        return design_document_text.strip()
    parts = design_document_text.split("---", 2)
    if len(parts) != 3:
        return design_document_text.strip()
    return parts[2].strip()


def inspect_source_context(source_text: str, design_document_text: str, slide_count: int) -> dict[str, object]:
    slide_sources = split_slide_sources(source_text)
    slide_role_count = sum(1 for slide_source in slide_sources if extract_section_attribute(slide_source, "data-slide-role"))
    visual_system_count = source_text.casefold().count("data-visual-system")
    return {
        "hasVisualSystemAttribute": visual_system_count > 0,
        "designDocumentBodyCharacterCount": len(design_document_body(design_document_text)),
        "slideRoleCount": slide_role_count,
        "expectedSlideCount": slide_count,
        "missingSlideRoleCount": max(0, len(slide_sources) - slide_role_count),
        "hasSideStripePattern": source_has_side_stripe(source_text),
        "hasGhostCardPattern": source_has_ghost_card_pattern(source_text),
        "hasTinyTextPattern": source_has_tiny_text_pattern(source_text),
        "absoluteTextFooterSlideCount": absolute_text_footer_slide_count(source_text, slide_sources),
    }


def absolute_text_footer_slide_count(source_text: str, slide_sources: list[str]) -> int:
    footer_classes = absolutely_positioned_bottom_classes(source_text)
    if not footer_classes:
        return 0
    return sum(1 for slide_source in slide_sources if slide_has_text_in_classes(slide_source, footer_classes))


def absolutely_positioned_bottom_classes(source_text: str) -> set[str]:
    classes = set()
    for match in re.finditer(r"\.([\w-]+)[^{}]*\{([^{}]*)\}", source_text):
        rule = match.group(2).casefold()
        if re.search(r"\bposition\s*:\s*absolute", rule) and re.search(r"\bbottom\s*:", rule):
            classes.add(match.group(1).casefold())
    return classes


def slide_has_text_in_classes(slide_source: str, class_names: set[str]) -> bool:
    for class_name in class_names:
        element_pattern = rf"<(\w+)[^>]*class\s*=\s*[\"'][^\"']*\b{re.escape(class_name)}\b[^\"']*[\"'][^>]*>(.*?)</\1>"
        for match in re.finditer(element_pattern, slide_source, flags=re.DOTALL | re.IGNORECASE):
            if len(visible_slide_text(match.group(2)).strip()) >= 3:
                return True
    return False


def source_has_side_stripe(source_text: str) -> bool:
    border_widths = css_pixel_values(r"border-(?:left|right)\s*:\s*([0-9.]+)px", source_text)
    return any(border_width > SIDE_STRIPE_MINIMUM_PIXELS for border_width in border_widths)


def source_has_ghost_card_pattern(source_text: str) -> bool:
    for rule in re.findall(r"\{[^{}]*\}", source_text):
        lowered = rule.casefold()
        if "box-shadow" in lowered and re.search(r"\bborder\s*:\s*1px\s+solid", lowered):
            return True
    return False


def source_has_tiny_text_pattern(source_text: str) -> bool:
    font_sizes = css_pixel_values(r"font-size\s*:\s*([0-9.]+)px", source_text)
    return sum(1 for font_size in font_sizes if font_size < TINY_FONT_SIZE_PIXELS) >= 2


def css_pixel_values(declaration_pattern: str, source_text: str) -> list[float]:
    values = []
    for match in re.finditer(declaration_pattern, source_text, flags=re.IGNORECASE):
        try:
            values.append(float(match.group(1)))
        except ValueError:
            continue
    return values
