from __future__ import annotations

from dataclasses import dataclass

from pptx.oxml.ns import qn

from units import EMU_PER_POINT


ROTATION_UNITS_PER_DEGREE = 60000


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def area(self) -> int:
        return max(self.w, 0) * max(self.h, 0)

    def intersection(self, other: "Box") -> "Box | None":
        left, top = max(self.x, other.x), max(self.y, other.y)
        right, bottom = min(self.right, other.right), min(self.bottom, other.bottom)
        if right <= left or bottom <= top:
            return None
        return Box(left, top, right - left, bottom - top)

    def to_json(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass(frozen=True)
class Frame:
    offset_x: float = 0.0
    offset_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0

    def to_slide(self, box: Box) -> Box:
        return Box(round(self.offset_x + box.x * self.scale_x), round(self.offset_y + box.y * self.scale_y), round(box.w * self.scale_x), round(box.h * self.scale_y))

    def to_local(self, box: Box) -> Box:
        return Box(round((box.x - self.offset_x) / self.scale_x), round((box.y - self.offset_y) / self.scale_y), round(box.w / self.scale_x), round(box.h / self.scale_y))


SLIDE_FRAME = Frame()


def child_frame(parent: Frame, group_element) -> Frame:
    transform = transform_of(group_element)
    offset, extent = transform.find(qn("a:off")), transform.find(qn("a:ext"))
    child_offset, child_extent = transform.find(qn("a:chOff")), transform.find(qn("a:chExt"))
    scale_x = ratio(int(extent.get("cx")), int(child_extent.get("cx")))
    scale_y = ratio(int(extent.get("cy")), int(child_extent.get("cy")))
    local_offset_x = int(offset.get("x")) - int(child_offset.get("x")) * scale_x
    local_offset_y = int(offset.get("y")) - int(child_offset.get("y")) * scale_y
    return Frame(parent.offset_x + parent.scale_x * local_offset_x, parent.offset_y + parent.scale_y * local_offset_y, parent.scale_x * scale_x, parent.scale_y * scale_y)


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def transform_of(element):
    if element.tag == qn("p:graphicFrame"):
        return element.find(qn("p:xfrm"))
    if element.tag == qn("p:grpSp"):
        return element.find(f"{qn('p:grpSpPr')}/{qn('a:xfrm')}")
    return element.find(f"{qn('p:spPr')}/{qn('a:xfrm')}")


def own_box(element) -> Box | None:
    transform = transform_of(element)
    if transform is None:
        return None
    offset, extent = transform.find(qn("a:off")), transform.find(qn("a:ext"))
    if offset is None or extent is None:
        return None
    return Box(int(offset.get("x")), int(offset.get("y")), int(extent.get("cx")), int(extent.get("cy")))


def local_box(element, context) -> Box:
    candidates = [element, *(inherited for _, inherited in context.placeholder_chain(element))] if context is not None else [element]
    return next((box for box in map(own_box, candidates) if box is not None), Box(0, 0, 0, 0))


def rotation_degrees(element) -> float:
    transform = transform_of(element)
    if transform is None:
        return 0.0
    return int(transform.get("rot", "0")) / ROTATION_UNITS_PER_DEGREE


def percent_of_slide(box: Box, slide_width: int, slide_height: int) -> dict:
    return {
        "x": round(100 * box.x / slide_width, 1),
        "y": round(100 * box.y / slide_height, 1),
        "w": round(100 * box.w / slide_width, 1),
        "h": round(100 * box.h / slide_height, 1),
    }


def points(box: Box) -> dict:
    return {name: round(value / EMU_PER_POINT, 1) for name, value in box.to_json().items()}
