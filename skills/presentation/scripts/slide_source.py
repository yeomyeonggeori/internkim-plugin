import html
import pathlib
import re


SPEAKER_NOTES_CLASS = "notes"
SPEAKER_NOTES_CLASS_ATTRIBUTE_PATTERN = rf"class=[\"'](?:[^\"']*\s)?{SPEAKER_NOTES_CLASS}(?:\s[^\"']*)?[\"']"
SPEAKER_NOTES_BLOCK_PATTERN = rf"<(?:aside|div)\b[^>]*{SPEAKER_NOTES_CLASS_ATTRIBUTE_PATTERN}[^>]*>(.*?)</(?:aside|div)>"


def read_optional_text(path: pathlib.Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def has_speaker_notes_class(class_value: str) -> bool:
    return SPEAKER_NOTES_CLASS in class_value.split()


def split_slide_sources(source_text: str) -> list[str]:
    sections = re.findall(r"<section\b[^>]*>.*?</section>", source_text, flags=re.IGNORECASE | re.DOTALL)
    return [section.strip() for section in sections if section.strip()]


def remove_invisible_markup(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(SPEAKER_NOTES_BLOCK_PATTERN, " ", text, flags=re.DOTALL | re.IGNORECASE)


def slide_title(slide_source: str) -> str:
    match = re.search(r"<(h[1-3])\b[^>]*>(.*?)</\1>", slide_source, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return single_line_text(match.group(2))


def single_line_text(markup: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "\n", markup))
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return " ".join(line for line in lines if line)


def slide_role(slide_source: str) -> str:
    return extract_section_attribute(slide_source, "data-slide-role")


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
