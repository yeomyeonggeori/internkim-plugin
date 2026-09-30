from __future__ import annotations

import pathlib

from png_codec import Pixel, PixelRows, read_png, write_png


CONTACT_SHEET_GROUP_SIZE = 4
CONTACT_SHEET_THUMBNAIL_WIDTH = 560
DEFAULT_THUMBNAIL_HEIGHT = 315
SHEET_COLUMNS = 2
SHEET_PADDING = 24
SHEET_GUTTER = 18
LABEL_HEIGHT = 34
SHEET_BACKGROUND = (248, 250, 252, 255)
FRAME_COLOR = (203, 213, 225, 255)
BADGE_COLOR = (17, 24, 39, 230)
BADGE_DIGIT_COLOR = (255, 255, 255, 255)
BADGE_DIGIT_SCALE = 4
BADGE_HEIGHT = 26
DIGIT_GLYPHS = {
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "001", "001", "001"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
}


def write_contact_sheets(review_directory_path: pathlib.Path, image_paths: list[pathlib.Path]) -> list[dict[str, object]]:
    contact_sheets = []
    for group_index in range(0, len(image_paths), CONTACT_SHEET_GROUP_SIZE):
        group_paths = image_paths[group_index:group_index + CONTACT_SHEET_GROUP_SIZE]
        sheet_path = review_directory_path / f"contact-sheet-{(group_index // CONTACT_SHEET_GROUP_SIZE) + 1:02d}.png"
        slide_numbers = list(range(group_index + 1, group_index + len(group_paths) + 1))
        sheet = compose_contact_sheet(group_paths, slide_numbers)
        write_png(sheet_path, sheet["width"], sheet["height"], sheet["rows"])
        contact_sheets.append({
            "filename": sheet_path.name,
            "slideNumbers": slide_numbers,
        })
    return contact_sheets


def compose_contact_sheet(image_paths: list[pathlib.Path], slide_numbers: list[int]) -> dict[str, object]:
    images = [read_png(path) for path in image_paths]
    thumbnail_width = CONTACT_SHEET_THUMBNAIL_WIDTH
    thumbnail_height = round(thumbnail_width * images[0]["height"] / images[0]["width"]) if images else DEFAULT_THUMBNAIL_HEIGHT
    row_count = max(1, (len(images) + SHEET_COLUMNS - 1) // SHEET_COLUMNS)
    sheet_width = (thumbnail_width * SHEET_COLUMNS) + (SHEET_GUTTER * (SHEET_COLUMNS - 1)) + (SHEET_PADDING * 2)
    sheet_height = ((thumbnail_height + LABEL_HEIGHT) * row_count) + (SHEET_GUTTER * (row_count - 1)) + (SHEET_PADDING * 2)
    sheet_rows = [[SHEET_BACKGROUND for _ in range(sheet_width)] for _ in range(sheet_height)]
    for index, image in enumerate(images):
        x = SHEET_PADDING + (index % SHEET_COLUMNS) * (thumbnail_width + SHEET_GUTTER)
        y = SHEET_PADDING + (index // SHEET_COLUMNS) * (thumbnail_height + LABEL_HEIGHT + SHEET_GUTTER)
        draw_number_badge(sheet_rows, x, y, slide_numbers[index])
        paste_image(sheet_rows, resize_image(image, thumbnail_width, thumbnail_height), x, y + LABEL_HEIGHT)
        draw_frame(sheet_rows, x, y + LABEL_HEIGHT, thumbnail_width, thumbnail_height)
    return {"width": sheet_width, "height": sheet_height, "rows": sheet_rows}


def resize_image(image: dict[str, object], target_width: int, target_height: int) -> PixelRows:
    rows = image["rows"]
    source_width = image["width"]
    source_height = image["height"]
    resized = []
    for target_y in range(target_height):
        source_row = rows[min(source_height - 1, round(target_y * source_height / target_height))]
        resized.append([
            source_row[min(source_width - 1, round(target_x * source_width / target_width))]
            for target_x in range(target_width)
        ])
    return resized


def paste_image(sheet_rows: PixelRows, image_rows: PixelRows, left: int, top: int) -> None:
    for y, row in enumerate(image_rows):
        target_row = sheet_rows[top + y]
        for x, pixel in enumerate(row):
            target_row[left + x] = pixel


def draw_frame(rows: PixelRows, left: int, top: int, width: int, height: int) -> None:
    for x in range(left, left + width):
        rows[top][x] = FRAME_COLOR
        rows[top + height - 1][x] = FRAME_COLOR
    for y in range(top, top + height):
        rows[y][left] = FRAME_COLOR
        rows[y][left + width - 1] = FRAME_COLOR


def draw_number_badge(rows: PixelRows, left: int, top: int, number: int) -> None:
    digits = str(number)
    digit_width = 3 * BADGE_DIGIT_SCALE
    badge_width = 20 + len(digits) * digit_width + max(0, len(digits) - 1) * BADGE_DIGIT_SCALE
    fill_rectangle(rows, left, top, badge_width, BADGE_HEIGHT, BADGE_COLOR)
    cursor = left + 10
    for digit in digits:
        draw_digit(rows, cursor, top + 5, digit)
        cursor += digit_width + BADGE_DIGIT_SCALE


def draw_digit(rows: PixelRows, left: int, top: int, digit: str) -> None:
    for y, line in enumerate(DIGIT_GLYPHS[digit]):
        for x, value in enumerate(line):
            if value == "1":
                fill_rectangle(rows, left + x * BADGE_DIGIT_SCALE, top + y * BADGE_DIGIT_SCALE, BADGE_DIGIT_SCALE, BADGE_DIGIT_SCALE, BADGE_DIGIT_COLOR)


def fill_rectangle(rows: PixelRows, left: int, top: int, width: int, height: int, color: Pixel) -> None:
    for y in range(top, min(len(rows), top + height)):
        row = rows[y]
        for x in range(left, min(len(row), left + width)):
            row[x] = color
