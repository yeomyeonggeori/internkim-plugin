from __future__ import annotations

import io
import math

from host import script_host


IMAGE_MEDIA_TYPE = "image/png"
JPEG_MEDIA_TYPE = "image/jpeg"
MAXIMUM_IMAGE_BYTES = 200_000
MINIMUM_IMAGE_SIDE = 320
JPEG_QUALITY = 85
SHEET_TILE_WIDTH = 400
SHEET_GAP = 8
LABEL_PIXEL = 4
LABEL_PADDING = 2
GLYPH_COLUMNS = 3
GLYPH_ROWS = 5
GLYPH_SPACING = 1

DIGIT_GLYPHS = (
    ("###", "# #", "# #", "# #", "###"),
    (" # ", "## ", " # ", " # ", "###"),
    ("###", "  #", "###", "#  ", "###"),
    ("###", "  #", "###", "  #", "###"),
    ("# #", "# #", "###", "  #", "  #"),
    ("###", "#  ", "###", "  #", "###"),
    ("###", "#  ", "###", "# #", "###"),
    ("###", "  #", "  #", "  #", "  #"),
    ("###", "# #", "###", "# #", "###"),
    ("###", "# #", "###", "  #", "###"),
)


def fit_image(data: bytes) -> script_host.Image:
    if len(data) <= MAXIMUM_IMAGE_BYTES:
        return script_host.Image(IMAGE_MEDIA_TYPE, data)
    picture = decoded_rgb(data)
    while picture.width >= MINIMUM_IMAGE_SIDE and picture.height >= MINIMUM_IMAGE_SIDE:
        encoded = encoded_jpeg(picture)
        if len(encoded) <= MAXIMUM_IMAGE_BYTES:
            return script_host.Image(JPEG_MEDIA_TYPE, encoded)
        picture = resized(picture, picture.width * 4 // 5, picture.height * 4 // 5)
    raise ValueError(f"the render does not fit {MAXIMUM_IMAGE_BYTES} bytes above {MINIMUM_IMAGE_SIDE} pixels")


def decoded_rgb(data: bytes):
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as picture:
            return picture.convert("RGB")
    except (UnidentifiedImageError, OSError) as failure:
        raise ValueError(f"the render is {len(data)} bytes and cannot be shrunk: {failure}") from failure


def encoded_jpeg(picture) -> bytes:
    buffer = io.BytesIO()
    picture.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def encoded_png(picture) -> bytes:
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    return buffer.getvalue()


def resized(picture, width: int, height: int):
    from PIL import Image

    return picture.resize((max(width, 1), max(height, 1)), Image.Resampling.BOX)


def sheet_columns(count: int) -> int:
    return math.ceil(math.sqrt(count))


def contact_sheet(renders: list[bytes]) -> script_host.Image:
    if not renders:
        raise ValueError("a contact sheet needs at least one render")
    tiles = []
    for index, render in enumerate(renders):
        try:
            tiles.append(decoded_rgb(render))
        except ValueError as failure:
            raise ValueError(f"decode render {index + 1} for the contact sheet: {failure}") from failure
    return fit_image(encoded_png(laid_out(tiles)))


def laid_out(tiles: list):
    from PIL import Image

    columns = sheet_columns(len(tiles))
    rows = (len(tiles) + columns - 1) // columns
    tile_height = SHEET_TILE_WIDTH * tiles[0].height // tiles[0].width
    sheet = Image.new("RGB", (columns * SHEET_TILE_WIDTH + (columns + 1) * SHEET_GAP, rows * tile_height + (rows + 1) * SHEET_GAP), (255, 255, 255))
    for index, tile in enumerate(tiles):
        origin = (SHEET_GAP + (index % columns) * (SHEET_TILE_WIDTH + SHEET_GAP), SHEET_GAP + (index // columns) * (tile_height + SHEET_GAP))
        sheet.paste(resized(tile, SHEET_TILE_WIDTH, tile_height), origin)
        draw_label(sheet, origin, index + 1)
    return sheet


def draw_label(sheet, origin: tuple[int, int], number: int) -> None:
    from PIL import ImageDraw

    digits = str(number)
    width = (len(digits) * (GLYPH_COLUMNS + GLYPH_SPACING) - GLYPH_SPACING) * LABEL_PIXEL + 2 * LABEL_PADDING * LABEL_PIXEL
    height = GLYPH_ROWS * LABEL_PIXEL + 2 * LABEL_PADDING * LABEL_PIXEL
    drawing = ImageDraw.Draw(sheet)
    drawing.rectangle((origin[0], origin[1], origin[0] + width - 1, origin[1] + height - 1), fill=(0, 0, 0))
    for position, digit in enumerate(digits):
        for row, line in enumerate(DIGIT_GLYPHS[int(digit)]):
            for column, cell in enumerate(line):
                if cell == "#":
                    left = origin[0] + (LABEL_PADDING + position * (GLYPH_COLUMNS + GLYPH_SPACING) + column) * LABEL_PIXEL
                    top = origin[1] + (LABEL_PADDING + row) * LABEL_PIXEL
                    drawing.rectangle((left, top, left + LABEL_PIXEL - 1, top + LABEL_PIXEL - 1), fill=(255, 255, 255))

