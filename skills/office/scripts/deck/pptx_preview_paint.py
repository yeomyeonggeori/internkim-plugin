from __future__ import annotations

from dataclasses import dataclass
import html

from pptx.oxml.ns import qn

from render.office_preview import data_uri
from deck.pptx_style import PERCENT_SCALE, resolve_color
from core.units import EMU_PER_PIXEL, PIXELS_PER_EMU, PIXELS_PER_POINT


DEFAULT_LINE_WIDTH_EMU = EMU_PER_PIXEL
FILL_TAGS = (qn("a:noFill"), qn("a:solidFill"), qn("a:gradFill"), qn("a:blipFill"), qn("a:pattFill"), qn("a:grpFill"))


@dataclass(frozen=True)
class Outline:
    color: str
    width: float


def pixels(emu: float) -> float:
    return round(emu * PIXELS_PER_EMU, 2)


def point_pixels(points: float) -> float:
    return round(points * PIXELS_PER_POINT, 2)


def css(properties: dict) -> str:
    return ";".join(f"{name}:{value}" for name, value in properties.items() if value is not None)


def element(tag: str, properties: dict, content: str = "", attributes: str = "") -> str:
    return f'<{tag}{attributes} style="{html.escape(css(properties))}">{content}</{tag}>'


def svg_uri(svg: str) -> str:
    return data_uri("image/svg+xml", svg.encode("utf-8"))


def fill_color(context, properties, style) -> str | None:
    own = next((child for child in properties if child.tag in FILL_TAGS), None) if properties is not None else None
    if own is not None:
        return paint_color(context, own)
    reference = style.find(qn("a:fillRef")) if style is not None else None
    if reference is None or reference.get("idx", "0") == "0" or not len(reference):
        return None
    return css_color(context, reference[0])


def paint_color(context, paint) -> str | None:
    if paint.tag == qn("a:solidFill") and len(paint):
        return css_color(context, paint[0])
    if paint.tag == qn("a:gradFill"):
        stop = paint.find(f"{qn('a:gsLst')}/{qn('a:gs')}")
        return css_color(context, stop[0]) if stop is not None and len(stop) else None
    return None


def css_color(context, color_element) -> str | None:
    hex_color = resolve_color(context, color_element)
    alpha = color_element.find(qn("a:alpha"))
    if hex_color is None or alpha is None:
        return hex_color
    red, green, blue = (int(hex_color[index:index + 2], 16) for index in (1, 3, 5))
    return f"rgba({red}, {green}, {blue}, {int(alpha.get('val')) / PERCENT_SCALE:.3f})"


def outline(context, properties, style) -> Outline | None:
    line = properties.find(qn("a:ln")) if properties is not None else None
    width = int(line.get("w", DEFAULT_LINE_WIDTH_EMU)) if line is not None else DEFAULT_LINE_WIDTH_EMU
    own = next((child for child in line if child.tag in FILL_TAGS), None) if line is not None else None
    if own is not None:
        color = paint_color(context, own)
        return Outline(color, max(pixels(width), 1.0)) if color else None
    reference = style.find(qn("a:lnRef")) if style is not None else None
    if reference is None or reference.get("idx", "0") == "0" or not len(reference):
        return None
    color = css_color(context, reference[0])
    return Outline(color, max(pixels(width), 1.0)) if color else None


def background_color(context, owners) -> tuple[str | None, object, int]:
    for index, owner in enumerate(owners):
        background = owner.find(f"{qn('p:cSld')}/{qn('p:bg')}")
        if background is None:
            continue
        properties = background.find(qn("p:bgPr"))
        if properties is not None:
            paint = next((child for child in properties if child.tag in FILL_TAGS), None)
            picture = paint if paint is not None and paint.tag == qn("a:blipFill") else None
            return (paint_color(context, paint) if paint is not None else None), picture, index
        reference = background.find(qn("p:bgRef"))
        if reference is not None and len(reference):
            return resolve_color(context, reference[0]), None, index
    return "#FFFFFF", None, 0
