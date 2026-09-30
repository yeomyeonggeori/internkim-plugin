import re

from native_rendering import (
    DATE_PATTERN,
    MISSING_SOURCE_TEXT,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    card_grid_cells,
    card_values,
    compact_source_line,
    native_slide_title,
    non_title_lines,
    normalize_text_for_comparison,
    table_cell_text,
    table_grid,
    table_row_fill,
    table_row_text_color,
    timeline_lines,
    visible_card_count,
)
from slide_model import SlideModel


RISK_SECTION_LABELS = {"증거:", "대응:", "evidence:", "response:"}
METRIC_COLUMN_CANDIDATES = {
    "metric": ["metric", "지표"],
    "q1": ["q1", "q1 2026"],
    "q2": ["q2", "q2 2026"],
    "target": ["target", "목표"],
    "note": ["note", "비고"],
}
RISK_COLUMN_CANDIDATES = {
    "risk": ["risk", "리스크"],
    "evidence": ["evidence", "근거"],
    "response": ["response", "대응"],
}
METRIC_CARD_WIDTH = 462
METRIC_CARD_HEIGHT = 188
RISK_LEDGER_ROW_HEIGHT = 182


def draw_native_slide(canvas, model: SlideModel, colors: dict[str, str]) -> None:
    title = native_slide_title(model)
    if model.kind == "cover":
        draw_cover(canvas, model, title, colors)
        return
    canvas.add_rectangle(0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, colors["background"])
    canvas.add_rectangle(72, 42, 160, 6, colors["accent"])
    canvas.add_text(72, 70, 1280, 78, [title], 28, colors["ink"], True)
    draw_slide_body(canvas, model, colors)


def draw_cover(canvas, model: SlideModel, title: str, colors: dict[str, str]) -> None:
    canvas.add_rectangle(0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, "111827")
    canvas.add_rectangle(112, 108, 330, 8, colors["accent"])
    canvas.add_text(112, 146, 900, 220, [title], 36, "FFFFFF", True)
    canvas.add_text(116, 390, 870, 190, non_title_lines(model)[:4], 20, "E5E7EB")
    canvas.add_rectangle(1088, 150, 360, 210, "0F172A", "334155")
    canvas.add_text(1128, 190, 280, 44, ["BOARD REVIEW"], 16, "94A3B8", True)
    canvas.add_text(1128, 250, 280, 70, ["승인 필요"], 24, "FFFFFF", True)
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
        draw_timeline(canvas, timeline_lines(model), colors)
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
    values = card_values(lines)
    summary_items = summary_dashboard_items(values)
    canvas.add_rectangle(72, 172, 610, 510, "111827")
    canvas.add_text(112, 218, 520, 56, ["핵심 판단"], 23, "FFFFFF", True)
    canvas.add_text(112, 318, 520, 260, [summary_items["success"], summary_items["caution"]], 19, "E5E7EB")
    canvas.add_rectangle(720, 172, 810, 154, colors["surface"], colors["line"])
    canvas.add_text(754, 206, 720, 44, ["성과"], 16, colors["accent"], True)
    canvas.add_text(754, 252, 720, 44, [summary_items["success"]], 18, colors["ink"], True)
    canvas.add_rectangle(720, 354, 810, 154, colors["surface"], colors["line"])
    canvas.add_text(754, 388, 720, 44, ["주의"], 16, "B45309", True)
    canvas.add_text(754, 434, 720, 44, [summary_items["caution"]], 18, colors["ink"], True)
    canvas.add_rectangle(720, 536, 810, 146, "ECFDF5", colors["accent"])
    canvas.add_text(754, 568, 720, 40, ["요청"], 16, colors["accent"], True)
    canvas.add_text(754, 612, 720, 44, [summary_items["request"]], 18, colors["ink"], True)


def summary_dashboard_items(lines: list[str]) -> dict[str, str]:
    values = [strip_leading_label(line) for line in lines if line.strip()]
    success = first_matching_line(values, ["성과", "실적", "달성", "growth", "met"]) or first_available_line(values, 0)
    caution = first_matching_line(values, ["과제", "주의", "결함", "미달", "risk", "miss"]) or first_available_line(values, 1)
    request = first_matching_line(values, ["승인", "요청", "approve", "sign-off"]) or first_available_line(values, 2)
    return {
        "success": success or MISSING_SOURCE_TEXT,
        "caution": caution or MISSING_SOURCE_TEXT,
        "request": request or MISSING_SOURCE_TEXT,
    }


def strip_leading_label(value: str) -> str:
    cleaned_value = value.strip()
    for separator in (":", "："):
        if separator not in cleaned_value:
            continue
        label, content = cleaned_value.split(separator, 1)
        if len(label.strip()) <= 12 and content.strip():
            return content.strip()
    return cleaned_value


def first_matching_line(lines: list[str], needles: list[str]) -> str:
    for line in lines:
        normalized_line = normalize_text_for_comparison(line)
        if any(normalize_text_for_comparison(needle) in normalized_line for needle in needles):
            return line
    return ""


def first_available_line(lines: list[str], index: int) -> str:
    if index < len(lines):
        return lines[index]
    if lines:
        return lines[-1]
    return ""


def draw_metric_scoreboard(canvas, rows: list[list[str]], colors: dict[str, str]) -> None:
    if len(rows) < 2:
        draw_table(canvas, rows, 72, 170, 1456, 620, colors)
        return
    columns = table_column_indexes(rows[0], METRIC_COLUMN_CANDIDATES)
    canvas.add_rectangle(72, 164, 1456, 86, "111827")
    canvas.add_text(104, 190, 720, 40, ["목표 대비 Q2 판정"], 22, "FFFFFF", True)
    canvas.add_text(980, 194, 500, 34, ["actual / target / signal"], 14, "CBD5E1", False, "ctr")
    for index, row in enumerate(rows[1:6]):
        x = 72 + (index % 3) * (METRIC_CARD_WIDTH + 36)
        y = 292 + (index // 3) * (METRIC_CARD_HEIGHT + 34)
        draw_metric_card(canvas, x, y, row, columns, colors)


def draw_metric_card(canvas, x: int, y: int, row: list[str], columns: dict[str, int], colors: dict[str, str]) -> None:
    metric, q1, q2, target, note = (table_value(row, columns[name]) for name in ("metric", "q1", "q2", "target", "note"))
    status_fill = metric_status_color(note, target)
    text_width = METRIC_CARD_WIDTH - 56
    canvas.add_rectangle(x, y, METRIC_CARD_WIDTH, METRIC_CARD_HEIGHT, colors["surface"], colors["line"])
    canvas.add_rectangle(x, y, METRIC_CARD_WIDTH, 8, status_fill)
    canvas.add_text(x + 28, y + 26, text_width, 34, [metric], 15, colors["muted"], True)
    canvas.add_text(x + 28, y + 66, text_width, 54, [q2], 26, colors["ink"], True)
    canvas.add_text(x + 28, y + 128, text_width, 30, [f"Q1 {q1}  ·  목표 {target}"], 12, colors["muted"])
    canvas.add_text(x + 28, y + 158, text_width, 24, [note], 12, status_fill, True)


def draw_risk_ledger_from_table(canvas, rows: list[list[str]], colors: dict[str, str]) -> None:
    if len(rows) < 2:
        draw_table(canvas, rows, 72, 170, 1456, 620, colors)
        return
    columns = table_column_indexes(rows[0], RISK_COLUMN_CANDIDATES)
    canvas.add_rectangle(72, 170, 1456, 64, "111827")
    canvas.add_text(104, 190, 420, 28, ["리스크"], 16, "FFFFFF", True)
    canvas.add_text(610, 190, 340, 28, ["근거"], 16, "FFFFFF", True)
    canvas.add_text(1034, 190, 420, 28, ["대응"], 16, "FFFFFF", True)
    for row_index, row in enumerate(rows[1:5]):
        draw_risk_ledger_row(canvas, row_index, row, columns, colors)


def draw_risk_ledger_row(canvas, row_index: int, row: list[str], columns: dict[str, int], colors: dict[str, str]) -> None:
    y = 258 + row_index * (RISK_LEDGER_ROW_HEIGHT + 24)
    fill = colors["surface"] if row_index % 2 == 0 else "F1F5F9"
    canvas.add_rectangle(72, y, 1456, RISK_LEDGER_ROW_HEIGHT, fill, colors["line"])
    canvas.add_rectangle(94, y + 26, 118, 34, "FEF3C7", "", True)
    canvas.add_text(112, y + 34, 82, 18, ["ACTIVE"], 10, "92400E", True, "ctr")
    canvas.add_text(104, y + 76, 430, 72, [table_value(row, columns["risk"])], 16, colors["ink"], True)
    canvas.add_text(610, y + 44, 340, 92, [table_value(row, columns["evidence"])], 15, colors["ink"])
    canvas.add_text(1034, y + 44, 420, 92, [table_value(row, columns["response"])], 15, colors["ink"], True)


def table_column_indexes(header: list[str], column_candidates: dict[str, list[str]]) -> dict[str, int]:
    return {name: table_column_index(header, candidates) for name, candidates in column_candidates.items()}


def table_column_index(header: list[str], candidates: list[str]) -> int:
    normalized_header = [normalize_text_for_comparison(value) for value in header]
    for candidate in candidates:
        normalized_candidate = normalize_text_for_comparison(candidate)
        for index, value in enumerate(normalized_header):
            if normalized_candidate in value:
                return index
    return 0


def table_value(row: list[str], index: int) -> str:
    if index < 0 or index >= len(row):
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
    values = card_values(lines)
    card_count = visible_card_count(values)
    cells = card_grid_cells(card_count, (x, y), (width, height), columns)
    for index, (line, cell) in enumerate(zip(values, cells)):
        canvas.add_rectangle(cell.x, cell.y, cell.width, cell.height, colors["surface"], colors["line"])
        canvas.add_rectangle(cell.x, cell.y, cell.width, 8, colors["accent"])
        font_size = 17 if len(line) < 80 else 14
        canvas.add_text(cell.x + 30, cell.y + 28, cell.width - 56, cell.height - 52, [line], font_size, colors["ink"], index < 2)
    remaining_lines = values[card_count:]
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
        canvas.add_text(x, y + height + 10, width, 52, ["추가 표 행: " + " / ".join(" | ".join(row) for row in remaining_rows[:2])], 12, colors["muted"])


def draw_timeline(canvas, lines: list[str], colors: dict[str, str]) -> None:
    values = card_values(lines)
    canvas.add_rectangle(128, 430, 1344, 8, colors["line"])
    card_width = 410
    gap = 46
    for index, line in enumerate(values[:3]):
        x = 110 + index * (card_width + gap)
        canvas.add_rectangle(x, 230, card_width, 350, colors["surface"], colors["line"])
        date_match = re.search(DATE_PATTERN, line)
        date_text = date_match.group(0) if date_match else f"Step {index + 1}"
        canvas.add_rectangle(x + 28, 258, 170, 42, colors["accent"], "", True)
        canvas.add_text(x + 42, 266, 146, 26, [date_text], 13, "FFFFFF", True, "ctr")
        canvas.add_text(x + 28, 324, card_width - 56, 172, timeline_card_lines(line), 15, colors["ink"], True)
    if len(values) > 3:
        canvas.add_text(112, 640, 1320, 70, values[3:6], 16, colors["muted"])


def timeline_card_lines(line: str) -> list[str]:
    cells = [cell.strip() for cell in line.split("/") if cell.strip()]
    if len(cells) >= 4:
        return [cells[0], f"{cells[2]} · {cells[3]}"]
    return [line]


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
    if not values:
        return [[MISSING_SOURCE_TEXT]]
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
    values = card_values(lines)
    left_lines = values[::2] or values[:1]
    right_lines = values[1::2] or values[1:2] or values[:1]
    canvas.add_rectangle(72, 178, 700, 520, "111827")
    canvas.add_text(116, 226, 610, 70, ["승인 요청"], 24, "FFFFFF", True)
    canvas.add_text(116, 326, 610, 260, left_lines[:5], 18, "E5E7EB")
    canvas.add_rectangle(828, 178, 700, 520, colors["surface"], colors["line"])
    canvas.add_text(872, 226, 610, 70, ["다음 단계"], 24, colors["ink"], True)
    canvas.add_text(872, 326, 610, 260, right_lines[:5], 18, colors["ink"])
    canvas.add_text(88, 748, 1380, 56, values[10:14], 14, colors["muted"])
