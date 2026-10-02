from __future__ import annotations

from render.office_preview import pixels
from core.units import points_to_pixels


DEFAULT_FONT_SIZE_POINTS = 10
HIGHLIGHT_COLORS = {
    "yellow": "#ffff00", "green": "#00ff00", "cyan": "#00ffff", "magenta": "#ff00ff", "blue": "#0000ff", "red": "#ff0000",
    "darkBlue": "#000080", "darkCyan": "#008080", "darkGreen": "#008000", "darkMagenta": "#800080", "darkRed": "#800000",
    "darkYellow": "#808000", "darkGray": "#808080", "lightGray": "#c0c0c0", "black": "#000000", "white": "#ffffff",
}
BORDER_STYLES = {"single": "solid", "thick": "solid", "double": "double", "dotted": "dotted", "dashed": "dashed", "dashSmallGap": "dashed", "dotDash": "dashed", "dotDotDash": "dotted", "triple": "double", "wave": "solid"}
NO_BORDER = ("nil", "none")


def hex_color(value: str | None) -> str | None:
    if not value or value == "auto":
        return None
    return f"#{value.lower()}" if len(value) == 6 else None


def text_decoration(properties: dict) -> str | None:
    lines = [name for name, flag in (("underline", properties.get("underline")), ("line-through", properties.get("strike"))) if flag]
    return " ".join(lines) or None


def border_value(border: dict | None) -> str | None:
    if not border or border.get("style") in NO_BORDER:
        return None
    style = BORDER_STYLES.get(border.get("style"), "solid")
    width = max(1.0, points_to_pixels(border.get("size", 4) / 8))
    if style == "double":
        width = max(width, 3.0)
    return f"{pixels(width)} {style} {hex_color(border.get('color')) or '#000000'}"
