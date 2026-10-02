from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from doc.blocks.charts import FENCE, parse_chart_fence


HEADING_PATTERN = re.compile(r"^(#{1,4})\s+(.*)$")
LIST_PATTERN = re.compile(r"^(\s*)([-*]|\d+[.)])\s+(.*)$")
THEMATIC_BREAK_PATTERN = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
IMAGE_LINE_PATTERN = re.compile(r"^\s*!\[([^\]]*)\]\(([^)\s]+)\)\s*$")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
CHART_FENCE_OPENING = f"{FENCE}chart"
INLINE_MATH = r"\$(?=[^\s$])(?:\\.|[^$\\\n])+?(?<=[^\s\\])\$(?!\d)"
INLINE_PATTERN = re.compile(rf"({INLINE_MATH}|\[[^\]]+\]\([^)\s]+\)|\*\*.+?\*\*|\*.+?\*|`.+?`)")
INLINE_MATH_PATTERN = re.compile(INLINE_MATH)
DISPLAY_MATH_FENCE = "$$"


@dataclass(frozen=True)
class Heading:
    level: int
    text: str


@dataclass(frozen=True)
class Table:
    rows: list[list[str]]
    alignments: tuple[str, ...] = ()


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


@dataclass(frozen=True)
class ThematicBreak:
    pass


@dataclass(frozen=True)
class CodeBlock:
    text: str
    language: str = ""


@dataclass(frozen=True)
class Equation:
    latex: str

    @property
    def text(self) -> str:
        return f"{DISPLAY_MATH_FENCE}{self.latex}{DISPLAY_MATH_FENCE}"


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
        if stripped.startswith(FENCE):
            block, index = code_block(lines, index)
            blocks.append(block)
            continue
        if stripped.startswith(DISPLAY_MATH_FENCE):
            block, index = equation_block(lines, index)
            blocks.append(block)
            continue
        if THEMATIC_BREAK_PATTERN.match(line):
            blocks.append(ThematicBreak())
            list_indents = []
            index += 1
            continue
        list_match = LIST_PATTERN.match(line)
        if not list_match:
            list_indents = []
        block, index = next_block(lines, index, list_match, list_indents)
        blocks.append(block)
    return blocks


def equation_block(lines: list[str], index: int):
    stripped = lines[index].strip()
    if len(stripped) > 2 * len(DISPLAY_MATH_FENCE) and stripped.endswith(DISPLAY_MATH_FENCE):
        return Equation(stripped[len(DISPLAY_MATH_FENCE):-len(DISPLAY_MATH_FENCE)].strip()), index + 1
    end = next((position for position in range(index + 1, len(lines)) if lines[position].strip().endswith(DISPLAY_MATH_FENCE)), len(lines) - 1)
    body = [stripped[len(DISPLAY_MATH_FENCE):], *(line.strip() for line in lines[index + 1:end]), lines[end].strip().removesuffix(DISPLAY_MATH_FENCE) if end > index else ""]
    return Equation(" ".join(part for part in body if part).strip()), end + 1


def chart_block(lines: list[str], index: int):
    end = next((position for position in range(index + 1, len(lines)) if lines[position].strip() == FENCE), len(lines))
    return parse_chart_fence(lines[index + 1:end], index + 1), end + 1


def code_block(lines: list[str], index: int):
    indent = len(lines[index]) - len(lines[index].lstrip())
    end = next((position for position in range(index + 1, len(lines)) if lines[position].strip() == FENCE), len(lines))
    body = [line[indent:] if not line[:indent].strip() else line.lstrip() for line in lines[index + 1:end]]
    return CodeBlock("\n".join(body), lines[index].strip()[len(FENCE):].strip()), end + 1


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
    dividers = [line for line in table_lines if is_divider_row(line)]
    alignments = tuple(column_alignment(cell) for cell in split_table_row(dividers[0])) if dividers else ()
    return Table([split_table_row(line) for line in table_lines if not is_divider_row(line)], alignments), index


def column_alignment(divider_cell: str) -> str:
    starts, ends = divider_cell.startswith(":"), divider_cell.endswith(":")
    if starts and ends:
        return "center"
    if ends:
        return "right"
    if starts:
        return "left"
    return ""


def paragraph_block(lines: list[str], index: int):
    paragraph_lines = []
    while index < len(lines) and continues_paragraph(lines[index]):
        paragraph_lines.append(lines[index].strip())
        index += 1
    return Paragraph("\n".join(paragraph_lines)), index


def continues_paragraph(line: str) -> bool:
    stripped = line.strip()
    if not stripped or HEADING_PATTERN.match(stripped) or is_table_line(line) or stripped.startswith(FENCE) or THEMATIC_BREAK_PATTERN.match(line) or stripped.startswith(DISPLAY_MATH_FENCE):
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


def math_latex(segment: str) -> str | None:
    return segment[1:-1] if INLINE_MATH_PATTERN.fullmatch(segment) else None


def link_parts(segment: str) -> tuple[str, str] | None:
    match = LINK_PATTERN.fullmatch(segment)
    return (match.group(1), match.group(2)) if match else None


def strip_inline_markers(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`", lambda match: next(group for group in match.groups() if group is not None), text)


def local_image_problem(source: str, image_path: Path) -> str | None:
    if source.startswith(("http://", "https://")):
        return "is a remote URL, which export does not download"
    if not image_path.is_file():
        return "does not exist"
    return None
