from __future__ import annotations

import copy

from PIL import Image, UnidentifiedImageError
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.util import Pt

from core.office_operations import OPERATION_NOT_APPLICABLE, Change
from core.office_result import INPUT_NOT_FOUND, INVALID_VALUE, OfficeFailure
from deck.pptx_animation import remove_animations_of
from deck.pptx_edit_definitions import PICTURE_UNREADABLE
from deck.pptx_geometry import ROTATION_UNITS_PER_DEGREE, Box, local_box, transform_of
from deck.pptx_inheritance import slide_context
from deck.pptx_relationships import carry_relationships, drop_unreferenced, relationship_ids
from deck.pptx_shape_kinds import NON_VISUAL_TAGS, shape_kind
from deck.pptx_targets import PptxEditing, ShapeTarget, require_kind, resolve_shape
from core.image_formats import OFFICE_PICTURE_FORMATS


SHAPE_TAGS = {qn("p:sp"), qn("p:grpSp"), qn("p:graphicFrame"), qn("p:cxnSp"), qn("p:pic"), qn("p:contentPart")}
DUPLICATE_OFFSET_EMU = 228600
FILLED_KINDS = ("shape", "text")
OUTLINED_KINDS = ("shape", "text", "picture", "connector")


def current_box(editing: PptxEditing, target: ShapeTarget) -> Box:
    return target.frame.to_slide(local_box(target.element, slide_context(editing.presentation, target.slide)))


def plan_set_transform(editing: PptxEditing, operation: dict, location: str) -> Change:
    if all(operation.get(name) is None for name in ("x", "y", "w", "h", "rotation")):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: set_transform changes nothing", location, "give at least one of x, y, w, h, rotation"))
    target = resolve_shape(editing, operation, location)

    def change() -> str:
        before = current_box(editing, target)
        after = Box(*(operation.get(name) if operation.get(name) is not None else getattr(before, name) for name in ("x", "y", "w", "h")))
        local = target.frame.to_local(after)
        write_local_box(target.element, local)
        if operation.get("rotation") is not None:
            transform_of(target.element).set("rot", str(round(operation["rotation"] % 360 * ROTATION_UNITS_PER_DEGREE)))
        editing.mark_edited(target.slide)
        return f"placed {target.label} at x {after.x}, y {after.y}, w {after.w}, h {after.h}"
    return change


def write_local_box(element, box: Box) -> None:
    before = local_box(element, None)
    transform = transform_of(element)
    if transform is None:
        transform = element.find(qn("p:spPr")).get_or_add_xfrm()
    offset, extent = transform.get_or_add_off(), transform.get_or_add_ext()
    offset.set("x", str(box.x))
    offset.set("y", str(box.y))
    extent.set("cx", str(box.w))
    extent.set("cy", str(box.h))
    if shape_kind(element) == "table" and before.w and before.h:
        scale_table(element, box.w / before.w, box.h / before.h)


def scale_table(element, width_ratio: float, height_ratio: float) -> None:
    table = element.find(f"{qn('a:graphic')}/{qn('a:graphicData')}/{qn('a:tbl')}")
    for column in table.iter(qn("a:gridCol")):
        column.set("w", str(round(int(column.get("w")) * width_ratio)))
    for row in table.iter(qn("a:tr")):
        row.set("h", str(round(int(row.get("h")) * height_ratio)))


def plan_delete_shape(editing: PptxEditing, operation: dict, location: str) -> Change:
    target = resolve_shape(editing, operation, location)
    for element in target.element.iter(*SHAPE_TAGS):
        editing.deleted_shapes.add(id(element))

    def change() -> str:
        identifiers = {str(properties[0].get("id")) for properties in target.element.iter(*NON_VISUAL_TAGS)}
        relationships = relationship_ids(target.element)
        target.element.getparent().remove(target.element)
        detach_connectors(target.slide._element, identifiers)
        removed_animations = remove_animations_of(target.slide._element, identifiers)
        for relationship_id in relationships:
            drop_unreferenced(target.slide.part, relationship_id)
        editing.mark_edited(target.slide)
        animations = f" and {removed_animations} animations on it" if removed_animations else ""
        return f"deleted {target.label}{animations}"
    return change


def detach_connectors(slide_element, identifiers: set[str]) -> None:
    for connection in [node for node in slide_element.iter(qn("a:stCxn"), qn("a:endCxn")) if node.get("id") in identifiers]:
        connection.getparent().remove(connection)


def plan_duplicate_shape(editing: PptxEditing, operation: dict, location: str) -> Change:
    target = resolve_shape(editing, operation, location)

    def change() -> str:
        before = current_box(editing, target)
        clone = copy.deepcopy(target.element)
        renumber_shapes(clone, next_shape_identifier(target.slide._element))
        carry_relationships(target.slide.part, target.slide.part, clone)
        target.element.addnext(clone)
        x = operation.get("x") if operation.get("x") is not None else before.x + DUPLICATE_OFFSET_EMU
        y = operation.get("y") if operation.get("y") is not None else before.y + DUPLICATE_OFFSET_EMU
        write_local_box(clone, target.frame.to_local(Box(x, y, before.w, before.h)))
        editing.mark_edited(target.slide)
        return f"copied {target.label} to x {x}, y {y}"
    return change


def next_shape_identifier(slide_element) -> int:
    identifiers = [int(properties[0].get("id")) for properties in slide_element.iter(*NON_VISUAL_TAGS) if properties[0].get("id", "").isdigit()]
    return max(identifiers, default=0) + 1


def renumber_shapes(element, first_identifier: int) -> None:
    for offset, properties in enumerate(element.iter(*NON_VISUAL_TAGS)):
        properties[0].set("id", str(first_identifier + offset))


def plan_set_z_order(editing: PptxEditing, operation: dict, location: str) -> Change:
    target = resolve_shape(editing, operation, location)

    def change() -> str:
        siblings = [child for child in target.element.getparent() if child.tag in SHAPE_TAGS]
        position = next(index for index, sibling in enumerate(siblings) if sibling is target.element)
        destination = {"front": len(siblings) - 1, "back": 0, "forward": min(position + 1, len(siblings) - 1), "backward": max(position - 1, 0)}[operation["to"]]
        if destination > position:
            siblings[destination].addnext(target.element)
        elif destination < position:
            siblings[destination].addprevious(target.element)
        editing.mark_edited(target.slide)
        return f"moved {target.label} {operation['to']}"
    return change


def plan_set_fill(editing: PptxEditing, operation: dict, location: str) -> Change:
    target = resolve_shape(editing, operation, location)
    require_kind(target, FILLED_KINDS, location, "only shapes and text boxes take a fill")

    def change() -> str:
        fill = target.shape.fill
        if operation["color"] == "none":
            fill.background()
        else:
            fill.solid()
            fill.fore_color.rgb = rgb(operation["color"])
        editing.mark_edited(target.slide)
        return f"filled {target.label} with {operation['color']}"
    return change


def plan_set_line(editing: PptxEditing, operation: dict, location: str) -> Change:
    if operation.get("color") is None and operation.get("width") is None:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: set_line changes nothing", location, "give color, width or both"))
    target = resolve_shape(editing, operation, location)
    require_kind(target, OUTLINED_KINDS, location, "only shapes, text boxes, pictures and connectors take an outline")

    def change() -> str:
        line = target.shape.line
        if operation.get("color") == "none":
            line.fill.background()
        elif operation.get("color") is not None:
            line.color.rgb = rgb(operation["color"])
        if operation.get("width") is not None:
            line.width = Pt(operation["width"])
        editing.mark_edited(target.slide)
        return f"set the outline of {target.label}"
    return change


def rgb(color: str) -> RGBColor:
    return RGBColor.from_string(color.lstrip("#").upper())


def plan_replace_picture(editing: PptxEditing, operation: dict, location: str) -> Change:
    target = resolve_shape(editing, operation, location)
    require_kind(target, ("picture",), location, "replace_picture swaps the image of a picture")
    image_size = readable_image_size(operation["image"], f"{location}.image")
    blip = target.element.find(f"{qn('p:blipFill')}/{qn('a:blip')}")
    if blip is None:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}.shape: {target.label} has no image to swap", f"{location}.shape"))

    def change() -> str:
        old_relationship = blip.get(qn("r:embed"))
        _, new_relationship = target.slide.part.get_or_add_image_part(operation["image"])
        blip.set(qn("r:embed"), new_relationship)
        drop_unreferenced(target.slide.part, old_relationship)
        frame = local_box(target.element, slide_context(editing.presentation, target.slide))
        crop_to_fill(target.shape, image_size, frame)
        editing.mark_edited(target.slide)
        return f"replaced the image of {target.label} with {operation['image']}, cropped to its frame"
    return change


def readable_image_size(path: str, location: str) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            if image.format not in OFFICE_PICTURE_FORMATS:
                raise OfficeFailure(PICTURE_UNREADABLE.issue(f"{location}: {path} is a {image.format} image", location))
            return image.size
    except FileNotFoundError as error:
        raise OfficeFailure(INPUT_NOT_FOUND.issue(f"{location}: {path} does not exist", location)) from error
    except UnidentifiedImageError as error:
        raise OfficeFailure(PICTURE_UNREADABLE.issue(f"{location}: {path} is not an image", location)) from error


def crop_to_fill(picture, image_size: tuple[int, int], frame: Box) -> None:
    image_ratio = image_size[0] / image_size[1]
    frame_ratio = frame.w / frame.h if frame.h else image_ratio
    horizontal = max(0.0, (1 - frame_ratio / image_ratio) / 2)
    vertical = max(0.0, (1 - image_ratio / frame_ratio) / 2)
    picture.crop_left = picture.crop_right = horizontal
    picture.crop_top = picture.crop_bottom = vertical


ELEMENT_PLANNERS = {
    "set_transform": plan_set_transform,
    "delete_shape": plan_delete_shape,
    "duplicate_shape": plan_duplicate_shape,
    "set_z_order": plan_set_z_order,
    "set_fill": plan_set_fill,
    "set_line": plan_set_line,
    "replace_picture": plan_replace_picture,
}
