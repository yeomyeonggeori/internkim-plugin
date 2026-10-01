from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from markdown_charts import FENCE, parse_chart_fence


HEADING_PATTERN = re.compile(r"^(#{1,4})\s+(.*)$")
LIST_PATTERN = re.compile(r"^(\s*)([-*]|\d+[.)])\s+(.*)$")
IMAGE_LINE_PATTERN = re.compile(r"^\s*!\[([^\]]*)\]\(([^)\s]+)\)\s*$")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
CHART_FENCE_OPENING = f"{FENCE}chart"
INLINE_PATTERN = re.compile(r"(\[[^\]]+\]\([^)\s]+\)|\*\*.+?\*\*|\*.+?\*|`.+?`)")


@dataclass(frozen=True)
class Heading:
    level: int
    text: str


@dataclass(frozen=True)
class Table:
    rows: list[list[str]]


@dataclass(frozen=True)
class ListItem:
    marker: str
    level: int
    text: str

    @property
    def is_numbered(self) -> bool:
        return self.marker not in ("-", "*")


@dataclass(frozen=True)
class Quote:
    text: str


@dataclass(frozen=True)
class Image:
    alt: str
    source: str


@dataclass(frozen=True)
class Paragraph:
    text: str


def parse_markdown(markdown_text: str) -> list:
    lines = markdown_text.splitlines()
    blocks = []
    list_indents: list[int] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.lower() == CHART_FENCE_OPENING:
            block, index = chart_block(lines, index)
            blocks.append(block)
            continue
        list_match = LIST_PATTERN.match(line)
        if not list_match:
            list_indents = []
        block, index = next_block(lines, index, list_match, list_indents)
        blocks.append(block)
    return blocks


def chart_block(lines: list[str], index: int):
    end = next((position for position in range(index + 1, len(lines)) if lines[position].strip() == FENCE), len(lines))
    return parse_chart_fence(lines[index + 1:end], index + 1), end + 1


def next_block(lines: list[str], index: int, list_match, list_indents: list[int]):
    line = lines[index]
    stripped = line.strip()
    heading_match = HEADING_PATTERN.match(stripped)
    if heading_match:
        return Heading(len(heading_match.group(1)), heading_match.group(2).strip()), index + 1
    if is_table_line(line):
        return table_block(lines, index)
    image_match = IMAGE_LINE_PATTERN.match(line)
    if image_match:
        return Image(image_match.group(1), image_match.group(2)), index + 1
    if list_match:
        return ListItem(list_match.group(2), list_level(list_indents, len(list_match.group(1))), list_match.group(3)), index + 1
    if stripped.startswith(">"):
        return Quote(stripped.lstrip("> ").strip()), index + 1
    return paragraph_block(lines, index)


def table_block(lines: list[str], index: int):
    table_lines = []
    while index < len(lines) and is_table_line(lines[index]):
        table_lines.append(lines[index])
        index += 1
    return Table([split_table_row(line) for line in table_lines if not is_divider_row(line)]), index


def paragraph_block(lines: list[str], index: int):
    paragraph_lines = []
    while index < len(lines) and continues_paragraph(lines[index]):
        paragraph_lines.append(lines[index].strip())
        index += 1
    return Paragraph(" ".join(paragraph_lines)), index


def continues_paragraph(line: str) -> bool:
    stripped = line.strip()
    if not stripped or HEADING_PATTERN.match(stripped) or is_table_line(line) or stripped.lower() == CHART_FENCE_OPENING:
        return False
    return not LIST_PATTERN.match(line) and not IMAGE_LINE_PATTERN.match(line)


def list_level(list_indents: list[int], indent: int) -> int:
    while list_indents and list_indents[-1] > indent:
        list_indents.pop()
    if not list_indents or list_indents[-1] < indent:
        list_indents.append(indent)
    return len(list_indents) - 1


def is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def is_divider_row(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:|-]+\|?", line.strip())) and "-" in line


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def inline_segments(text: str) -> list[str]:
    return [segment for segment in INLINE_PATTERN.split(text) if segment]


def link_parts(segment: str) -> tuple[str, str] | None:
    match = LINK_PATTERN.fullmatch(segment)
    return (match.group(1), match.group(2)) if match else None


def strip_inline_markers(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`", lambda match: next(group for group in match.groups() if group is not None), text)


def has_link(text: str) -> bool:
    return bool(LINK_PATTERN.search(text))


def local_image_problem(source: str, image_path: Path) -> str | None:
    if source.startswith(("http://", "https://")):
        return "is a remote URL, which export does not download"
    if not image_path.is_file():
        return "does not exist"
    return None
