from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import re
import unicodedata


SPACE = "[ 　]"
GAP = re.compile(rf"{SPACE}*_{{3,}}{SPACE}*|{SPACE}{{3,}}")
DATE_PART_GAP = rf"{SPACE}*_+{SPACE}*|{SPACE}{{2,}}"
DATE_SKELETON = re.compile(rf"(?P<century>\d{{1,3}})?(?P<year>{DATE_PART_GAP})년{SPACE}*?(?P<month>{DATE_PART_GAP})월{SPACE}*?(?P<day>{DATE_PART_GAP})일")
LABEL_END = ":："


@dataclass(frozen=True)
class TextBlank:
    kind: str
    label: str
    start: int
    end: int
    parts: dict = field(default_factory=dict)
    century: str = ""


def text_blanks(text: str) -> list[TextBlank]:
    dates = [date_blank(text, match) for match in DATE_SKELETON.finditer(text)]
    taken = [(blank.start, blank.end) for blank in dates]
    gaps = [gap for gap in (gap_blank(text, match) for match in GAP.finditer(text) if not overlaps(match.span(), taken)) if gap is not None]
    return sorted(dates + gaps, key=lambda blank: blank.start)


def overlaps(span: tuple[int, int], taken: list[tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in taken)


def label_before(text: str, position: int) -> str:
    line_start = text.rfind("\n", 0, position) + 1
    previous = GAP.search(text[line_start:position][::-1])
    segment = text[line_start:position] if previous is None else text[position - previous.start():position]
    return re.sub(r"\s+", " ", segment).strip().rstrip(LABEL_END).strip()


def has_letter(text: str) -> bool:
    return re.search(r"[^\W\d_]", text) is not None


def ends_line(text: str, position: int) -> bool:
    return position >= len(text) or text[position] == "\n"


def is_letter_spacing(text: str, match: re.Match) -> bool:
    before = text[:match.start()].split()
    after = text[match.end():].split()
    return bool(before and after) and len(before[-1]) == 1 and len(after[0]) == 1


def gap_blank(text: str, match: re.Match) -> TextBlank | None:
    label = label_before(text, match.start())
    if not has_letter(label) or is_letter_spacing(text, match):
        return None
    preceding = text[:match.start()].rstrip()
    if ends_line(text, match.end()) and "_" not in match.group() and not preceding.endswith(tuple(LABEL_END)):
        return None
    return TextBlank("text", label, match.start(), match.end())


def date_blank(text: str, match: re.Match) -> TextBlank:
    label = label_before(text, match.start())
    shown = label if has_letter(label) else re.sub(r"\s+", " ", match.group()).strip()
    parts = {part: match.span(part) for part in ("year", "month", "day")}
    return TextBlank("date", shown, match.start(), match.end(), parts, match.group("century") or "")


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(character) in "WF" else 1 for character in text)


def text_in_gap(value: str, gap: str) -> str:
    return " " + value + " " * max(1, display_width(gap) - display_width(value) - 1)


def date_parts(blank: TextBlank, value: date, text: str) -> list[tuple[int, int, str]]:
    year = str(value.year)
    year_text = year[len(blank.century):] if blank.century and year.startswith(blank.century) else year
    year_start = blank.start if blank.century and not year.startswith(blank.century) else blank.parts["year"][0]
    if not blank.century and year_start > 0 and not text[year_start - 1].isspace():
        year_text = " " + year_text
    return [(year_start, blank.parts["year"][1], year_text), (*blank.parts["month"], f" {value.month}"), (*blank.parts["day"], f" {value.day}")]


def replacements(text: str, filled: dict[int, object]) -> list[tuple[int, int, str]]:
    blanks = text_blanks(text)
    changes = []
    for index, value in filled.items():
        if index >= len(blanks) or value is None:
            continue
        blank = blanks[index]
        if blank.kind == "date" and isinstance(value, date):
            changes.extend(date_parts(blank, value, text))
        else:
            changes.append((blank.start, blank.end, text_in_gap(str(value), text[blank.start:blank.end])))
    return sorted(changes, reverse=True)


def filled_text(text: str, filled: dict[int, object]) -> str:
    for start, end, new in replacements(text, filled):
        text = text[:start] + new + text[end:]
    return text


def paragraph_text(paragraph) -> str:
    return "".join(run.text for run in paragraph.runs)


def fill_paragraph(paragraph, filled: dict[int, object]) -> None:
    for start, end, new in replacements(paragraph_text(paragraph), filled):
        replace_in_runs(paragraph.runs, start, end, new)


def replace_in_runs(runs: list, start: int, end: int, new: str) -> None:
    offset = 0
    for run in runs:
        text = run.text
        run_start, run_end = offset, offset + len(text)
        offset = run_end
        holds_start = run_start <= start < run_end
        cut_start, cut_end = max(start, run_start), min(end, run_end)
        if not holds_start and cut_start >= cut_end:
            continue
        run.text = text[:cut_start - run_start] + (new if holds_start else "") + text[cut_end - run_start:]
