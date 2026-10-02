from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError
from pptx.oxml.ns import qn

from core.css_color import most_contrasting
from powerpoint.model.geometry import Box, own_box
from powerpoint.model.inheritance import SlideContext, slide_context
from powerpoint.preview.paint import background_color, fill_color
from powerpoint.model.shape_kinds import shape_kind
from powerpoint.model.style import resolve_color


DARK_TEXT_SLOT = "tx1"
LIGHT_TEXT_SLOT = "bg1"
FALLBACK_BACKDROP = "#FFFFFF"


def readable_text_color(presentation, slide, box: Box) -> str:
    context = slide_context(presentation, slide)
    backdrop = backdrop_color(context, slide, box)
    candidates = [f"#{color.lstrip('#')}" for color in (resolve_color(context, DARK_TEXT_SLOT), resolve_color(context, LIGHT_TEXT_SLOT)) if color]
    return most_contrasting(candidates, backdrop).lstrip("#").upper()


def backdrop_color(context: SlideContext, slide, box: Box) -> str:
    for shape in reversed(list(slide.shapes)):
        painted = painted_color(context, shape, box)
        if painted:
            return painted
    owners = [slide, slide.slide_layout, slide.slide_layout.slide_master]
    color, picture_fill, owner = background_color(context, [item._element for item in owners])
    if picture_fill is not None:
        return picture_fill_color(owners[owner].part, picture_fill) or color or FALLBACK_BACKDROP
    return color or FALLBACK_BACKDROP


def painted_color(context: SlideContext, shape, box: Box) -> str | None:
    shape_box = own_box(shape._element)
    if shape_box is None or not contains_center(shape_box, box):
        return None
    kind = shape_kind(shape._element)
    if kind == "picture":
        return picture_region_color(shape.image.blob, shape_box, box)
    if kind == "shape":
        return opaque(fill_color(context, shape._element.find(qn("p:spPr")), shape._element.find(qn("p:style"))))
    return None


def contains_center(outer: Box, inner: Box) -> bool:
    center_x, center_y = inner.x + inner.w // 2, inner.y + inner.h // 2
    return outer.x <= center_x <= outer.right and outer.y <= center_y <= outer.bottom


def opaque(color: str | None) -> str | None:
    return color if color and color.startswith("#") else None


def picture_fill_color(part, picture_fill) -> str | None:
    blip = picture_fill.find(qn("a:blip"))
    relationship = blip.get(qn("r:embed")) if blip is not None else None
    if relationship is None:
        return None
    return average_color(part.related_part(relationship).blob, None)


def picture_region_color(blob: bytes, picture_box: Box, box: Box) -> str | None:
    region = picture_box.intersection(box)
    if region is None or picture_box.w <= 0 or picture_box.h <= 0:
        return None
    share = ((region.x - picture_box.x) / picture_box.w, (region.y - picture_box.y) / picture_box.h, (region.right - picture_box.x) / picture_box.w, (region.bottom - picture_box.y) / picture_box.h)
    return average_color(blob, share)


def average_color(blob: bytes, share: tuple[float, float, float, float] | None) -> str | None:
    try:
        image = Image.open(io.BytesIO(blob)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        return None
    if share is not None:
        left, top, right, bottom = share
        image = image.crop((int(left * image.width), int(top * image.height), max(int(right * image.width), int(left * image.width) + 1), max(int(bottom * image.height), int(top * image.height) + 1)))
    red, green, blue = image.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    return f"#{red:02X}{green:02X}{blue:02X}"
