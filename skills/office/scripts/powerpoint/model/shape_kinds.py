from __future__ import annotations

from pptx.oxml.ns import qn


TABLE_URI = "http://schemas.openxmlformats.org/drawingml/2006/table"
CHART_URI = "http://schemas.openxmlformats.org/drawingml/2006/chart"
DIAGRAM_URI = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
MEDIA_TAGS = (qn("a:videoFile"), qn("a:audioFile"), qn("a:quickTimeFile"))
NON_VISUAL_TAGS = {qn("p:nvSpPr"), qn("p:nvPicPr"), qn("p:nvGraphicFramePr"), qn("p:nvGrpSpPr"), qn("p:nvCxnSpPr")}


def shape_kind(element) -> str:
    tag = element.tag
    if tag == qn("p:grpSp"):
        return "group"
    if tag == qn("p:cxnSp"):
        return "connector"
    if tag == qn("p:pic"):
        return "media" if any(element.iter(*MEDIA_TAGS)) else "picture"
    if tag == qn("p:graphicFrame"):
        return graphic_frame_kind(element)
    if tag == qn("p:sp"):
        return "text" if is_text_box(element) or placeholder_of(element) is not None else "shape"
    return "object"


def graphic_frame_kind(element) -> str:
    graphic_data = element.find(f"{qn('a:graphic')}/{qn('a:graphicData')}")
    uri = graphic_data.get("uri") if graphic_data is not None else ""
    return {TABLE_URI: "table", CHART_URI: "chart", DIAGRAM_URI: "diagram"}.get(uri, "object")


def is_text_box(element) -> bool:
    properties = element.find(f"{qn('p:nvSpPr')}/{qn('p:cNvSpPr')}")
    return properties is not None and properties.get("txBox") in ("1", "true")


def non_visual_properties(element):
    return next((child for child in element if child.tag in NON_VISUAL_TAGS), None)


def placeholder_of(element):
    properties = non_visual_properties(element)
    if properties is None:
        return None
    return properties.find(f"{qn('p:nvPr')}/{qn('p:ph')}")


def placeholder_type(element) -> str | None:
    placeholder = placeholder_of(element)
    if placeholder is None:
        return None
    return placeholder.get("type", "obj")


def shape_identifier(element) -> int:
    properties = non_visual_properties(element)
    return int(properties[0].get("id"))


def shape_address(prefix: str, index: int) -> str:
    return f"{prefix}.{index}" if prefix else str(index)


def shape_reference(address: str) -> int | str:
    return int(address) if address.isdigit() else address
