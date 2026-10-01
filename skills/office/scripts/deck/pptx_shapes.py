from __future__ import annotations

from css_color import parse_css_color
from pptx_connectors import Attachment, Point, Route, connection_site, connector_xml, line_xml
from pptx_text import SlideScale, color_xml


MAXIMUM_CORNER_ADJUSTMENT = 50000
ADJUSTMENT_SCALE = 100000


def shape_xml(shape_id: int, shape: dict, scale: SlideScale) -> str:
    if shape["geometry"] == "line":
        return rule_xml(shape_id, shape, scale)
    return box_xml(shape_id, shape, scale)


def box_xml(shape_id: int, shape: dict, scale: SlideScale) -> str:
    box = shape["box"]
    width, height = scale.x(box["right"] - box["left"]), scale.y(box["bottom"] - box["top"])
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Box {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{scale.x(box["left"])}" y="{scale.y(box["top"])}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>'
        f"{preset_geometry_xml(shape, box)}{fill_xml(shape.get('fill'))}{outline_xml(shape.get('line'), scale)}</p:spPr></p:sp>"
    )


def preset_geometry_xml(shape: dict, box: dict) -> str:
    geometry = shape["geometry"]
    shorter_side = min(box["right"] - box["left"], box["bottom"] - box["top"])
    guides = ""
    if geometry == "roundRect":
        guides = guide_xml("adj", corner_adjustment(shape["radiusPx"], shorter_side))
    if geometry == "round2SameRect":
        guides = guide_xml("adj1", corner_adjustment(shape["radiusPx"], shorter_side)) + guide_xml("adj2", corner_adjustment(shape["bottomRadiusPx"], shorter_side))
    return f'<a:prstGeom prst="{geometry}"><a:avLst>{guides}</a:avLst></a:prstGeom>'


def corner_adjustment(radius_pixels: float, shorter_side_pixels: float) -> int:
    if shorter_side_pixels <= 0:
        return 0
    return min(MAXIMUM_CORNER_ADJUSTMENT, round(radius_pixels / shorter_side_pixels * ADJUSTMENT_SCALE))


def guide_xml(name: str, value: int) -> str:
    return f'<a:gd name="{name}" fmla="val {value}"/>'


def fill_xml(paint: dict | None) -> str:
    if not paint:
        return "<a:noFill/>"
    return f"<a:solidFill>{color_xml(parse_css_color(paint['color']), paint['opacity'])}</a:solidFill>"


def outline_xml(paint: dict | None, scale: SlideScale) -> str:
    if not paint:
        return "<a:ln><a:noFill/></a:ln>"
    return f'<a:ln w="{scale.x(paint["widthPx"])}" cap="flat">{fill_xml(paint)}<a:miter lim="800000"/></a:ln>'


def rule_xml(shape_id: int, shape: dict, scale: SlideScale) -> str:
    start, end = shape["from"], shape["to"]
    left, top = min(start["x"], end["x"]), min(start["y"], end["y"])
    flips = (' flipH="1"' if end["x"] < start["x"] else "") + (' flipV="1"' if end["y"] < start["y"] else "")
    return (
        f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{shape_id}" name="Rule {shape_id}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
        f'<p:spPr><a:xfrm{flips}><a:off x="{scale.x(left)}" y="{scale.y(top)}"/>'
        f'<a:ext cx="{scale.x(abs(end["x"] - start["x"]))}" cy="{scale.y(abs(end["y"] - start["y"]))}"/></a:xfrm>'
        f'<a:prstGeom prst="line"><a:avLst/></a:prstGeom>{outline_xml(shape["line"], scale)}</p:spPr></p:cxnSp>'
    )


def connectors_xml(connectors: list[dict], shapes: list[dict], first_shape_id: int, scale: SlideScale) -> str:
    exported = exported_shapes(shapes, first_shape_id)
    first_id = first_shape_id + len(shapes)
    return "".join(
        kit_connector_xml(shape_id, connector, exported, scale)
        for shape_id, connector in enumerate(connectors, start=first_id)
    )


def exported_shapes(shapes: list[dict], first_shape_id: int) -> dict[str, tuple[int, str]]:
    exported = {}
    for shape_id, shape in enumerate(shapes, start=first_shape_id):
        if shape.get("exportId") and shape["geometry"] != "line":
            exported.setdefault(shape["exportId"], (shape_id, shape["geometry"]))
    return exported


def kit_connector_xml(shape_id: int, connector: dict, exported: dict[str, tuple[int, str]], scale: SlideScale) -> str:
    start, end = connector["start"], connector["end"]
    sides = tuple(connector["sides"]) if connector.get("sides") else ("", "")
    route = Route(Point(scale.x(start["x"]), scale.y(start["y"])), Point(scale.x(end["x"]), scale.y(end["y"])), sides, sides[0] in ("top", "bottom"))
    attachments = (attachment(exported.get(connector.get("fromShape") or ""), sides[0]), attachment(exported.get(connector.get("toShape") or ""), sides[1]))
    outline = line_xml(scale.x(connector["line"]["widthPx"]), fill_xml({"color": connector["line"]["color"], "opacity": 1}), connector["arrow"])
    return connector_xml(shape_id, f"Connector {shape_id}", route, connector["elbow"], outline, attachments)


def attachment(exported: tuple[int, str] | None, side: str) -> Attachment | None:
    if exported is None:
        return None
    site = connection_site(exported[1], side)
    return Attachment(exported[0], site) if site is not None else None
