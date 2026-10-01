from __future__ import annotations

import io
import re

from PIL import Image, UnidentifiedImageError

from docx.oxml.ns import qn

from docx_charts import read_specification
from docx_page_operations import PICTURE_WATERMARK_PREFIX
from docx_preview_model import BoxItem, ChartItem, ImageItem
from docx_preview_tables import TableLayers
from office_preview import data_uri
from units import emu_to_pixels, inches_to_pixels, points_to_pixels


NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "v": "urn:schemas-microsoft-com:vml",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
}
ALTERNATE_CONTENT_TAG = f"{{{NAMESPACES['mc']}}}AlternateContent"
GRAPHIC_TAGS = (qn("w:drawing"), qn("w:pict"), ALTERNATE_CONTENT_TAG)
VML_LENGTH = re.compile(r"(width|height)\s*:\s*([\d.]+)(pt|in|px)?")
VML_UNITS_TO_PIXELS = {"pt": points_to_pixels, "in": inches_to_pixels, "px": float, "": points_to_pixels}
WASHOUT_WHITE_SHARE = 0.7


def graphic_items(element, part, builder) -> list:
    if element.tag == ALTERNATE_CONTENT_TAG:
        choice = element.find("mc:Choice", NAMESPACES)
        return [item for child in (choice if choice is not None else []) for item in graphic_items(child, part, builder)]
    if element.tag == qn("w:drawing"):
        return drawing_items(element, part, builder)
    if element.tag == qn("w:pict"):
        return vml_items(element, part, builder)
    return []


def drawing_items(drawing, part, builder) -> list:
    placement = drawing.find("wp:inline", NAMESPACES)
    if placement is None:
        placement = drawing.find("wp:anchor", NAMESPACES)
        builder.preview.approximate("floating pictures and shapes placed in line")
    if placement is None:
        return []
    extent = placement.find("wp:extent", NAMESPACES)
    width = emu_to_pixels(int(extent.get("cx", "0"))) if extent is not None else 0
    height = emu_to_pixels(int(extent.get("cy", "0"))) if extent is not None else 0
    blip = placement.find(".//a:blip", NAMESPACES)
    if blip is not None:
        source = image_data_uri(part, blip.get(f"{{{NAMESPACES['r']}}}embed"))
        return [ImageItem(source, width, height)] if source else []
    text_box = placement.find(f".//{{{NAMESPACES['wps']}}}txbx/{qn('w:txbxContent')}")
    if text_box is not None:
        return [BoxItem(builder.blocks(list(text_box), part, TableLayers()), width, height)]
    chart = placement.find(".//c:chart", NAMESPACES)
    if chart is not None:
        return chart_items(chart, part, builder, width, height)
    return []


def chart_items(chart, part, builder, width: float, height: float) -> list:
    relationship_id = chart.get(f"{{{NAMESPACES['r']}}}id")
    if part is None or relationship_id not in part.rels:
        builder.preview.approximate("charts whose data part is missing")
        return [BoxItem([], width, height)]
    chart_specification = read_specification(part.rels[relationship_id].target_part)
    return [ChartItem(chart_specification.model(), chart_specification.look(builder.chart_palette), width, height)]


def vml_items(picture, part, builder) -> list:
    text_path = picture.find(".//v:textpath", NAMESPACES)
    if text_path is not None:
        builder.watermark = text_path.get("string", "")
        return []
    shape = next((child for child in picture if child.tag.startswith(f"{{{NAMESPACES['v']}}}") and not child.tag.endswith("}shapetype")), None)
    width, height = vml_size(shape.get("style", "") if shape is not None else "")
    image = picture.find(".//v:imagedata", NAMESPACES)
    if image is not None and shape is not None and (shape.get("id") or "").startswith(PICTURE_WATERMARK_PREFIX):
        builder.watermark_image = watermark_image(part, image.get(f"{{{NAMESPACES['r']}}}id"), width, height, image.get("gain") is not None)
        return []
    if image is not None:
        source = image_data_uri(part, image.get(f"{{{NAMESPACES['r']}}}id"))
        return [ImageItem(source, width, height)] if source else []
    text_box = picture.find(f".//{qn('w:txbxContent')}")
    if text_box is not None:
        builder.preview.approximate("floating pictures and shapes placed in line")
        return [BoxItem(builder.blocks(list(text_box), part, TableLayers()), width, height)]
    return []


def watermark_image(part, relationship_id: str | None, width: float, height: float, is_washed_out: bool) -> ImageItem | None:
    source = image_data_uri(part, relationship_id)
    if source is None or not is_washed_out:
        return ImageItem(source, width, height) if source else None
    try:
        return ImageItem(washed_out(part.rels[relationship_id].target_part.blob), width, height)
    except UnidentifiedImageError:
        return ImageItem(source, width, height)


def washed_out(blob: bytes) -> str:
    with Image.open(io.BytesIO(blob)) as picture:
        opaque = picture.convert("RGBA")
    white = Image.new("RGBA", opaque.size, (255, 255, 255, 255))
    stream = io.BytesIO()
    Image.blend(opaque, white, WASHOUT_WHITE_SHARE).save(stream, format="PNG")
    return data_uri("image/png", stream.getvalue())


def vml_size(style: str) -> tuple[float, float]:
    sizes = {name: VML_UNITS_TO_PIXELS[unit](float(value)) for name, value, unit in VML_LENGTH.findall(style)}
    return sizes.get("width", 0), sizes.get("height", 0)


def image_data_uri(part, relationship_id: str | None) -> str | None:
    if part is None or not relationship_id or relationship_id not in part.rels:
        return None
    target = part.rels[relationship_id].target_part
    return data_uri(target.content_type, target.blob)
