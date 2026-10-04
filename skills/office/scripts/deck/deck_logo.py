from __future__ import annotations

from dataclasses import dataclass
import pathlib

from core.css_color import hex_of, hex_oklch


SAMPLE_SIDE = 96
OPAQUE_ALPHA = 128
TRANSPARENT_SHARE = 0.02
BRAND_CHROMA_MINIMUM = 0.06
BRAND_LIGHTNESS_RANGE = (0.2, 0.92)
BRAND_PIXEL_SHARE = 0.03
HUE_BIN_DEGREES = 15
CROP_MARGIN_SHARE = 0.04
NEAR_BACKGROUND_DISTANCE = 36
RASTER_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


@dataclass(frozen=True)
class Logo:
    path: pathlib.Path
    width: int
    height: int
    has_transparency: bool
    ink: str
    brand_color: str | None
    crop: tuple[int, int, int, int] | None = None


def read_logo(path: pathlib.Path) -> Logo | None:
    if not path.is_file() or path.suffix.casefold() not in RASTER_SUFFIXES:
        return None
    from PIL import Image

    crop = logo_crop_box(path)
    with Image.open(path) as image:
        width, height = crop[2] - crop[0], crop[3] - crop[1]
        sample = image.convert("RGBA").crop(crop)
        sample.thumbnail((SAMPLE_SIDE, SAMPLE_SIDE))
        data = sample.tobytes()
    pixels = [tuple(data[index:index + 4]) for index in range(0, len(data), 4)]
    opaque = [pixel[:3] for pixel in pixels if pixel[3] >= OPAQUE_ALPHA]
    if not opaque:
        return None
    has_transparency = (len(pixels) - len(opaque)) / len(pixels) >= TRANSPARENT_SHARE
    marks = opaque if has_transparency else [pixel for pixel in opaque if not is_near(pixel, background_of(pixels))]
    return Logo(path, width, height, has_transparency, mean_color(marks or opaque), brand_color(marks or opaque), crop)


def logo_crop_box(path: pathlib.Path) -> tuple[int, int, int, int]:
    from PIL import Image

    with Image.open(path) as image:
        rgba = image.convert("RGBA")
    width, height = rgba.size
    mask = mark_mask(rgba)
    box = mask.getbbox()
    if box is None:
        return (0, 0, width, height)
    margin = round(max(box[2] - box[0], box[3] - box[1]) * CROP_MARGIN_SHARE)
    return (max(box[0] - margin, 0), max(box[1] - margin, 0), min(box[2] + margin, width), min(box[3] + margin, height))


def mark_mask(rgba):
    from PIL import Image, ImageChops

    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] < OPAQUE_ALPHA:
        return alpha.point(lambda value: 255 if value >= OPAQUE_ALPHA else 0)
    corner = rgba.getpixel((0, 0))
    difference = ImageChops.difference(rgba.convert("RGB"), Image.new("RGB", rgba.size, corner[:3]))
    red, green, blue = difference.split()
    return ImageChops.add(ImageChops.add(red, green), blue).point(lambda value: 255 if value >= NEAR_BACKGROUND_DISTANCE else 0)


def cropped_logo_bytes(logo: Logo) -> bytes:
    import io

    from PIL import Image

    with Image.open(logo.path) as image:
        cropped = image.convert("RGBA").crop(logo.crop) if logo.crop else image.convert("RGBA")
    buffer = io.BytesIO()
    cropped.save(buffer, format="PNG")
    return buffer.getvalue()


def background_of(pixels: list[tuple[int, int, int, int]]) -> tuple[int, int, int]:
    return pixels[0][:3]


def is_near(pixel: tuple[int, int, int], other: tuple[int, int, int]) -> bool:
    return sum(abs(first - second) for first, second in zip(pixel, other)) < NEAR_BACKGROUND_DISTANCE


def mean_color(pixels: list[tuple[int, int, int]]) -> str:
    return hex_of(tuple(sum(pixel[channel] for pixel in pixels) / len(pixels) / 255 for channel in range(3)))


def brand_color(pixels: list[tuple[int, int, int]]) -> str | None:
    bins: dict[int, list[tuple[int, int, int]]] = {}
    for pixel in pixels:
        lightness, chroma, hue = hex_oklch(hex_of(tuple(channel / 255 for channel in pixel)))
        if chroma >= BRAND_CHROMA_MINIMUM and BRAND_LIGHTNESS_RANGE[0] <= lightness <= BRAND_LIGHTNESS_RANGE[1]:
            bins.setdefault(int(hue // HUE_BIN_DEGREES), []).append(pixel)
    if not bins:
        return None
    largest = max(bins.values(), key=len)
    return mean_color(largest) if len(largest) >= BRAND_PIXEL_SHARE * len(pixels) else None
