from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


STRAIGHT_GEOMETRY = "straightConnector1"
ELBOW_GEOMETRY = "bentConnector3"
QUARTER_TURN = 5400000
ARROW_HEAD = "triangle"
RECTANGLE_SITES = {"top": 0, "left": 1, "bottom": 2, "right": 3}
ELLIPSE_SITES = {"top": 0, "left": 2, "bottom": 4, "right": 6}
CONNECTION_SITES = {"rect": RECTANGLE_SITES, "roundRect": RECTANGLE_SITES, "round2SameRect": RECTANGLE_SITES, "diamond": RECTANGLE_SITES, "ellipse": ELLIPSE_SITES}
ARROW_ENDS = {"none": (False, False), "end": (False, True), "start": (True, False), "both": (True, True)}


class Rectangle(Protocol):
    x: int
    y: int
    w: int
    h: int
    right: int
    bottom: int


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class Attachment:
    shape_id: int
    site: int


@dataclass(frozen=True)
class Route:
    start: Point
    end: Point
    sides: tuple[str, str]
    vertical: bool


def facing_route(first: Rectangle, second: Rectangle) -> Route:
    horizontal_gap = max(second.x - first.right, first.x - second.right)
    vertical_gap = max(second.y - first.bottom, first.y - second.bottom)
    if vertical_gap > horizontal_gap:
        downward = second.y >= first.bottom
        sides = ("bottom", "top") if downward else ("top", "bottom")
        return Route(side_point(first, sides[0]), side_point(second, sides[1]), sides, True)
    rightward = second.x >= first.right
    sides = ("right", "left") if rightward else ("left", "right")
    return Route(side_point(first, sides[0]), side_point(second, sides[1]), sides, False)


def side_point(box: Rectangle, side: str) -> Point:
    points = {
        "top": Point(box.x + box.w // 2, box.y),
        "bottom": Point(box.x + box.w // 2, box.bottom),
        "left": Point(box.x, box.y + box.h // 2),
        "right": Point(box.right, box.y + box.h // 2),
    }
    return points[side]


def connection_site(geometry: str | None, side: str) -> int | None:
    return CONNECTION_SITES.get(geometry or "", {}).get(side)


def transform_xml(start: Point, end: Point, elbow: bool, vertical: bool) -> str:
    if elbow and vertical:
        return turned_transform_xml(start, end)
    flips = flip_attributes(end.x < start.x, end.y < start.y)
    return (
        f'<a:xfrm{flips}><a:off x="{min(start.x, end.x)}" y="{min(start.y, end.y)}"/>'
        f'<a:ext cx="{abs(end.x - start.x)}" cy="{abs(end.y - start.y)}"/></a:xfrm>'
    )


def turned_transform_xml(start: Point, end: Point) -> str:
    length, breadth = abs(end.y - start.y), abs(end.x - start.x)
    center_x, center_y = (start.x + end.x) // 2, (start.y + end.y) // 2
    flips = flip_attributes(end.y < start.y, end.x > start.x)
    return (
        f'<a:xfrm rot="{QUARTER_TURN}"{flips}><a:off x="{center_x - length // 2}" y="{center_y - breadth // 2}"/>'
        f'<a:ext cx="{length}" cy="{breadth}"/></a:xfrm>'
    )


def flip_attributes(horizontal: bool, vertical: bool) -> str:
    return (' flipH="1"' if horizontal else "") + (' flipV="1"' if vertical else "")


def arrow_xml(arrow: str) -> str:
    at_start, at_end = ARROW_ENDS[arrow]
    return (f'<a:headEnd type="{ARROW_HEAD}"/>' if at_start else "") + (f'<a:tailEnd type="{ARROW_HEAD}"/>' if at_end else "")


def attachments_xml(start: Attachment | None, end: Attachment | None) -> str:
    connected = ""
    if start is not None:
        connected += f'<a:stCxn id="{start.shape_id}" idx="{start.site}"/>'
    if end is not None:
        connected += f'<a:endCxn id="{end.shape_id}" idx="{end.site}"/>'
    return connected


def connector_xml(shape_id: int, name: str, route: Route, elbow: bool, outline: str, attachments: tuple[Attachment | None, Attachment | None]) -> str:
    geometry = ELBOW_GEOMETRY if elbow else STRAIGHT_GEOMETRY
    return (
        f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvCxnSpPr>{attachments_xml(*attachments)}</p:cNvCxnSpPr><p:nvPr/></p:nvCxnSpPr>'
        f'<p:spPr>{transform_xml(route.start, route.end, elbow, route.vertical)}<a:prstGeom prst="{geometry}"><a:avLst/></a:prstGeom>{outline}</p:spPr></p:cxnSp>'
    )


def line_xml(width_emu: int, paint_xml: str, arrow: str) -> str:
    return f'<a:ln w="{width_emu}" cap="flat">{paint_xml}<a:round/>{arrow_xml(arrow)}</a:ln>'
