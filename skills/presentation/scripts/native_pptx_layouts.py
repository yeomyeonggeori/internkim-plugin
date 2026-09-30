import re

from native_rendering import (
    DATE_PATTERN,
    MISSING_SOURCE_TEXT,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    card_grid_cells,
    compact_source_line,
    non_title_lines,
    normalize_text_for_comparison,
    table_cell_text,
    table_grid,
    table_row_fill,
    table_row_text_color,
    timeline_entries,
    visible_card_count,
)
from slide_model import SlideModel


RISK_SECTION_LABELS = {"증거:", "대응:", "evidence:", "response:"}
METRIC_NAME_CANDIDATES = ["metric", "지표"]
METRIC_TARGET_CANDIDATES = ["target", "목표"]
METRIC_NOTE_CANDIDATES = ["note", "비고"]
RISK_COLUMN_CANDIDATES = {
    "risk": ["risk", "리스크"],
    "evidence": ["evidence", "근거"],
    "response": ["response", "대응"],
}
METRIC_CARD_WIDTH = 462
METRIC_CARD_HEIGHT = 188
RISK_LEDGER_ROW_HEIGHT = 182
TIMELINE_CARD_WIDTH = 410


def draw_native_slide(canvas, model: SlideModel, colors: dict[str, str]) -> None:
    if model.kind == "cover":
        draw_cover(canvas, model, colors)
        return
    canvas.add_rectangle(0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, colors["background"])
    canvas.add_rectangle(72, 42, 160, 6, colors["accent"])
    canvas.add_text(72, 70, 1280, 78, [model.title], 28, colors["ink"], True)
    draw_slide_body(canvas, model, colors)


def draw_cover(canvas, model: SlideModel, colors: dict[str, str]) -> None:
    canvas.add_rectangle(0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, "111827")
    canvas.add_rectangle(112, 108, 330, 8, colors["accent"])
    canvas.add_text(112, 146, 900, 220, [model.title], 36, "FFFFFF", True)
    canvas.add_text(116, 390, 870, 190, non_title_lines(model)[:4], 20, "E5E7EB")
    canvas.add_rectangle(112, 676, 1180, 1, "334155")
    canvas.add_text(112, 724, 1120, 70, compact_source_line(model), 16, "CBD5E1")


def draw_slide_body(canvas, model: SlideModel, colors: dict[str, str]) -> None:
    if model.kind == "summary":
        draw_summary_dashboard(canvas, non_title_lines(model), colors)
        return
    if model.kind == "metrics" and model.tables:
        draw_metric_scoreboard(canvas, model.tables[0], colors)
        return
    if model.kind == "metrics":
        draw_line_cards(canvas, non_title_lines(model), 72, 170, 1456, 610, colors, 3)
        return
    if model.kind == "timeline":
        draw_timeline(canvas, timeline_entries(model), colors)
        return
    if model.kind == "risk" and model.tables:
        draw_risk_ledger_from_table(canvas, model.tables[0], colors)
        return
    if model.kind == "risk":
        draw_risk_panels(canvas, non_title_lines(model), colors)
        return
    if model.kind == "approval":
        draw_approval(canvas, non_title_lines(model), colors)
        return
    draw_line_cards(canvas, non_title_lines(model), 72, 170, 1456, 610, colors, 2)


def draw_summary_dashboard(canvas, lines: list[str], colors: dict[str, str]) -> None:
    if not lines:
        return
    canvas.add_rectangle(72, 172, 610, 510, "111827")
    canvas.add_text(112, 218, 520, 420, lines[:1], 23, "FFFFFF", True)
    for index, line in enumerate(lines[1:4]):
        y = 172 + index * 182
        canvas.add_rectangle(720, y, 810, 154, colors["surface"], colors["line"])
        canvas.add_text(754, y + 34, 720, 90, [line], 18, colors["ink"], True)


def draw_metric_scoreboard(canvas, rows: list[list[str]], colors: dict[str, str]) -> None:
    if len(rows) < 2:
        draw_table(canvas, rows, 72, 170, 1456, 620, colors)
        return
    columns = metric_columns(rows[0])
    for index, row in enumerate(rows[1:6]):
        x = 72 + (index % 3) * (METRIC_CARD_WIDTH + 36)
        y = 180 + (index // 3) * (METRIC_CARD_HEIGHT + 34)
        draw_metric_card(canvas, x, y, rows[0], row, columns, colors)


def metric_columns(header: list[str]) -> dict[str, object]:
    name_index = optional_column_index(header, METRIC_NAME_CANDIDATES) or 0
    target_index = optional_column_index(header, METRIC_TARGET_CANDIDATES)
    note_index = optional_column_index(header, METRIC_NOTE_CANDIDATES)
    value_indexes = [index for index in range(len(header)) if index not in {name_index, target_index, note_index}]
    reference_indexes = value_indexes[:-1] + ([] if target_index is None else [target_index])
    return {
        "name": name_index,
        "value": value_indexes[-1] if value_indexes else None,
        "references": reference_indexes,
        "target": target_index,
        "note": note_index,
    }


def draw_metric_card(canvas, x: int, y: int, header: list[str], row: list[str], columns: dict[str, object], colors: dict[str, str]) -> None:
    note = table_value(row, columns["note"])
    status_fill = metric_status_color(note, table_value(row, columns["target"]))
    text_width = METRIC_CARD_WIDTH - 56
    canvas.add_rectangle(x, y, METRIC_CARD_WIDTH, METRIC_CARD_HEIGHT, colors["surface"], colors["line"])
    canvas.add_rectangle(x, y, METRIC_CARD_WIDTH, 8, status_fill)
    canvas.add_text(x + 28, y + 26, text_width, 34, [table_value(row, columns["name"])], 15, colors["muted"], True)
    canvas.add_text(x + 28, y + 66, text_width, 54, [table_value(row, columns["value"])], 26, colors["ink"], True)
    canvas.add_text(x + 28, y + 128, text_width, 30, [metric_reference_line(header, row, columns["references"])], 12, colors["muted"])
    canvas.add_text(x + 28, y + 158, text_width, 24, [note], 12, status_fill, True)


def metric_reference_line(header: list[str], row: list[str], reference_indexes: list[int]) -> str:
    references = [
        f"{table_value(header, index)} {table_value(row, index)}"
        for index in reference_indexes
        if table_value(row, index)
    ]
    return "  ·  ".join(references)


def draw_risk_ledger_from_table(canvas, rows: list[list[str]], colors: dict[str, str]) -> None:
    if len(rows) < 2:
        draw_table(canvas, rows, 72, 170, 1456, 620, colors)
        return
    header = rows[0]
    columns = {name: optional_column_index(header, candidates) or 0 for name, candidates in RISK_COLUMN_CANDIDATES.items()}
    canvas.add_rectangle(72, 170, 1456, 64, "111827")
    canvas.add_text(104, 190, 420, 28, [table_value(header, columns["risk"])], 16, "FFFFFF", True)
    canvas.add_text(610, 190, 340, 28, [table_value(header, columns["evidence"])], 16, "FFFFFF", True)
    canvas.add_text(1034, 190, 420, 28, [table_value(header, columns["response"])], 16, "FFFFFF", True)
    for row_index, row in enumerate(rows[1:5]):
        draw_risk_ledger_row(canvas, row_index, row, columns, colors)


def draw_risk_ledger_row(canvas, row_index: int, row: list[str], columns: dict[str, int], colors: dict[str, str]) -> None:
    y = 258 + row_index * (RISK_LEDGER_ROW_HEIGHT + 24)
    fill = colors["surface"] if row_index % 2 == 0 else "F1F5F9"
    canvas.add_rectangle(72, y, 1456, RISK_LEDGER_ROW_HEIGHT, fill, colors["line"])
    canvas.add_text(104, y + 44, 430, 92, [table_value(row, columns["risk"])], 16, colors["ink"], True)
    canvas.add_text(610, y + 44, 340, 92, [table_value(row, columns["evidence"])], 15, colors["ink"])
    canvas.add_text(1034, y + 44, 420, 92, [table_value(row, columns["response"])], 15, colors["ink"], True)


def optional_column_index(header: list[str], candidates: list[str]) -> int | None:
    normalized_header = [normalize_text_for_comparison(value) for value in header]
    for candidate in candidates:
        normalized_candidate = normalize_text_for_comparison(candidate)
        for index, value in enumerate(normalized_header):
            if normalized_candidate in value:
                return index
    return None


def table_value(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index]


def metric_status_color(note: str, target: str) -> str:
    normalized_note = normalize_text_for_comparison(note)
    normalized_target = normalize_text_for_comparison(target)
    if "miss" in normalized_note or "미달" in normalized_note or "초과" in normalized_note:
        return "B45309"
    if "met" in normalized_note or "달성" in normalized_note:
        return "0F766E"
    if "not provided" in normalized_target or MISSING_SOURCE_TEXT in normalized_target:
        return "64748B"
    return "0F766E"


def draw_line_cards(canvas, lines: list[str], x: int, y: int, width: int, height: int, colors: dict[str, str], columns: int) -> None:
    card_count = visible_card_count(lines)
    cells = card_grid_cells(card_count, (x, y), (width, height), columns)
    for index, (line, cell) in enumerate(zip(lines, cells)):
        canvas.add_rectangle(cell.x, cell.y, cell.width, cell.height, colors["surface"], colors["line"])
        canvas.add_rectangle(cell.x, cell.y, cell.width, 8, colors["accent"])
        font_size = 17 if len(line) < 80 else 14
        canvas.add_text(cell.x + 30, cell.y + 28, cell.width - 56, cell.height - 52, [line], font_size, colors["ink"], index < 2)
    remaining_lines = lines[card_count:]
    if remaining_lines:
        canvas.add_text(x, y + height + 16, width, 56, remaining_lines[:3], 13, colors["muted"])


def draw_table(canvas, rows: list[list[str]], x: int, y: int, width: int, height: int, colors: dict[str, str]) -> None:
    grid = table_grid(rows, width, height)
    for row_index, row in enumerate(grid.visible_rows):
        row_y = y + row_index * grid.row_height
        fill = table_row_fill(row_index, colors)
        text_color = table_row_text_color(row_index, colors)
        for column_index in range(grid.column_count):
            cell_x = x + column_index * grid.column_width
            cell_text = table_cell_text(row, column_index)
            canvas.add_rectangle(cell_x, row_y, grid.column_width - 2, grid.row_height - 2, fill, colors["line"])
            canvas.add_text(cell_x + 16, row_y + 12, grid.column_width - 32, grid.row_height - 20, [cell_text], 14 if row_index else 15, text_color, row_index == 0)
    remaining_rows = rows[len(grid.visible_rows):]
    if remaining_rows:
        canvas.add_text(x, y + height + 10, width, 52, [" / ".join(" | ".join(row) for row in remaining_rows[:2])], 12, colors["muted"])


def draw_timeline(canvas, entries: list[list[str]], colors: dict[str, str]) -> None:
    if not entries:
        return
    canvas.add_rectangle(128, 430, 1344, 8, colors["line"])
    for index, entry in enumerate(entries[:3]):
        draw_timeline_card(canvas, 110 + index * (TIMELINE_CARD_WIDTH + 46), entry, colors)
    later_entries = [" / ".join(entry) for entry in entries[3:6]]
    if later_entries:
        canvas.add_text(112, 640, 1320, 70, later_entries, 16, colors["muted"])


def draw_timeline_card(canvas, x: int, entry: list[str], colors: dict[str, str]) -> None:
    canvas.add_rectangle(x, 230, TIMELINE_CARD_WIDTH, 350, colors["surface"], colors["line"])
    date_text = entry_date(entry)
    if date_text:
        canvas.add_rectangle(x + 28, 258, 170, 42, colors["accent"], "", True)
        canvas.add_text(x + 42, 266, 146, 26, [date_text], 13, "FFFFFF", True, "ctr")
    body_lines = [cell for cell in entry if cell != date_text] or entry
    canvas.add_text(x + 28, 324, TIMELINE_CARD_WIDTH - 56, 172, body_lines, 15, colors["ink"], True)


def entry_date(entry: list[str]) -> str:
    for cell in entry:
        date_match = re.search(DATE_PATTERN, cell)
        if date_match:
            return date_match.group(0)
    return ""


def draw_risk_panels(canvas, lines: list[str], colors: dict[str, str]) -> None:
    groups = group_risk_lines(lines)
    panel_width = 700
    panel_height = 220
    positions = [(72, 180), (828, 180), (72, 450), (828, 450)]
    for index, group in enumerate(groups[:4]):
        x, y = positions[index]
        canvas.add_rectangle(x, y, panel_width, panel_height, colors["surface"], colors["line"])
        canvas.add_rectangle(x, y, panel_width, 8, colors["accent"])
        canvas.add_text(x + 34, y + 30, panel_width - 68, 48, [group[0]], 20, colors["ink"], True)
        canvas.add_text(x + 34, y + 92, panel_width - 68, 96, group[1:], 15, colors["muted"])
    remaining_lines = [line for group in groups[4:] for line in group]
    if remaining_lines:
        canvas.add_text(88, 720, 1380, 60, remaining_lines[:4], 13, colors["muted"])


def group_risk_lines(lines: list[str]) -> list[list[str]]:
    values = [line for line in lines if line.strip()]
    if any(normalize_text_for_comparison(line) in RISK_SECTION_LABELS for line in values):
        return [values[index:index + 5] for index in range(0, len(values), 5)]
    groups = []
    current_group = []
    for line in values:
        if current_group and not normalize_text_for_comparison(line).endswith(":") and len(current_group) >= 3:
            groups.append(current_group)
            current_group = []
        current_group.append(line)
    if current_group:
        groups.append(current_group)
    return groups


def draw_approval(canvas, lines: list[str], colors: dict[str, str]) -> None:
    if not lines:
        return
    canvas.add_rectangle(72, 178, 700, 520, "111827")
    canvas.add_text(116, 226, 610, 420, lines[::2][:5], 18, "E5E7EB")
    canvas.add_rectangle(828, 178, 700, 520, colors["surface"], colors["line"])
    canvas.add_text(872, 226, 610, 420, lines[1::2][:5], 18, colors["ink"])
    canvas.add_text(88, 748, 1380, 56, lines[10:14], 14, colors["muted"])
