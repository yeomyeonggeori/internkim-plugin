from __future__ import annotations

import colorsys

from lxml import etree
from openpyxl.styles.colors import COLOR_INDEX

from core.office_theme import OFFICE_THEME, THEME_SLOTS


DRAWING_NAMESPACE = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
DEFAULT_THEME = tuple(OFFICE_THEME.values())


def theme_palette(theme_bytes: bytes | None) -> tuple[str, ...]:
    if not theme_bytes:
        return DEFAULT_THEME
    scheme = etree.fromstring(theme_bytes).find(f".//{DRAWING_NAMESPACE}clrScheme")
    if scheme is None:
        return DEFAULT_THEME
    colors = []
    for slot, fallback in zip(THEME_SLOTS, DEFAULT_THEME):
        element = scheme.find(f"{DRAWING_NAMESPACE}{slot}")
        colors.append(scheme_color(element) or fallback)
    return tuple(colors)


def scheme_color(element) -> str | None:
    if element is None:
        return None
    for child in element:
        if child.get("val") and child.tag.endswith("srgbClr"):
            return child.get("val")
        if child.get("lastClr"):
            return child.get("lastClr")
    return None


def css_color(color, palette: tuple[str, ...]) -> str | None:
    if color is None:
        return None
    kind = getattr(color, "type", None)
    if kind == "rgb" and isinstance(color.rgb, str):
        return f"#{color.rgb[-6:].lower()}"
    if kind == "theme" and color.theme is not None and color.theme < len(palette):
        return f"#{tinted(palette[color.theme], color.tint or 0).lower()}"
    if kind == "indexed" and color.indexed is not None and color.indexed < len(COLOR_INDEX):
        return f"#{COLOR_INDEX[color.indexed][-6:].lower()}" if color.indexed not in (64, 65) else None
    return None


def tinted(hex_color: str, tint: float) -> str:
    red, green, blue = (int(hex_color[index:index + 2], 16) / 255 for index in (0, 2, 4))
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    lightness = lightness * (1 + tint) if tint < 0 else lightness * (1 - tint) + tint
    red, green, blue = colorsys.hls_to_rgb(hue, max(0.0, min(1.0, lightness)), saturation)
    return "".join(f"{round(channel * 255):02X}" for channel in (red, green, blue))
