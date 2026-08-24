#!/usr/bin/env python3
import datetime
import html
import html.parser
import json
import pathlib
import re
import struct
import sys
import typing
import zlib


FIT_REVIEW_FILE_PATTERN = "fit-review-XX.md"
CONTACT_SHEET_GROUP_SIZE = 4
CONTACT_SHEET_THUMBNAIL_WIDTH = 560
CONTENT_DENSITY_MINIMUM = 0.006
CONTENT_DENSITY_MAXIMUM = 0.42
TEXT_OVERFLOW_CHARACTER_LIMIT = 900
TEXT_OVERFLOW_LINE_LIMIT = 16
VISUAL_QUALITY_SCORE_MINIMUM = 82
FIT_REVIEW_PROMPT = (
    "Open the paired contact sheet and verify every expected visible text item is fully inside the slide frame, "
    "not clipped, hidden, or pushed past the right or bottom edge."
)
DESIGN_REVIEW_PROMPT = (
    "Also judge whether the deck looks like a purposeful executive artifact: varied slide roles, claim-style titles, "
    "clear decision logic, and no generic repeated card-grid or raw table/list slides."
)
STRUCTURE_DOMINANCE_RATIO = 0.55
CLAIM_TITLE_WORD_MINIMUM = 5
DESIGN_DOCUMENT_BODY_MINIMUM_CHARACTERS = 80
VERTICAL_DEAD_ZONE_HEIGHT_RATIO = 0.27
DECORATIVE_BAND_OCCUPANCY = 0.85
DECORATIVE_BAND_MAXIMUM_DEPTH_RATIO = 0.15
KOREAN_SENTENCE_ENDINGS = ("다", "요", "까", "죠")
LABEL_ONLY_SLIDE_ROLES = {"title", "cover", "divider", "section"}
DESIGN_WARNING_PREFIXES = (
    "topicTitleWarning",
    "rawTableWarning",
    "bareListWarning",
    "repeatedCompositionWarning",
    "rawStructurePatternWarning",
    "weakVisualIdentityWarning",
    "missingSlideRoleWarning",
    "sideStripeWarning",
    "ghostCardWarning",
    "tinyTextWarning",
    "languageMismatchWarning",
    "unsourcedCurrentDateWarning",
    "verticalDeadZoneWarning",
    "absoluteFooterWarning",
    "emojiIconWarning",
    "missingRequiredTextWarning",
    "inconsistentFooterBaselineWarning",
    "unpinnedFooterWarning",
    "missingSpeakerNotesWarning",
)
DESIGN_WARNING_WEIGHTS = {
    "weakVisualIdentityWarning": 24,
    "missingSlideRoleWarning": 16,
    "sideStripeWarning": 14,
    "ghostCardWarning": 14,
    "tinyTextWarning": 8,
    "repeatedCompositionWarning": 14,
    "rawStructurePatternWarning": 12,
    "rawTableWarning": 10,
    "bareListWarning": 10,
    "topicTitleWarning": 8,
    "languageMismatchWarning": 10,
    "unsourcedCurrentDateWarning": 10,
    "verticalDeadZoneWarning": 10,
    "absoluteFooterWarning": 12,
    "emojiIconWarning": 8,
    "missingRequiredTextWarning": 14,
    "inconsistentFooterBaselineWarning": 8,
    "unpinnedFooterWarning": 10,
    "missingSpeakerNotesWarning": 8,
}


def main() -> int:
    arguments = parse_arguments(sys.argv)
    if not arguments:
        print("Usage: render_review.py <source> <deck-name> <review-dir>", file=sys.stderr)
        return 2
    report = build_review_report(arguments["sourcePath"], arguments["deckName"], arguments["reviewDirectoryPath"])
    write_review_outputs(arguments["reviewDirectoryPath"], report)
    print(
        f"  - Slide render review: {report['slideCount']} slides, "
        f"passed={str(report['passed']).lower()}, "
        f"staticGatePassed={str(report['staticGatePassed']).lower()}, "
        f"visualQualityScore={report['visualQualityScore']}, "
        f"needsDesignRevision={str(report['needsDesignRevision']).lower()}, "
        f"renderSource={report['renderSource']}"
    )
    print("QUALITY_GATE " + json.dumps({
        "source": "presentation-review",
        "passed": bool(report["staticGatePassed"]) and not bool(report["needsDesignRevision"]),
        "score": report["visualQualityScore"],
    }))
    return 0


def parse_arguments(raw_arguments: list[str]) -> typing.Optional[dict[str, object]]:
    if len(raw_arguments) != 4:
        return None
    return {
        "sourcePath": pathlib.Path(raw_arguments[1]),
        "deckName": raw_arguments[2],
        "reviewDirectoryPath": pathlib.Path(raw_arguments[3]),
    }


def build_review_report(source_path: pathlib.Path, deck_name: str, review_directory_path: pathlib.Path) -> dict[str, object]:
    image_paths = sorted(review_directory_path.glob(deck_name + "*.png"))
    render_source = read_render_source(review_directory_path, image_paths)
    source_text = source_path.read_text(encoding="utf-8")
    design_document_text = read_optional_text(source_path.parent / "DESIGN.md")
    required_text_ledger = read_optional_text(source_path.parent / "required-visible-text.txt")
    design = read_design_tokens(design_document_text)
    slide_count = max(len(split_slide_sources(source_text)), len(image_paths))
    source_context = inspect_source_context(source_text, design_document_text, slide_count)
    slide_texts = read_slide_texts(source_text, slide_count)
    slides = [
        review_slide(image_paths[index] if index < len(image_paths) else None, design, index + 1, slide_texts[index])
        for index in range(slide_count)
    ]
    apply_deck_design_warnings(slides, source_context, render_source)
    apply_language_mismatch_warning(slides, slide_texts)
    apply_unsourced_current_date_warning(slides, slide_texts, required_text_ledger)
    apply_emoji_icon_warning(slides, slide_texts)
    apply_missing_required_text_warning(slides, slide_texts, required_text_ledger)
    apply_footer_baseline_warning(slides)
    apply_unpinned_footer_warning(slides, source_text)
    apply_missing_speaker_notes_warning(slides, source_text)
    annotate_design_revision_need(slides)
    contact_sheets = write_contact_sheets(review_directory_path, deck_name, image_paths)
    fit_reviews = create_fit_reviews(contact_sheets, slides)
    design_warnings = unique_design_warnings(slides)
    visual_evidence_reliable = render_source == "browser"
    visual_quality_score = calculate_visual_quality_score(design_warnings)
    static_gate_passed = visual_quality_score >= VISUAL_QUALITY_SCORE_MINIMUM
    quality_gate_passed = (
        all(slide["passed"] for slide in slides)
        and len(slides) > 0
        and visual_evidence_reliable
        and static_gate_passed
    )
    return {
        "passed": quality_gate_passed,
        "qualityGatePassed": quality_gate_passed,
        "staticGatePassed": static_gate_passed,
        "visualQualityScore": visual_quality_score,
        "visualQualityScoreMinimum": VISUAL_QUALITY_SCORE_MINIMUM,
        "visualEvidenceReliable": visual_evidence_reliable,
        "needsDesignRevision": bool(design_warnings) or not static_gate_passed,
        "reviewUnavailable": slide_count == 0,
        "renderSource": render_source,
        "designWarnings": design_warnings,
        "sourceContext": source_context,
        "source": source_path.name,
        "deckName": deck_name,
        "slideCount": slide_count,
        "renderedSlideCount": len(image_paths),
        "design": design,
        "designReviewPrompt": DESIGN_REVIEW_PROMPT,
        "contactSheets": attach_fit_review_metadata(contact_sheets, fit_reviews),
        "fitReviews": fit_reviews,
        "slides": slides,
    }


def read_render_source(review_directory_path: pathlib.Path, image_paths: list[pathlib.Path]) -> str:
    source_path = review_directory_path / "render-source.txt"
    if source_path.exists():
        value = source_path.read_text(encoding="utf-8").strip()
        if value:
            return value
    if image_paths:
        return "browser"
    return "unavailable"


def write_review_outputs(review_directory_path: pathlib.Path, report: dict[str, object]) -> None:
    write_fit_reviews(review_directory_path, report["fitReviews"])
    write_json(review_directory_path / "slide-review.json", report)
    write_markdown(review_directory_path / "slide-review.md", report)


def read_optional_text(path: pathlib.Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


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


def read_slide_texts(source_text: str, slide_count: int) -> list[dict[str, object]]:
    slide_sources = split_slide_sources(source_text)
    slide_texts = []
    for index in range(slide_count):
        slide_source = slide_sources[index] if index < len(slide_sources) else ""
        visible_text = visible_slide_text(slide_source) if slide_source else ""
        lines = [line for line in visible_text.splitlines() if line.strip()]
        slide_texts.append({
            "index": index + 1,
            "expectedVisibleText": visible_text,
            "textCharacterCount": len(visible_text),
            "textLineCount": len(lines),
            "textPreview": preview_text(visible_text),
            "structure": inspect_slide_structure(slide_source),
        })
    return slide_texts


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
    for match in re.finditer(r"border-(?:left|right)\s*:\s*([0-9.]+)px", source_text, flags=re.IGNORECASE):
        try:
            if float(match.group(1)) > 2:
                return True
        except ValueError:
            continue
    return False


def source_has_ghost_card_pattern(source_text: str) -> bool:
    for rule in re.findall(r"\{[^{}]*\}", source_text):
        lowered = rule.casefold()
        if "box-shadow" in lowered and re.search(r"\bborder\s*:\s*1px\s+solid", lowered):
            return True
    return False


def source_has_tiny_text_pattern(source_text: str) -> bool:
    font_sizes = []
    for match in re.finditer(r"font-size\s*:\s*([0-9.]+)px", source_text, flags=re.IGNORECASE):
        try:
            font_sizes.append(float(match.group(1)))
        except ValueError:
            continue
    return sum(1 for font_size in font_sizes if font_size < 16) >= 2


def split_slide_sources(source_text: str) -> list[str]:
    sections = re.findall(r"<section\b[^>]*>.*?</section>", source_text, flags=re.DOTALL | re.IGNORECASE)
    return [section.strip() for section in sections if section.strip()]


def visible_slide_text(slide_source: str) -> str:
    text = remove_invisible_markup(slide_source)
    text = convert_html_markup_to_text(text)
    return normalize_visible_text(html.unescape(text))


def remove_invisible_markup(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(
        r"<(?:aside|div)\b[^>]*class=[\"'][^\"']*(?:speaker-notes|notes)[^\"']*[\"'][^>]*>.*?</(?:aside|div)>",
        " ",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text


def convert_html_markup_to_text(text: str) -> str:
    replacements = [
        (r"<[^>]+>", "\n"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def normalize_visible_text(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def preview_text(text: str) -> str:
    compact_text = re.sub(r"\s+", " ", text).strip()
    if len(compact_text) <= 180:
        return compact_text
    return compact_text[:177].rstrip() + "..."


def inspect_slide_structure(slide_source: str) -> dict[str, object]:
    class_names = extract_class_names(slide_source)
    title = first_heading_text(slide_source)
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


def first_heading_text(slide_source: str) -> str:
    heading_texts = [
        normalize_visible_text(html.unescape(convert_html_markup_to_text(match.group(2)))).replace("\n", " ")
        for match in re.finditer(r"<(h[1-3])\b[^>]*>(.*?)</\1>", slide_source, flags=re.IGNORECASE | re.DOTALL)
    ]
    if not heading_texts:
        return ""
    return max(heading_texts, key=len)


def normalize_structure_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def has_tag(slide_source: str, tag_name: str) -> bool:
    return re.search(rf"<{tag_name}\b", slide_source, flags=re.IGNORECASE) is not None


def review_slide(path: typing.Optional[pathlib.Path], design: dict[str, str], index: int, slide_text: dict[str, object]) -> dict[str, object]:
    structure = slide_text["structure"]
    if path is None:
        return review_slide_without_image(index, slide_text, structure)
    image = read_png(path)
    background = corner_background_color(image)
    analysis = analyze_image_content(image, background)
    content_bounds = analysis["bounds"]
    density = content_density(image, background)
    margin = margin_pixels(image, design)
    checks = slide_checks(content_bounds, image, margin, density)
    risks = slide_risks(content_bounds, image, margin, slide_text)
    warnings = slide_warnings(checks, margin, density, risks, structure)
    if analysis["verticalGapRatio"] >= VERTICAL_DEAD_ZONE_HEIGHT_RATIO and str(structure["slideRole"]) not in LABEL_ONLY_SLIDE_ROLES:
        warnings.append(
            f"verticalDeadZoneWarning: an empty band spans {analysis['verticalGapRatio']:.0%} of the slide height; distribute content to fill the frame"
        )
    return {
        "index": index,
        "filename": path.name,
        "hasRenderEvidence": True,
        "width": image["width"],
        "height": image["height"],
        "contentBounds": content_bounds or {},
        "contentDensity": density,
        "expectedVisibleText": slide_text["expectedVisibleText"],
        "textCharacterCount": slide_text["textCharacterCount"],
        "textLineCount": slide_text["textLineCount"],
        "textPreview": slide_text["textPreview"],
        "marginPixel": margin,
        "passed": all(checks.values()),
        "checks": checks,
        "risks": risks,
        "warnings": warnings,
        "needsDesignRevision": False,
        "structure": structure,
    }


def review_slide_without_image(index: int, slide_text: dict[str, object], structure: dict[str, object]) -> dict[str, object]:
    risks = {"textOverflowRisk": text_overflow_risk(slide_text), "frameFitRisk": False}
    warnings = []
    if risks["textOverflowRisk"]:
        warnings.append("textOverflowRisk: extracted slide text is long enough to require contact sheet verification")
    warnings.extend(slide_design_warnings(structure))
    return {
        "index": index,
        "filename": "",
        "hasRenderEvidence": False,
        "width": 0,
        "height": 0,
        "contentBounds": {},
        "contentDensity": 0.0,
        "expectedVisibleText": slide_text["expectedVisibleText"],
        "textCharacterCount": slide_text["textCharacterCount"],
        "textLineCount": slide_text["textLineCount"],
        "textPreview": slide_text["textPreview"],
        "marginPixel": 0,
        "passed": False,
        "checks": {},
        "risks": risks,
        "warnings": warnings,
        "needsDesignRevision": False,
        "structure": structure,
    }


def slide_checks(bounds: typing.Optional[dict[str, int]], image: dict[str, object], margin: int, density: float) -> dict[str, bool]:
    return {
        "nonblank": bounds is not None,
        "safeMargin": safe_margin_passed(bounds, image, margin),
        "edgeOverflow": edge_overflow_passed(bounds, image),
        "notTooEmpty": density >= CONTENT_DENSITY_MINIMUM,
        "notTooDense": density <= CONTENT_DENSITY_MAXIMUM,
    }


def slide_risks(bounds: typing.Optional[dict[str, int]], image: dict[str, object], margin: int, slide_text: dict[str, object]) -> dict[str, bool]:
    return {
        "textOverflowRisk": text_overflow_risk(slide_text),
        "frameFitRisk": frame_fit_risk(bounds, image, margin),
    }


def read_png(path: pathlib.Path) -> dict[str, object]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(str(path) + " is not a PNG")
    offset = 8
    width = 0
    height = 0
    color_type = 0
    bit_depth = 0
    palette = []
    compressed_parts = []
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk_data = data[offset + 8:offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = parse_ihdr(chunk_data)
        elif chunk_type == b"PLTE":
            palette = parse_palette(chunk_data)
        elif chunk_type == b"IDAT":
            compressed_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break
    if bit_depth != 8:
        raise ValueError(str(path) + " uses unsupported PNG bit depth")
    rows = decode_png_rows(width, height, color_type, palette, b"".join(compressed_parts))
    return {"width": width, "height": height, "rows": rows}


def parse_ihdr(chunk_data: bytes) -> tuple[int, int, int, int]:
    width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk_data)
    return width, height, bit_depth, color_type


def parse_palette(chunk_data: bytes) -> list[tuple[int, int, int, int]]:
    return [(chunk_data[index], chunk_data[index + 1], chunk_data[index + 2], 255) for index in range(0, len(chunk_data), 3)]


def decode_png_rows(
    width: int,
    height: int,
    color_type: int,
    palette: list[tuple[int, int, int, int]],
    compressed_data: bytes,
) -> list[list[tuple[int, int, int, int]]]:
    raw = zlib.decompress(compressed_data)
    bytes_per_pixel = png_bytes_per_pixel(color_type)
    stride = width * bytes_per_pixel
    rows = []
    previous = [0] * stride
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        current = list(raw[offset:offset + stride])
        offset += stride
        reconstructed = unfilter_row(filter_type, current, previous, bytes_per_pixel)
        rows.append(pixels_from_row(reconstructed, color_type, palette))
        previous = reconstructed
    return rows


def png_bytes_per_pixel(color_type: int) -> int:
    if color_type == 0:
        return 1
    if color_type == 2:
        return 3
    if color_type == 3:
        return 1
    if color_type == 4:
        return 2
    if color_type == 6:
        return 4
    raise ValueError("unsupported PNG color type")


def unfilter_row(filter_type: int, current: list[int], previous: list[int], bytes_per_pixel: int) -> list[int]:
    row = current[:]
    for index, value in enumerate(row):
        left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index] if index < len(previous) else 0
        upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel and index < len(previous) else 0
        if filter_type == 1:
            row[index] = (value + left) & 255
        elif filter_type == 2:
            row[index] = (value + up) & 255
        elif filter_type == 3:
            row[index] = (value + ((left + up) // 2)) & 255
        elif filter_type == 4:
            row[index] = (value + paeth_predictor(left, up, upper_left)) & 255
        elif filter_type != 0:
            raise ValueError("unsupported PNG filter")
    return row


def paeth_predictor(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def pixels_from_row(row: list[int], color_type: int, palette: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    pixels = []
    step = png_bytes_per_pixel(color_type)
    for index in range(0, len(row), step):
        if color_type == 0:
            value = row[index]
            pixels.append((value, value, value, 255))
        elif color_type == 2:
            pixels.append((row[index], row[index + 1], row[index + 2], 255))
        elif color_type == 3:
            pixels.append(palette[row[index]])
        elif color_type == 4:
            value = row[index]
            pixels.append((value, value, value, row[index + 1]))
        elif color_type == 6:
            pixels.append((row[index], row[index + 1], row[index + 2], row[index + 3]))
    return pixels


def corner_background_color(image: dict[str, object]) -> tuple[int, int, int, int]:
    rows = image["rows"]
    width = image["width"]
    height = image["height"]
    samples = []
    sample_size = max(6, min(width, height) // 40)
    for y in list(range(sample_size)) + list(range(height - sample_size, height)):
        for x in list(range(sample_size)) + list(range(width - sample_size, width)):
            samples.append(rows[y][x])
    return median_color(samples)


def median_color(samples: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    channels = []
    for channel_index in range(4):
        values = sorted(sample[channel_index] for sample in samples)
        channels.append(values[len(values) // 2])
    return tuple(channels)


def analyze_image_content(image: dict[str, object], background: tuple[int, int, int, int]) -> dict[str, object]:
    width = image["width"]
    height = image["height"]
    row_spans, column_counts = content_row_spans(image, background)
    row_counts = [span["count"] for span in row_spans]
    top_trim = decorative_band_depth(row_counts, width, height)
    bottom_trim = decorative_band_depth(list(reversed(row_counts)), width, height)
    interior_height = height - top_trim - bottom_trim
    left_trim = decorative_band_depth(column_counts, interior_height, width)
    right_trim = decorative_band_depth(list(reversed(column_counts)), interior_height, width)
    left_limit = left_trim
    right_limit = width - right_trim - 1
    occupied_rows = [
        y
        for y in range(top_trim, height - bottom_trim)
        if row_is_occupied(row_spans[y], left_limit, right_limit)
    ]
    if not occupied_rows:
        return {"bounds": None, "verticalGapRatio": 0.0}
    bounds = {
        "left": max(left_limit, min(row_spans[y]["left"] for y in occupied_rows)),
        "top": occupied_rows[0],
        "right": min(right_limit, max(row_spans[y]["right"] for y in occupied_rows)),
        "bottom": occupied_rows[-1],
    }
    largest_gap = largest_internal_gap(occupied_rows)
    return {"bounds": bounds, "verticalGapRatio": round(largest_gap / height, 3)}


def content_row_spans(
    image: dict[str, object], background: tuple[int, int, int, int]
) -> tuple[list[dict[str, object]], list[int]]:
    width = image["width"]
    column_counts = [0] * width
    row_spans = []
    for row in image["rows"]:
        count = 0
        left = None
        right = None
        for x, pixel in enumerate(row):
            if is_background_pixel(pixel, background):
                continue
            count += 1
            column_counts[x] += 1
            if left is None:
                left = x
            right = x
        row_spans.append({"count": count, "left": left, "right": right})
    return row_spans, column_counts


def decorative_band_depth(counts: list[int], span_length: int, dimension_length: int) -> int:
    maximum_depth = round(dimension_length * DECORATIVE_BAND_MAXIMUM_DEPTH_RATIO)
    depth = 0
    for count in counts:
        if depth >= maximum_depth or count < span_length * DECORATIVE_BAND_OCCUPANCY:
            break
        depth += 1
    return depth


def row_is_occupied(span: dict[str, object], left_limit: int, right_limit: int) -> bool:
    if span["count"] == 0:
        return False
    return int(span["right"]) >= left_limit and int(span["left"]) <= right_limit


def largest_internal_gap(occupied_rows: list[int]) -> int:
    largest = 0
    for previous_row, next_row in zip(occupied_rows, occupied_rows[1:]):
        largest = max(largest, next_row - previous_row - 1)
    return largest


def content_density(image: dict[str, object], background: tuple[int, int, int, int]) -> float:
    rows = image["rows"]
    content_pixels = 0
    total_pixels = image["width"] * image["height"]
    for row in rows:
        for pixel in row:
            if not is_background_pixel(pixel, background):
                content_pixels += 1
    if total_pixels == 0:
        return 0
    return round(content_pixels / total_pixels, 4)


def is_background_pixel(pixel: tuple[int, int, int, int], background: tuple[int, int, int, int]) -> bool:
    if pixel[3] < 8:
        return True
    distance = sum(abs(pixel[index] - background[index]) for index in range(3))
    return distance <= 34


def margin_pixels(image: dict[str, object], design: dict[str, str]) -> int:
    margin = parse_pixel_value(design.get("layout.margin", "68px"), 68)
    scale = image["width"] / 1280
    return max(16, round(margin * scale * 0.35))


def parse_pixel_value(value: str, default_value: int) -> int:
    cleaned = value.strip().lower().removesuffix("px")
    try:
        return int(float(cleaned))
    except ValueError:
        return default_value


def safe_margin_passed(bounds: typing.Optional[dict[str, int]], image: dict[str, object], margin: int) -> bool:
    if bounds is None:
        return False
    return all([
        bounds["left"] >= margin,
        bounds["top"] >= margin,
        image["width"] - bounds["right"] >= margin,
        image["height"] - bounds["bottom"] >= margin,
    ])


def edge_overflow_passed(bounds: typing.Optional[dict[str, int]], image: dict[str, object]) -> bool:
    if bounds is None:
        return False
    edge = max(8, round(min(image["width"], image["height"]) * 0.015))
    return bounds["left"] > edge and bounds["top"] > edge and image["width"] - bounds["right"] > edge and image["height"] - bounds["bottom"] > edge


def text_overflow_risk(slide_text: dict[str, object]) -> bool:
    return int(slide_text["textCharacterCount"]) > TEXT_OVERFLOW_CHARACTER_LIMIT or int(slide_text["textLineCount"]) > TEXT_OVERFLOW_LINE_LIMIT


def frame_fit_risk(bounds: typing.Optional[dict[str, int]], image: dict[str, object], margin: int) -> bool:
    if bounds is None:
        return False
    clearance = max(round(margin * 1.75), 36)
    right_clearance = image["width"] - bounds["right"]
    bottom_clearance = image["height"] - bounds["bottom"]
    return right_clearance < clearance or bottom_clearance < clearance


def slide_warnings(checks: dict[str, bool], margin: int, density: float, risks: dict[str, bool], structure: dict[str, object]) -> list[str]:
    warnings = []
    if not checks["nonblank"]:
        warnings.append("slide render appears blank")
    if not checks["safeMargin"]:
        warnings.append(f"content extends inside the recommended safe margin of {margin}px")
    if not checks["edgeOverflow"]:
        warnings.append("content touches the slide edge and may be clipped")
    if not checks["notTooEmpty"]:
        warnings.append(f"slide appears too sparse for a finished deck (content density {density:.1%})")
    if not checks["notTooDense"]:
        warnings.append(f"slide appears visually crowded (content density {density:.1%})")
    if risks["textOverflowRisk"]:
        warnings.append("textOverflowRisk: extracted slide text is long enough to require contact sheet verification")
    if risks["frameFitRisk"]:
        warnings.append("frameFitRisk: rendered content is close to the right or bottom frame edge")
    warnings.extend(slide_design_warnings(structure))
    return warnings


def slide_design_warnings(structure: dict[str, object]) -> list[str]:
    warnings = []
    if not structure["hasSlideRole"]:
        warnings.append("missingSlideRoleWarning: slide lacks data-slide-role, so its job is not explicit")
    if has_generic_topic_title(structure):
        warnings.append("topicTitleWarning: title reads as a topic label rather than a claim with a conclusion")
    if slide_is_table_dominated(structure):
        warnings.append("rawTableWarning: a raw table is the slide's primary composition")
    if slide_is_list_dominated(structure):
        warnings.append("bareListWarning: a bare list is the slide's primary composition")
    return warnings


def slide_is_table_dominated(structure: dict[str, object]) -> bool:
    return bool(structure["hasTable"]) and float(structure["tableTextRatio"]) >= STRUCTURE_DOMINANCE_RATIO


def slide_is_list_dominated(structure: dict[str, object]) -> bool:
    return bool(structure["hasList"]) and float(structure["listTextRatio"]) >= STRUCTURE_DOMINANCE_RATIO


def has_generic_topic_title(structure: dict[str, object]) -> bool:
    if str(structure["slideRole"]) in LABEL_ONLY_SLIDE_ROLES:
        return False
    return title_reads_as_topic_label(str(structure["title"]))


def title_reads_as_topic_label(title: str) -> bool:
    stripped = strip_parenthetical(title).strip()
    if not stripped:
        return False
    if stripped[-1] in ".!?…":
        return False
    if stripped.rstrip("\"'」』 ").endswith(KOREAN_SENTENCE_ENDINGS):
        return False
    return len(stripped.split()) < CLAIM_TITLE_WORD_MINIMUM


def strip_parenthetical(title: str) -> str:
    return re.sub(r"\s*[(（][^)）]*[)）]\s*", " ", title).strip()


def apply_deck_design_warnings(slides: list[dict[str, object]], source_context: dict[str, object], render_source: str) -> None:
    table_or_list_count = sum(1 for slide in slides if slide_has_dominant_raw_structure(slide))
    repeated_composition_count = repeated_composition_slide_count(slides)
    if not source_has_visual_identity(source_context):
        missing_parts = []
        if not source_context["hasVisualSystemAttribute"]:
            missing_parts.append("a data-visual-system attribute in slides.html")
        if int(source_context["designDocumentBodyCharacterCount"]) < DESIGN_DOCUMENT_BODY_MINIMUM_CHARACTERS:
            missing_parts.append("a DESIGN.md body that describes the visual system")
        append_deck_warning(slides, "weakVisualIdentityWarning: deck lacks " + " and ".join(missing_parts))
    if int(source_context["missingSlideRoleCount"]) > 0:
        append_deck_warning(slides, "missingSlideRoleWarning: one or more slide sections lack data-slide-role")
    if render_source != "browser":
        append_deck_warning(slides, "unreliableVisualEvidenceWarning: review images did not come from browser rendering")
    if source_context["hasSideStripePattern"]:
        append_deck_warning(slides, "sideStripeWarning: thick left or right border accents are doing the visual-identity work")
    if source_context["hasGhostCardPattern"]:
        append_deck_warning(slides, "ghostCardWarning: thin-bordered boxes with soft shadows read as a default template surface")
    if source_context["hasTinyTextPattern"]:
        append_deck_warning(slides, "tinyTextWarning: multiple CSS font sizes below 16px may be unreadable in review contact sheets")
    if int(source_context["absoluteTextFooterSlideCount"]) >= 2:
        append_deck_warning(
            slides,
            "absoluteFooterWarning: an absolutely positioned bottom strip carries text on multiple slides and can overlap the body; make header, body, and footer sibling flow children",
        )
    if repeated_composition_count >= 3:
        append_deck_warning(
            slides,
            f"repeatedCompositionWarning: {repeated_composition_count} slides share the same composition classes; vary slide composition",
        )
    if table_or_list_count >= 2:
        append_deck_warning(slides, "rawStructurePatternWarning: multiple slides use a raw table or bare list as the primary composition")


HANGUL_PATTERN = re.compile(r"[가-힣]")
LATIN_LETTER_PATTERN = re.compile(r"[A-Za-z]")


def apply_language_mismatch_warning(slides: list[dict[str, object]], slide_texts: list[dict[str, object]]) -> None:
    deck_text = "\n".join(str(slide_text["expectedVisibleText"]) for slide_text in slide_texts)
    if not deck_text_is_korean(deck_text):
        return
    mismatched_indexes = [
        str(slide_text["index"])
        for slide_text in slide_texts
        if str(slide_text["structure"]["slideRole"]) not in LABEL_ONLY_SLIDE_ROLES
        and title_is_latin_only(str(slide_text["structure"]["title"]))
    ]
    if mismatched_indexes:
        append_deck_warning(
            slides,
            "languageMismatchWarning: slide " + ", ".join(mismatched_indexes)
            + " titles are Latin-only while the deck text is Korean; write slide titles in the request language",
        )


def deck_text_is_korean(text: str) -> bool:
    hangul_count = len(HANGUL_PATTERN.findall(text))
    latin_count = len(LATIN_LETTER_PATTERN.findall(text))
    return hangul_count >= 40 and hangul_count * 3 >= latin_count


def title_is_latin_only(title: str) -> bool:
    return len(LATIN_LETTER_PATTERN.findall(title)) >= 4 and not HANGUL_PATTERN.search(title)


def apply_unsourced_current_date_warning(
    slides: list[dict[str, object]],
    slide_texts: list[dict[str, object]],
    required_text_ledger: str,
) -> None:
    today = datetime.date.today()
    date_pattern = current_date_pattern(today)
    if date_pattern.search(required_text_ledger):
        return
    dated_indexes = [
        str(slide_text["index"])
        for slide_text in slide_texts
        if date_pattern.search(str(slide_text["expectedVisibleText"]))
    ]
    if dated_indexes:
        append_deck_warning(
            slides,
            "unsourcedCurrentDateWarning: slide " + ", ".join(dated_indexes)
            + f" shows today's date {today.isoformat()}, which is not in required-visible-text.txt; only show dates from the source material",
        )


def apply_missing_required_text_warning(
    slides: list[dict[str, object]],
    slide_texts: list[dict[str, object]],
    required_text_ledger: str,
) -> None:
    ledger_lines = [line.strip() for line in required_text_ledger.splitlines() if line.strip()]
    if not ledger_lines:
        return
    deck_text = normalize_for_coverage("\n".join(str(slide_text["expectedVisibleText"]) for slide_text in slide_texts))
    spaceless_deck_text = deck_text.replace(" ", "")
    missing_lines = [
        line
        for line in ledger_lines
        if normalize_for_coverage(line) not in deck_text
        and normalize_for_coverage(line).replace(" ", "") not in spaceless_deck_text
    ]
    if missing_lines:
        preview = "; ".join(missing_lines[:4]) + (" ..." if len(missing_lines) > 4 else "")
        append_deck_warning(
            slides,
            f"missingRequiredTextWarning: {len(missing_lines)} of {len(ledger_lines)} required-visible-text.txt lines are not visible in the deck: {preview}",
        )


def normalize_for_coverage(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


FOOTER_BASELINE_VARIANCE_RATIO = 0.05
FOOTER_CANDIDATE_MINIMUM_SLIDES = 3
FOOTER_CANDIDATE_MINIMUM_SHARE = 0.6
VOID_HTML_TAGS = {"img", "br", "hr", "meta", "input", "link", "source", "track", "wbr", "area", "base", "col", "embed"}


class DirectChildScanner(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.direct_children = []

    def handle_starttag(self, tag, attributes):
        if self.depth == 1:
            self.direct_children.append((tag, dict(attributes)))
        if tag not in VOID_HTML_TAGS:
            self.depth += 1

    def handle_startendtag(self, tag, attributes):
        if self.depth == 1:
            self.direct_children.append((tag, dict(attributes)))

    def handle_endtag(self, tag):
        if tag not in VOID_HTML_TAGS:
            self.depth = max(0, self.depth - 1)


def last_direct_child(slide_source: str) -> typing.Optional[tuple[str, dict]]:
    scanner = DirectChildScanner()
    try:
        scanner.feed(slide_source)
    except Exception:
        return None
    for child in reversed(scanner.direct_children):
        if not is_speaker_note_child(child):
            return child
    return None


def is_speaker_note_child(child: tuple[str, dict]) -> bool:
    tag, attributes = child
    if tag == "aside" or "data-speaker-notes" in attributes:
        return True
    return "notes" in str(attributes.get("class") or "")


def footer_identity(child: typing.Optional[tuple[str, dict]]) -> str:
    if child is None:
        return ""
    tag, attributes = child
    if tag == "footer":
        return "footer"
    class_value = str(attributes.get("class") or "").strip()
    if class_value:
        return "." + class_value.split()[0]
    return ""


def apply_unpinned_footer_warning(slides: list[dict[str, object]], source_text: str) -> None:
    slide_sources = split_slide_sources(source_text)
    if len(slide_sources) < FOOTER_CANDIDATE_MINIMUM_SLIDES:
        return
    last_children = [last_direct_child(slide_source) for slide_source in slide_sources]
    identities = [footer_identity(child) for child in last_children]
    candidate = most_common_footer_identity(identities)
    if not candidate:
        return
    footer_rule_text = collect_rule_text(source_text, candidate)
    inline_styles = " ".join(
        str(child[1].get("style") or "")
        for child, identity in zip(last_children, identities)
        if child is not None and identity == candidate
    )
    if re.search(r"position\s*:\s*absolute", footer_rule_text + inline_styles, flags=re.IGNORECASE):
        return
    if re.search(r"margin-top\s*:\s*auto", footer_rule_text + inline_styles, flags=re.IGNORECASE):
        return
    if grow_class_present_on_footer_slides(source_text, slide_sources, identities, candidate):
        return
    append_deck_warning(
        slides,
        f"unpinnedFooterWarning: the recurring bottom element {candidate} is not pinned to the frame bottom; give it margin-top: auto (or grow the body with flex: 1) inside the flex column slide",
    )


SPEAKER_NOTES_PATTERN = re.compile(
    r"<aside\b[^>]*(?:class=[\"'][^\"']*notes[^\"']*[\"']|role=[\"']note[\"'])|data-speaker-notes",
    flags=re.IGNORECASE,
)


def apply_missing_speaker_notes_warning(slides: list[dict[str, object]], source_text: str) -> None:
    slide_sources = split_slide_sources(source_text)
    if not slide_sources:
        return
    missing_indexes = [
        str(index)
        for index, slide_source in enumerate(slide_sources, start=1)
        if not SPEAKER_NOTES_PATTERN.search(slide_source)
    ]
    if missing_indexes:
        append_deck_warning(
            slides,
            "missingSpeakerNotesWarning: slide " + ", ".join(missing_indexes)
            + " lacks an <aside class=\"notes\"> speaker script the presenter can read aloud",
        )


def most_common_footer_identity(identities: list[str]) -> str:
    counts: dict[str, int] = {}
    for identity in identities:
        if identity:
            counts[identity] = counts.get(identity, 0) + 1
    if not counts:
        return ""
    candidate, count = max(counts.items(), key=lambda pair: pair[1])
    if count < FOOTER_CANDIDATE_MINIMUM_SLIDES or count < len(identities) * FOOTER_CANDIDATE_MINIMUM_SHARE:
        return ""
    return candidate


def collect_rule_text(source_text: str, identity: str) -> str:
    if identity.startswith("."):
        selector_pattern = re.escape(identity)
    else:
        selector_pattern = rf"(?:^|[,\s}}]){re.escape(identity)}"
    parts = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", source_text):
        if re.search(selector_pattern, match.group(1)):
            parts.append(match.group(2))
    return "\n".join(parts)


def grow_class_present_on_footer_slides(
    source_text: str,
    slide_sources: list[str],
    identities: list[str],
    candidate: str,
) -> bool:
    grow_classes = set()
    for match in re.finditer(r"\.([\w-]+)[^{}]*\{([^{}]*)\}", source_text):
        if re.search(r"\bflex\s*:\s*1\b|\bflex-grow\s*:\s*[1-9]", match.group(2)):
            grow_classes.add(match.group(1).casefold())
    if not grow_classes:
        return False
    for slide_source, identity in zip(slide_sources, identities):
        if identity != candidate:
            continue
        slide_classes = set(extract_class_names(slide_source))
        if not (slide_classes & grow_classes):
            return False
    return True


def apply_footer_baseline_warning(slides: list[dict[str, object]]) -> None:
    content_slides = [
        slide
        for slide in slides
        if slide["hasRenderEvidence"]
        and slide["contentBounds"]
        and str(slide["structure"]["slideRole"]) not in LABEL_ONLY_SLIDE_ROLES
    ]
    if len(content_slides) < 3:
        return
    bottoms = [int(slide["contentBounds"]["bottom"]) for slide in content_slides]
    height = max(int(slide["height"]) for slide in content_slides)
    variance = max(bottoms) - min(bottoms)
    if variance > height * FOOTER_BASELINE_VARIANCE_RATIO:
        append_deck_warning(
            slides,
            f"inconsistentFooterBaselineWarning: the content bottom edge varies by {variance}px across slides; keep the footer on the same baseline on every slide",
        )


EMOJI_PATTERN = re.compile("[\U0001F000-\U0001FAFF✅❌❎❗❓⭐⚠⌚⏰️]")


def apply_emoji_icon_warning(slides: list[dict[str, object]], slide_texts: list[dict[str, object]]) -> None:
    emoji_indexes = [
        str(slide_text["index"])
        for slide_text in slide_texts
        if EMOJI_PATTERN.search(str(slide_text["expectedVisibleText"]))
    ]
    if emoji_indexes:
        append_deck_warning(
            slides,
            "emojiIconWarning: slide " + ", ".join(emoji_indexes)
            + " uses emoji glyphs; use text labels, CSS markers, or inline SVG instead",
        )


def current_date_pattern(today: datetime.date) -> re.Pattern[str]:
    separator = r"\s*[.\-/년월]\s*"
    return re.compile(rf"(?<!\d){today.year}{separator}0?{today.month}{separator}0?{today.day}(?!\d)")


def design_document_body(design_document_text: str) -> str:
    if design_document_text.startswith("---"):
        parts = design_document_text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return design_document_text.strip()


def source_has_visual_identity(source_context: dict[str, object]) -> bool:
    return (
        bool(source_context["hasVisualSystemAttribute"])
        and int(source_context["designDocumentBodyCharacterCount"]) >= DESIGN_DOCUMENT_BODY_MINIMUM_CHARACTERS
    )


def slide_has_dominant_raw_structure(slide: dict[str, object]) -> bool:
    structure = slide["structure"]
    return slide_is_table_dominated(structure) or slide_is_list_dominated(structure)


def repeated_composition_slide_count(slides: list[dict[str, object]]) -> int:
    if len(slides) < 3:
        return 0
    signatures = [frozenset(slide["structure"]["classNames"]) for slide in slides]
    universal_classes = frozenset.intersection(*signatures)
    distinctive_signatures = [signature - universal_classes for signature in signatures]
    counts: dict[frozenset, int] = {}
    for signature in distinctive_signatures:
        if signature:
            counts[signature] = counts.get(signature, 0) + 1
    return max(counts.values(), default=0)


def append_deck_warning(slides: list[dict[str, object]], warning: str) -> None:
    for slide in slides:
        if warning not in slide["warnings"]:
            slide["warnings"].append(warning)


def annotate_design_revision_need(slides: list[dict[str, object]]) -> None:
    for slide in slides:
        slide["needsDesignRevision"] = any(is_design_warning(warning) for warning in slide["warnings"])


def unique_design_warnings(slides: list[dict[str, object]]) -> list[str]:
    warnings = []
    for slide in slides:
        for warning in slide["warnings"]:
            if is_design_warning(warning) and warning not in warnings:
                warnings.append(warning)
    return warnings


def calculate_visual_quality_score(design_warnings: list[str]) -> int:
    score = 100
    for warning in design_warnings:
        score -= design_warning_weight(warning)
    return max(0, min(100, score))


def design_warning_weight(warning: str) -> int:
    for prefix, weight in DESIGN_WARNING_WEIGHTS.items():
        if warning.startswith(prefix):
            return weight
    return 6


def is_design_warning(warning: str) -> bool:
    return warning.startswith(DESIGN_WARNING_PREFIXES)


def write_contact_sheets(review_directory_path: pathlib.Path, deck_name: str, image_paths: list[pathlib.Path]) -> list[dict[str, object]]:
    contact_sheets = []
    for group_index in range(0, len(image_paths), CONTACT_SHEET_GROUP_SIZE):
        group_paths = image_paths[group_index:group_index + CONTACT_SHEET_GROUP_SIZE]
        sheet_path = review_directory_path / f"contact-sheet-{(group_index // CONTACT_SHEET_GROUP_SIZE) + 1:02d}.png"
        slide_numbers = list(range(group_index + 1, group_index + len(group_paths) + 1))
        sheet = compose_contact_sheet(group_paths, slide_numbers)
        write_png(sheet_path, sheet["width"], sheet["height"], sheet["rows"])
        contact_sheets.append({
            "filename": sheet_path.name,
            "slideNumbers": slide_numbers,
        })
    return contact_sheets


def create_fit_reviews(contact_sheets: list[dict[str, object]], slides: list[dict[str, object]]) -> list[dict[str, object]]:
    fit_reviews = []
    for sheet_index, contact_sheet in enumerate(contact_sheets, start=1):
        filename = f"fit-review-{sheet_index:02d}.md"
        group_slides = [slides[number - 1] for number in contact_sheet["slideNumbers"] if number - 1 < len(slides)]
        review = {
            "filename": filename,
            "contactSheetFilename": contact_sheet["filename"],
            "slideNumbers": contact_sheet["slideNumbers"],
            "reviewPrompt": FIT_REVIEW_PROMPT,
            "slides": [fit_review_slide(slide) for slide in group_slides],
        }
        fit_reviews.append(review)
    return fit_reviews


def write_fit_reviews(review_directory_path: pathlib.Path, fit_reviews: list[dict[str, object]]) -> None:
    for fit_review in fit_reviews:
        write_fit_review_markdown(review_directory_path / fit_review["filename"], fit_review)
    write_json(review_directory_path / "fit-review.json", {
        "reviewPrompt": FIT_REVIEW_PROMPT,
        "filenamePattern": FIT_REVIEW_FILE_PATTERN,
        "groups": fit_reviews,
    })


def fit_review_slide(slide: dict[str, object]) -> dict[str, object]:
    return {
        "index": slide["index"],
        "expectedVisibleText": slide["expectedVisibleText"],
        "textCharacterCount": slide["textCharacterCount"],
        "textLineCount": slide["textLineCount"],
        "textPreview": slide["textPreview"],
        "warnings": slide["warnings"],
        "needsDesignRevision": slide["needsDesignRevision"],
        "risks": slide["risks"],
        "structure": slide["structure"],
    }


def attach_fit_review_metadata(contact_sheets: list[dict[str, object]], fit_reviews: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        contact_sheet | {
            "fitReviewFilename": fit_review["filename"],
            "slideTextSummary": fit_review_text_summary(fit_review),
        }
        for contact_sheet, fit_review in zip(contact_sheets, fit_reviews)
    ]


def fit_review_text_summary(fit_review: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "index": slide["index"],
            "textPreview": slide["textPreview"],
            "textCharacterCount": slide["textCharacterCount"],
            "textLineCount": slide["textLineCount"],
        }
        for slide in fit_review["slides"]
    ]


def write_fit_review_markdown(path: pathlib.Path, review: dict[str, object]) -> None:
    lines = [
        f"# Fit Review {path.stem.removeprefix('fit-review-')}",
        "",
        f"- Contact sheet: {review['contactSheetFilename']}",
        f"- Slides: {', '.join(str(number) for number in review['slideNumbers'])}",
        f"- Check: {review['reviewPrompt']}",
        f"- Design check: {DESIGN_REVIEW_PROMPT}",
        "",
    ]
    for slide in review["slides"]:
        warning_text = "; ".join(slide["warnings"]) if slide["warnings"] else "none"
        lines.append(f"## Slide {slide['index']}")
        lines.append("")
        lines.append(f"- Text length: {slide['textCharacterCount']} chars, {slide['textLineCount']} lines")
        lines.append(f"- Deterministic warnings: {warning_text}")
        lines.append(f"- Needs design revision: {slide['needsDesignRevision']}")
        lines.append("")
        lines.append("Expected visible text:")
        lines.append("")
        lines.append("```text")
        lines.append(str(slide["expectedVisibleText"]) or "(no visible text extracted)")
        lines.append("```")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def compose_contact_sheet(image_paths: list[pathlib.Path], slide_numbers: list[int]) -> dict[str, object]:
    images = [read_png(path) for path in image_paths]
    thumbnail_width = CONTACT_SHEET_THUMBNAIL_WIDTH
    thumbnail_height = round(thumbnail_width * images[0]["height"] / images[0]["width"]) if images else 315
    columns = 2
    rows = max(1, (len(images) + columns - 1) // columns)
    padding = 24
    gutter = 18
    label_height = 34
    sheet_width = (thumbnail_width * columns) + (gutter * (columns - 1)) + (padding * 2)
    sheet_height = ((thumbnail_height + label_height) * rows) + (gutter * (rows - 1)) + (padding * 2)
    sheet_rows = [[(248, 250, 252, 255) for _ in range(sheet_width)] for _ in range(sheet_height)]
    for index, image in enumerate(images):
        column = index % columns
        row = index // columns
        x = padding + column * (thumbnail_width + gutter)
        y = padding + row * (thumbnail_height + label_height + gutter)
        thumbnail = resize_image(image, thumbnail_width, thumbnail_height)
        draw_number_badge(sheet_rows, x, y, slide_numbers[index])
        paste_image(sheet_rows, thumbnail, x, y + label_height)
        draw_frame(sheet_rows, x, y + label_height, thumbnail_width, thumbnail_height)
    return {"width": sheet_width, "height": sheet_height, "rows": sheet_rows}


def resize_image(image: dict[str, object], target_width: int, target_height: int) -> list[list[tuple[int, int, int, int]]]:
    rows = image["rows"]
    source_width = image["width"]
    source_height = image["height"]
    resized = []
    for target_y in range(target_height):
        source_y = min(source_height - 1, round(target_y * source_height / target_height))
        source_row = rows[source_y]
        resized_row = []
        for target_x in range(target_width):
            source_x = min(source_width - 1, round(target_x * source_width / target_width))
            resized_row.append(source_row[source_x])
        resized.append(resized_row)
    return resized


def paste_image(sheet_rows: list[list[tuple[int, int, int, int]]], image_rows: list[list[tuple[int, int, int, int]]], left: int, top: int) -> None:
    for y, row in enumerate(image_rows):
        target_row = sheet_rows[top + y]
        for x, pixel in enumerate(row):
            target_row[left + x] = pixel


def draw_frame(rows: list[list[tuple[int, int, int, int]]], left: int, top: int, width: int, height: int) -> None:
    color = (203, 213, 225, 255)
    for x in range(left, left + width):
        rows[top][x] = color
        rows[top + height - 1][x] = color
    for y in range(top, top + height):
        rows[y][left] = color
        rows[y][left + width - 1] = color


def draw_number_badge(rows: list[list[tuple[int, int, int, int]]], left: int, top: int, number: int) -> None:
    digits = str(number)
    scale = 4
    digit_width = 3 * scale
    badge_width = 20 + len(digits) * digit_width + max(0, len(digits) - 1) * scale
    badge_height = 26
    fill_rect(rows, left, top, badge_width, badge_height, (17, 24, 39, 230))
    cursor = left + 10
    for digit in digits:
        draw_digit(rows, cursor, top + 5, digit, scale, (255, 255, 255, 255))
        cursor += digit_width + scale


def fill_rect(rows: list[list[tuple[int, int, int, int]]], left: int, top: int, width: int, height: int, color: tuple[int, int, int, int]) -> None:
    for y in range(top, min(len(rows), top + height)):
        row = rows[y]
        for x in range(left, min(len(row), left + width)):
            row[x] = color


def draw_digit(rows: list[list[tuple[int, int, int, int]]], left: int, top: int, digit: str, scale: int, color: tuple[int, int, int, int]) -> None:
    glyph = digit_glyphs().get(digit, digit_glyphs()["0"])
    for y, line in enumerate(glyph):
        for x, value in enumerate(line):
            if value == "1":
                fill_rect(rows, left + x * scale, top + y * scale, scale, scale, color)


def digit_glyphs() -> dict[str, list[str]]:
    return {
        "0": ["111", "101", "101", "101", "111"],
        "1": ["010", "110", "010", "010", "111"],
        "2": ["111", "001", "111", "100", "111"],
        "3": ["111", "001", "111", "001", "111"],
        "4": ["101", "101", "111", "001", "001"],
        "5": ["111", "100", "111", "001", "111"],
        "6": ["111", "100", "111", "101", "111"],
        "7": ["111", "001", "001", "001", "001"],
        "8": ["111", "101", "111", "101", "111"],
        "9": ["111", "101", "111", "001", "111"],
    }


def write_json(path: pathlib.Path, report: dict[str, object]) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_png(path: pathlib.Path, width: int, height: int, rows: list[list[tuple[int, int, int, int]]]) -> None:
    raw_rows = []
    for row in rows:
        raw_row = bytearray([0])
        for red, green, blue, alpha in row:
            raw_row.extend([red, green, blue, alpha])
        raw_rows.append(bytes(raw_row))
    chunks = [
        png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
        png_chunk(b"IDAT", zlib.compress(b"".join(raw_rows))),
        png_chunk(b"IEND", b""),
    ]
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"".join(chunks))


def png_chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
    return struct.pack(">I", len(chunk_data)) + chunk_type + chunk_data + struct.pack(">I", checksum)


def write_markdown(path: pathlib.Path, report: dict[str, object]) -> None:
    lines = [
        "# Slide Render Review",
        "",
        f"- Passed: {report['passed']}",
        f"- Quality gate passed: {report['qualityGatePassed']}",
        f"- Static gate passed: {report['staticGatePassed']}",
        f"- Visual quality score: {report['visualQualityScore']} / 100 (minimum {report['visualQualityScoreMinimum']})",
        f"- Visual evidence reliable: {report['visualEvidenceReliable']}",
        f"- Render source: {report['renderSource']}",
        f"- Needs design revision: {report['needsDesignRevision']}",
        f"- Slide count: {report['slideCount']}",
        f"- Rendered slide count: {report['renderedSlideCount']}",
        f"- Contact sheets: {', '.join(sheet['filename'] for sheet in report['contactSheets'])}",
        f"- Fit reviews: {', '.join(review['filename'] for review in report['fitReviews'])}",
        "",
        "## Fit Review Instructions",
        "",
        FIT_REVIEW_PROMPT,
        "",
        "## Design Review Instructions",
        "",
        str(report["designReviewPrompt"]),
        "",
    ]
    if report["needsDesignRevision"]:
        lines.extend([
            "## Design Revision Needed",
            "",
            "These warnings do not fail export, but they should trigger a design pass before delivery unless the user only asked for mechanical conversion.",
            "",
        ])
        for warning in report["designWarnings"]:
            lines.append(f"- {warning}")
        lines.append("")
    for slide in report["slides"]:
        status = "PASS" if slide["passed"] else ("WARN" if slide["hasRenderEvidence"] else "NO-RENDER")
        warning_text = "; ".join(slide["warnings"]) if slide["warnings"] else "none"
        lines.append(f"## Slide {slide['index']}: {status}")
        lines.append("")
        if slide["hasRenderEvidence"]:
            lines.append(f"- File: {slide['filename']}")
            lines.append(f"- Content density: {slide['contentDensity']:.1%}")
        else:
            lines.append("- File: (no render image; static source review only)")
        lines.append(f"- Text length: {slide['textCharacterCount']} chars, {slide['textLineCount']} lines")
        lines.append(f"- Warnings: {warning_text}")
        lines.append(f"- Needs design revision: {slide['needsDesignRevision']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
