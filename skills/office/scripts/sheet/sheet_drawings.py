from __future__ import annotations

import os

from lxml import etree
from openpyxl.drawing.image import Image
from PIL import Image as PillowImage, UnidentifiedImageError

from core.office_operations import Change
from core.office_result import INPUT_NOT_FOUND, INVALID_VALUE, OfficeFailure
from sheet.sheet_definitions import SHAPE_GEOMETRIES
from sheet.sheet_formatting import require_colors
from sheet.workbook_access import parse_cell, sheet_of
from sheet.workbook_fidelity import DRAWING_NAMESPACE, EditRecord, create_drawing, drawing_part, shift_anchor
from sheet.workbook_package import Package, worksheet_parts
from core.units import EMU_PER_CENTIMETRE, EMU_PER_PIXEL, PIXELS_PER_CENTIMETRE
from core.image_formats import PICTURE_FORMATS_TEXT


DRAWING_MAIN_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/main"
DEFAULT_IMAGE_WIDTH = 8
DEFAULT_SHAPE_WIDTH = 6
DEFAULT_SHAPE_HEIGHT = 2
DEFAULT_SHAPE_FILL = "DCEAF7"
DEFAULT_SHAPE_LINE = "2563EB"
DEFAULT_TEXT_COLOR = "1F2937"


def plan_add_image(workbook, operation: dict, location: str) -> Change:
    worksheet = sheet_of(workbook, operation, location)
    row, column = parse_cell(operation["cell"], f"{location}.cell")
    path = os.path.expanduser(operation["path"])
    if not os.path.isfile(path):
        raise OfficeFailure(INPUT_NOT_FOUND.issue(f"{location}.path: {operation['path']} does not exist", f"{location}.path"))
    try:
        with PillowImage.open(path) as probe:
            width, height = probe.size
    except UnidentifiedImageError:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.path: {operation['path']} is not a {PICTURE_FORMATS_TEXT} image", f"{location}.path")) from None
    shown_width = operation.get("width", DEFAULT_IMAGE_WIDTH) * PIXELS_PER_CENTIMETRE

    def change() -> str:
        image = Image(path)
        image.width, image.height = shown_width, shown_width * height / width
        worksheet.add_image(image, f"{worksheet.cell(row=row, column=column).coordinate}")
        return f"added the image {os.path.basename(path)} at {worksheet.title}!{operation['cell'].upper()}"
    return change


def plan_add_shape(editing, operation: dict, location: str) -> Change:
    worksheet = sheet_of(editing.workbook, operation, location)
    row, column = parse_cell(operation["cell"], f"{location}.cell")
    require_colors(operation, location)

    def change() -> str:
        recorded = len(editing.record.steps)
        anchor = shape_anchor(operation, row - 1, column - 1)
        editing.package_patches.append(lambda package: add_anchor(package, worksheet.title, anchor, EditRecord(editing.record.steps[recorded:]), worksheet.title))
        return f"added a {operation.get('shape', 'rectangle')} at {worksheet.title}!{operation['cell'].upper()}"
    return change


def drawing_tag(name: str) -> str:
    return f"{{{DRAWING_NAMESPACE}}}{name}"


def main_drawing_tag(name: str) -> str:
    return f"{{{DRAWING_MAIN_NAMESPACE}}}{name}"


def solid_fill(parent, color: str) -> None:
    fill = etree.SubElement(parent, main_drawing_tag("solidFill"))
    etree.SubElement(fill, main_drawing_tag("srgbClr"), val=color.upper())


def shape_anchor(operation: dict, row: int, column: int):
    anchor = etree.Element(drawing_tag("oneCellAnchor"), nsmap={"xdr": DRAWING_NAMESPACE, "a": DRAWING_MAIN_NAMESPACE})
    marker = etree.SubElement(anchor, drawing_tag("from"))
    for name, value in (("col", column), ("colOff", 0), ("row", row), ("rowOff", 0)):
        etree.SubElement(marker, drawing_tag(name)).text = str(value)
    width = round(operation.get("width", DEFAULT_SHAPE_WIDTH) * EMU_PER_CENTIMETRE)
    height = round(operation.get("height", DEFAULT_SHAPE_HEIGHT) * EMU_PER_CENTIMETRE)
    etree.SubElement(anchor, drawing_tag("ext"), cx=str(width), cy=str(height))
    anchor.append(shape_element(operation))
    etree.SubElement(anchor, drawing_tag("clientData"))
    return anchor


def shape_element(operation: dict):
    kind = operation.get("shape", "rectangle")
    shape = etree.Element(drawing_tag("sp"), macro="", textlink="")
    properties = etree.SubElement(shape, drawing_tag("nvSpPr"))
    etree.SubElement(properties, drawing_tag("cNvPr"), id="0", name=kind)
    etree.SubElement(properties, drawing_tag("cNvSpPr"), **({"txBox": "1"} if kind == "textbox" else {}))
    geometry = etree.SubElement(shape, drawing_tag("spPr"))
    preset = etree.SubElement(geometry, main_drawing_tag("prstGeom"), prst=SHAPE_GEOMETRIES[kind])
    etree.SubElement(preset, main_drawing_tag("avLst"))
    if kind == "textbox" and not operation.get("fill"):
        etree.SubElement(geometry, main_drawing_tag("noFill"))
    else:
        solid_fill(geometry, operation.get("fill", DEFAULT_SHAPE_FILL))
    line = etree.SubElement(geometry, main_drawing_tag("ln"), w=str(EMU_PER_PIXEL))
    solid_fill(line, operation.get("lineColor", DEFAULT_SHAPE_LINE))
    shape.append(text_body(operation))
    return shape


def text_body(operation: dict):
    body = etree.Element(drawing_tag("txBody"))
    etree.SubElement(body, main_drawing_tag("bodyPr"), wrap="square", rtlCol="0", anchor="ctr")
    etree.SubElement(body, main_drawing_tag("lstStyle"))
    for line in (operation.get("text") or "").split("\n"):
        paragraph = etree.SubElement(body, main_drawing_tag("p"))
        etree.SubElement(paragraph, main_drawing_tag("pPr"), algn="l" if operation.get("shape") == "textbox" else "ctr")
        run = etree.SubElement(paragraph, main_drawing_tag("r"))
        run_properties = etree.SubElement(run, main_drawing_tag("rPr"), lang="ko-KR", sz=str(round(operation.get("fontSize", 11) * 100)), b="1" if operation.get("bold") else "0")
        solid_fill(run_properties, operation.get("fontColor", DEFAULT_TEXT_COLOR))
        etree.SubElement(run, main_drawing_tag("t")).text = line
    return body


def add_anchor(package: Package, title: str, anchor, later_steps: EditRecord, original_title: str) -> None:
    sheet_part = next((part for part, name in worksheet_parts(package).items() if name == title), None)
    if sheet_part is None:
        return
    for shift in later_steps.shifts_for(original_title):
        shift_anchor(anchor, shift)
    part = drawing_part(package, sheet_part) or create_drawing(package, sheet_part)
    root = package.xml(part)
    identifiers = [int(node.get("id")) for node in root.iter(drawing_tag("cNvPr")) if (node.get("id") or "").isdigit()]
    for properties in anchor.iter(drawing_tag("cNvPr")):
        properties.set("id", str(max(identifiers, default=1) + 1))
        properties.set("name", f"{properties.get('name')} {properties.get('id')}")
    root.append(anchor)
    package.set_xml(part, root)
