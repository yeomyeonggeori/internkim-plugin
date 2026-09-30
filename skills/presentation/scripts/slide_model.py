from dataclasses import dataclass
import html
import pathlib
import re

from slide_source import SPEAKER_NOTES_BLOCK_PATTERN, remove_invisible_markup, slide_title, split_slide_sources


SLIDE_KIND_KEYWORDS = (
    ("summary", ["summary", "요약", "executive"]),
    ("approval", ["approval", "승인", "next step", "다음 단계", "요청"]),
    ("risk", ["risk", "리스크", "defect", "sla", "response", "대응"]),
    ("timeline", ["roadmap", "로드맵", "timeline", "milestone"]),
    ("metrics", ["metric", "지표", "revenue", "uptime", "target", "actual", "목표", "실제"]),
)


@dataclass(frozen=True)
class SlideModel:
    index: int
    title: str
    lines: list[str]
    tables: list[list[list[str]]]
    list_items: list[str]
    kind: str


def extract_slide_sources(source_path: pathlib.Path) -> list[str]:
    return split_slide_sources(source_path.read_text(encoding="utf-8"))


def create_slide_models(slide_sources: list[str]) -> list[SlideModel]:
    return [create_slide_model(index, slide_source) for index, slide_source in enumerate(slide_sources, start=1)]


def create_slide_model(index: int, slide_source: str) -> SlideModel:
    lines = slide_visible_lines(slide_source)
    title = slide_title(slide_source) or first_non_empty_line(lines, "")
    return SlideModel(
        index=index,
        title=title,
        lines=lines,
        tables=extract_tables(slide_source),
        list_items=extract_list_items(slide_source),
        kind=infer_slide_kind(index, title, lines),
    )


def slide_visible_lines(slide_source: str) -> list[str]:
    text = visible_text(remove_invisible_markup(slide_source))
    return [line for line in text.splitlines() if line.strip()]


def first_non_empty_line(lines: list[str], default_value: str) -> str:
    for line in lines:
        if line.strip():
            return line.strip()
    return default_value


def extract_tables(slide_source: str) -> list[list[list[str]]]:
    tables = []
    for table_match in re.finditer(r"<table\b[^>]*>(.*?)</table>", slide_source, flags=re.IGNORECASE | re.DOTALL):
        rows = extract_table_rows(table_match.group(1))
        if rows:
            tables.append(rows)
    return tables


def extract_table_rows(table_source: str) -> list[list[str]]:
    rows = []
    for row_match in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", table_source, flags=re.IGNORECASE | re.DOTALL):
        cells = inline_texts(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_match.group(1))
        if cells:
            rows.append(cells)
    return rows


def extract_list_items(slide_source: str) -> list[str]:
    return inline_texts(r"<li\b[^>]*>(.*?)</li>", slide_source)


def inline_texts(element_pattern: str, source: str) -> list[str]:
    texts = []
    for match in re.finditer(element_pattern, source, flags=re.IGNORECASE | re.DOTALL):
        text = visible_text(remove_invisible_markup(match.group(1))).replace("\n", " ").strip()
        if text:
            texts.append(text)
    return texts


def infer_slide_kind(index: int, title: str, lines: list[str]) -> str:
    if index == 1:
        return "cover"
    text = " ".join([title, *lines]).casefold()
    for kind, keywords in SLIDE_KIND_KEYWORDS:
        if contains_any(text, keywords):
            return kind
    return "content"


def contains_any(text: str, values: list[str]) -> bool:
    return any(value.casefold() in text for value in values)


def extract_notes(slide_source: str) -> str:
    matches = re.findall(SPEAKER_NOTES_BLOCK_PATTERN, slide_source, flags=re.IGNORECASE | re.DOTALL)
    return "\n".join(visible_text(match) for match in matches if visible_text(match)).strip()


def visible_text(source: str) -> str:
    source = re.sub(r"<script[^>]*>.*?</script>", " ", source, flags=re.IGNORECASE | re.DOTALL)
    source = re.sub(r"<style[^>]*>.*?</style>", " ", source, flags=re.IGNORECASE | re.DOTALL)
    source = re.sub(r"<[^>]+>", "\n", source)
    lines = [re.sub(r"\s+", " ", html.unescape(line)).strip() for line in source.splitlines()]
    return "\n".join(line for line in lines if line)

