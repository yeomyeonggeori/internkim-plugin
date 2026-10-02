from __future__ import annotations

from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Pt

from core.office_operations import Change
from core.office_result import INVALID_VALUE, OfficeFailure
from powerpoint.operations.backdrop import readable_text_color
from powerpoint.model.connectors import DEFAULT_ARROW, DEFAULT_WIDTH_POINTS, ELBOW_KIND, Attachment, Route, connection_site, connector_xml, facing_route, line_xml
from powerpoint.operations.elements import current_box, next_shape_identifier
from powerpoint.model.geometry import Box
from powerpoint.operations.targets import PptxEditing, ShapeTarget, resolve_shape


def plan_add_connector(editing: PptxEditing, operation: dict, location: str) -> Change:
    first = resolve_shape(editing, operation, location, "from")
    second = resolve_shape(editing, operation, location, "to")
    if first.element is second.element:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.to: a connector joins two different shapes", f"{location}.to", "name another shape from office read"))

    def change() -> str:
        route = facing_route(current_box(editing, first), current_box(editing, second))
        elbow = operation.get("kind") == ELBOW_KIND
        identifier = next_shape_identifier(first.slide._element)
        attachments = (attachment(first, route.sides[0]), attachment(second, route.sides[1]))
        paint = f'<a:solidFill><a:srgbClr val="{connector_color(editing, first, route, operation)}"/></a:solidFill>'
        width = Pt(operation.get("width", DEFAULT_WIDTH_POINTS))
        xml = connector_xml(identifier, f"Connector {identifier}", route, elbow, line_xml(int(width), paint, operation.get("arrow", DEFAULT_ARROW)), attachments)
        first.slide.shapes._spTree.insert_element_before(parse_xml(f'<p:spTree {nsdecls("p", "a")}>{xml}</p:spTree>')[0], "p:extLst")
        editing.mark_edited(first.slide)
        return f"connected {first.label} to shape {second.address} with an {'elbow' if elbow else 'straight'} connector {len(first.slide.shapes) - 1}"
    return change


def attachment(target: ShapeTarget, side: str) -> Attachment | None:
    geometry = target.element.find(f"{qn('p:spPr')}/{qn('a:prstGeom')}")
    site = connection_site(geometry.get("prst") if geometry is not None else None, side)
    return Attachment(target.shape.shape_id, site) if site is not None else None


def connector_color(editing: PptxEditing, target: ShapeTarget, route: Route, operation: dict) -> str:
    if operation.get("color"):
        return operation["color"].lstrip("#").upper()
    left, top = min(route.start.x, route.end.x), min(route.start.y, route.end.y)
    span = Box(left, top, max(abs(route.end.x - route.start.x), 1), max(abs(route.end.y - route.start.y), 1))
    return readable_text_color(editing.presentation, target.slide, span)
