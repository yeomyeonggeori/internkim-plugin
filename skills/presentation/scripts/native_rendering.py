from dataclasses import dataclass
import re

from slide_model import SlideModel


SLIDE_WIDTH = 1600
SLIDE_HEIGHT = 900
MISSING_SOURCE_TEXT = "제공된 자료 없음"
DEFAULT_NATIVE_COLORS = {
    "background": "F8FAFC",
    "surface": "FFFFFF",
    "ink": "111827",
    "muted": "64748B",
    "accent": "0F766E",
    "line": "CBD5E1",
}
DATE_PATTERN = r"\d{4}-\d{2}-\d{2}"
CARD_GAP = 26
MAXIMUM_CARD_COUNT = 6
MAXIMUM_TABLE_ROW_COUNT = 8


@dataclass(frozen=True)
class CardCell:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class TableGrid:
    visible_rows: list[list[str]]
    column_count: int
    row_height: int
    column_width: int


def native_colors(design: dict[str, str]) -> dict[str, str]:
    return {
        key: normalize_hex_color(design.get("colors." + key, default_color), default_color)
        for key, default_color in DEFAULT_NATIVE_COLORS.items()
    }


def normalize_hex_color(value: str, default_value: str) -> str:
    cleaned_value = value.strip().removeprefix("#").upper()
    if re.fullmatch(r"[0-9A-F]{3}", cleaned_value):
        return "".join(character * 2 for character in cleaned_value)
    if re.fullmatch(r"[0-9A-F]{6}", cleaned_value):
        return cleaned_value
    return default_value


def non_title_lines(model: SlideModel) -> list[str]:
    title_text = normalize_text_for_comparison(model.title)
    lines = []
    for line in model.lines:
        if normalize_text_for_comparison(line) == title_text:
            continue
        if line not in lines:
            lines.append(line)
    return merge_label_value_lines(lines)


def merge_label_value_lines(lines: list[str]) -> list[str]:
    labels = []
    index = 0
    while index < len(lines) and is_label_line(lines[index]):
        labels.append(lines[index].rstrip(":：").strip())
        index += 1
    values = lines[index:]
    if len(labels) < 2 or len(values) < len(labels):
        return lines
    merged_lines = [f"{label}: {values[label_index]}" for label_index, label in enumerate(labels)]
    return merged_lines + values[len(labels):]


def is_label_line(value: str) -> bool:
    cleaned_value = value.strip()
    return cleaned_value.endswith((":", "：")) and len(cleaned_value) <= 16


def normalize_text_for_comparison(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def compact_source_line(model: SlideModel) -> list[str]:
    values = []
    for line in model.lines:
        if any(character.isdigit() for character in line) or MISSING_SOURCE_TEXT in line:
            values.append(line)
        if len(values) >= 3:
            break
    return values


def timeline_lines(model: SlideModel) -> list[str]:
    return [" / ".join(entry) for entry in timeline_entries(model)]


def timeline_entries(model: SlideModel) -> list[list[str]]:
    if model.tables:
        rows = model.tables[0][1:] if len(model.tables[0]) > 1 else model.tables[0]
        return [row for row in rows if row]
    dated_lines = [line for line in non_title_lines(model) if re.search(DATE_PATTERN, line)]
    if dated_lines:
        return [[line] for line in dated_lines]
    if model.list_items:
        return [[item] for item in model.list_items]
    return [[line] for line in non_title_lines(model)]


def card_grid_cells(card_count: int, origin: tuple[int, int], size: tuple[int, int], columns: int) -> list[CardCell]:
    x, y = origin
    width, height = size
    row_count = (card_count + columns - 1) // columns
    card_width = (width - CARD_GAP * (columns - 1)) // columns
    card_height = (height - CARD_GAP * (row_count - 1)) // row_count
    return [
        CardCell(
            x=x + (index % columns) * (card_width + CARD_GAP),
            y=y + (index // columns) * (card_height + CARD_GAP),
            width=card_width,
            height=card_height,
        )
        for index in range(card_count)
    ]


def visible_card_count(values: list[str]) -> int:
    return max(1, min(MAXIMUM_CARD_COUNT, len(values)))


def table_grid(rows: list[list[str]], width: int, height: int) -> TableGrid:
    visible_rows = rows[:MAXIMUM_TABLE_ROW_COUNT]
    column_count = max(len(row) for row in visible_rows)
    return TableGrid(
        visible_rows=visible_rows,
        column_count=column_count,
        row_height=max(52, min(86, height // max(1, len(visible_rows)))),
        column_width=width // max(1, column_count),
    )


def table_row_fill(row_index: int, colors: dict[str, str]) -> str:
    if row_index == 0:
        return colors["ink"]
    return colors["surface"] if row_index % 2 else "EEF2F7"


def table_row_text_color(row_index: int, colors: dict[str, str]) -> str:
    return "FFFFFF" if row_index == 0 else colors["ink"]


def table_cell_text(row: list[str], column_index: int) -> str:
    return row[column_index] if column_index < len(row) else ""
