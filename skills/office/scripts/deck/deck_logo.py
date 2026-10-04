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
RASTER_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


@dataclass(frozen=True)
class Logo:
    path: pathlib.Path
    width: int
    height: int
    has_transparency: bool
    ink: str
    brand_color: str | None

def read_logo(path: pathlib.Path) -> Logo | None:
    if not path.is_file() or path.suffix.casefold() not in RASTER_SUFFIXES:
        return None
    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
        sample = image.convert("RGBA")
        sample.thumbnail((SAMPLE_SIDE, SAMPLE_SIDE))
        data = sample.tobytes()
    pixels = [tuple(data[index:index + 4]) for index in range(0, len(data), 4)]
    opaque = [pixel[:3] for pixel in pixels if pixel[3] >= OPAQUE_ALPHA]
    if not opaque:
        return None
    has_transparency = (len(pixels) - len(opaque)) / len(pixels) >= TRANSPARENT_SHARE
    marks = opaque if has_transparency else [pixel for pixel in opaque if not is_near(pixel, background_of(pixels))]
    return Logo(path, width, height, has_transparency, mean_color(marks or opaque), brand_color(marks or opaque))


def background_of(pixels: list[tuple[int, int, int, int]]) -> tuple[int, int, int]:
    return pixels[0][:3]


def is_near(pixel: tuple[int, int, int], other: tuple[int, int, int]) -> bool:
    return sum(abs(first - second) for first, second in zip(pixel, other)) < 36


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
