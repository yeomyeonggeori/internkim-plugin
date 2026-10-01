from __future__ import annotations

import pathlib
import sys

from native_rendering import (
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    card_grid_cells,
    compact_source_line,
    native_colors,
    non_title_lines,
    normalize_hex_color,
    table_cell_text,
    table_grid,
    table_row_fill,
    table_row_text_color,
    timeline_lines,
    visible_card_count,
)
from fonts.registry import BOLD_WEIGHT, DECK, REGULAR_WEIGHT, default_family
from slide_images import slide_image_filename
from slide_model import SlideModel



def write_native_review_images(slide_models: list[SlideModel], design: dict[str, str], review_path: pathlib.Path, deck_name: str) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[warning] Pillow is unavailable; native fallback review images were not created", file=sys.stderr, flush=True)
        return False
    review_path.mkdir(parents=True, exist_ok=True)
    colors = native_colors(design)
    fonts = {
        "title": preview_font(ImageFont, 46, True),
        "subtitle": preview_font(ImageFont, 28, True),
        "body": preview_font(ImageFont, 23, False),
        "small": preview_font(ImageFont, 17, False),
    }
    for model in slide_models:
        image = Image.new("RGB", (SLIDE_WIDTH, SLIDE_HEIGHT), hex_to_rgb("111827" if model.kind == "cover" else colors["background"]))
        draw = ImageDraw.Draw(image)
        draw_native_preview_slide(draw, model, colors, fonts)
        image.save(review_path / slide_image_filename(deck_name, model.index))
    return True


def preview_font(image_font_module, size: int, is_bold: bool):
    return image_font_module.truetype(str(preview_font_path(is_bold)), size)


def preview_font_path(is_bold: bool) -> pathlib.Path:
    family = default_family(DECK)
    return family.path(family.face(BOLD_WEIGHT if is_bold else REGULAR_WEIGHT))


def draw_native_preview_slide(draw, model: SlideModel, colors: dict[str, str], fonts: dict[str, object]) -> None:
    if model.kind == "cover":
        draw_preview_cover(draw, model, colors, fonts)
        return
    draw.rectangle((0, 0, SLIDE_WIDTH, 20), fill=hex_to_rgb(colors["accent"]))
    draw_wrapped_text(draw, model.title, (72, 58), 1280, fonts["subtitle"], hex_to_rgb(colors["ink"]), 1.2)
    if model.tables:
        draw_preview_table(draw, model.tables[0], (72, 170), (1456, 620), colors, fonts)
        return
    values = timeline_lines(model) if model.kind == "timeline" else non_title_lines(model)
    draw_preview_cards(draw, values, (72, 170), (1456, 610), colors, fonts, 3 if model.kind == "metrics" else 2)


def draw_preview_cover(draw, model: SlideModel, colors: dict[str, str], fonts: dict[str, object]) -> None:
    draw.rectangle((0, 0, 92, SLIDE_HEIGHT), fill=hex_to_rgb(colors["accent"]))
    draw.rectangle((1260, 96, 1480, 316), fill=hex_to_rgb("1F2937"))
    draw_wrapped_text(draw, model.title, (150, 130), 1080, fonts["title"], hex_to_rgb("FFFFFF"), 1.15)
    draw_wrapped_lines(draw, non_title_lines(model)[:7], (154, 360), 980, fonts["body"], hex_to_rgb("E5E7EB"), 1.35)
    draw.rectangle((150, 684, 450, 692), fill=hex_to_rgb(colors["accent"]))
    draw_wrapped_lines(draw, compact_source_line(model), (150, 735), 1120, fonts["small"], hex_to_rgb("9CA3AF"), 1.25)


def draw_preview_table(draw, rows: list[list[str]], origin: tuple[int, int], size: tuple[int, int], colors: dict[str, str], fonts: dict[str, object]) -> None:
    x, y = origin
    grid = table_grid(rows, *size)
    for row_index, row in enumerate(grid.visible_rows):
        fill = hex_to_rgb(table_row_fill(row_index, colors))
        text_color = hex_to_rgb(table_row_text_color(row_index, colors))
        cell_y = y + row_index * grid.row_height
        for column_index in range(grid.column_count):
            cell_x = x + column_index * grid.column_width
            draw.rectangle((cell_x, cell_y, cell_x + grid.column_width - 2, cell_y + grid.row_height - 2), fill=fill, outline=hex_to_rgb(colors["line"]))
            draw_wrapped_text(draw, table_cell_text(row, column_index), (cell_x + 14, cell_y + 12), grid.column_width - 28, fonts["small"], text_color, 1.15)


def draw_preview_cards(draw, lines: list[str], origin: tuple[int, int], size: tuple[int, int], colors: dict[str, str], fonts: dict[str, object], columns: int) -> None:
    for line, cell in zip(lines, card_grid_cells(visible_card_count(lines), origin, size, columns)):
        draw.rectangle((cell.x, cell.y, cell.x + cell.width, cell.y + cell.height), fill=hex_to_rgb(colors["surface"]), outline=hex_to_rgb(colors["line"]), width=2)
        draw.rectangle((cell.x, cell.y, cell.x + 10, cell.y + cell.height), fill=hex_to_rgb(colors["accent"]))
        draw_wrapped_text(draw, line, (cell.x + 30, cell.y + 28), cell.width - 56, fonts["body"], hex_to_rgb(colors["ink"]), 1.25)


def draw_wrapped_lines(draw, lines: list[str], origin: tuple[int, int], width: int, font, fill: tuple[int, int, int], line_height_scale: float) -> None:
    y = origin[1]
    for line in lines:
        y = draw_wrapped_text(draw, line, (origin[0], y), width, font, fill, line_height_scale) + 8


def draw_wrapped_text(draw, text: str, origin: tuple[int, int], width: int, font, fill: tuple[int, int, int], line_height_scale: float) -> int:
    x, y = origin
    line_height = max(18, round(font_size_pixels(font) * line_height_scale))
    for line in wrap_preview_text(draw, text, font, width):
        draw.text((x, y), line, fill=fill, font=font)
        y += line_height
    return y


def wrap_preview_text(draw, text: str, font, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines = []
    current_line = ""
    for word in words:
        candidate = word if not current_line else current_line + " " + word
        if draw.textlength(candidate, font=font) <= width:
            current_line = candidate
            continue
        if current_line:
            lines.append(current_line)
        current_line = word
    if current_line:
        lines.append(current_line)
    return lines[:8]


def font_size_pixels(font) -> int:
    size = getattr(font, "size", None)
    return int(size) if isinstance(size, int) else 20


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    color = normalize_hex_color(value, "000000")
    return tuple(int(color[index:index + 2], 16) for index in range(0, 6, 2))
