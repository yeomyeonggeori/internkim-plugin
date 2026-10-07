from __future__ import annotations

import re


FENCE = "---"
VALUE_LINE = re.compile(r"^\s*[A-Za-z][\w.-]*\s*:")


def parse_front_matter(design_document_text: str) -> dict[str, str | dict[str, str]]:
    document: dict[str, str | dict[str, str]] = {}
    section = ""
    for raw_line in design_front_matter(design_document_text).splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), unquoted(value)
        if not line.startswith((" ", "\t")):
            section = key if not value else ""
            document[key] = {} if not value else value
        elif section and isinstance(document.get(section), dict) and value:
            document[section][key] = value
    return document


def unquoted(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def design_front_matter(design_document_text: str) -> str:
    lines = front_matter_lines(design_document_text)
    return "" if lines is None else "\n".join(lines)


def front_matter_problem(design_document_text: str) -> str | None:
    lines = design_document_text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != FENCE:
        return "line 1 must be --- on its own, opening the front matter that holds the values"
    if front_matter_lines(design_document_text) is not None:
        return None
    return f"the front matter opened by --- on line 1 is never closed: put the closing --- on its own line at line {closing_line_number(lines)}, right after the last value"


def front_matter_lines(design_document_text: str) -> list[str] | None:
    lines = design_document_text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != FENCE:
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == FENCE:
            return lines[1:index]
    return None


def closing_line_number(lines: list[str]) -> int:
    last_value_index = 0
    for index, line in enumerate(lines[1:], start=1):
        if VALUE_LINE.match(line):
            last_value_index = index
        elif line.strip():
            break
    return last_value_index + 2
