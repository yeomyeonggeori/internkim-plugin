from __future__ import annotations

from pptx.chart.plot import PlotTypeInspector
from pptx.oxml.ns import qn

from pptx_comments import slide_comments
from pptx_content import frame_text, notes_text
from pptx_geometry import SLIDE_FRAME, Frame, child_frame, local_box, percent_of_slide, points, rotation_degrees
from pptx_inheritance import SlideContext, slide_context
from pptx_section_operations import describe_sections
from pptx_shape_kinds import non_visual_properties, placeholder_type, shape_address, shape_identifier, shape_kind, shape_reference
from pptx_style import resolve_color, run_style


ALIGNMENT_NAMES = {"l": "left", "ctr": "center", "r": "right", "just": "justify", "dist": "distributed"}
TRANSITION_EXTRAS = ("sndAc", "extLst")
AUTOFIT_NAMES = {qn("a:noAutofit"): "none", qn("a:normAutofit"): "shrink", qn("a:spAutoFit"): "resize"}


def describe_presentation(presentation, numbers: list[int], detail: bool) -> dict:
    slides = list(presentation.slides)
    width, height = presentation.slide_width, presentation.slide_height
    description = {
        "slideCount": len(slides),
        "slideSize": {"w": width, "h": height, "unit": "EMU", "emuPerPoint": 12700},
        "layouts": [layout.name for master in presentation.slide_masters for layout in master.slide_layouts],
    }
    sections = describe_sections(presentation)
    if sections:
        description["sections"] = sections
    description["slides"] = [describe_slide(presentation, slides[number - 1], number, detail) for number in numbers]
    return description


def describe_slide(presentation, slide, number: int, detail: bool) -> dict:
    context = slide_context(presentation, slide)
    description = {"slide": number, "layout": slide.slide_layout.name}
    if slide._element.get("show") == "0":
        description["hidden"] = True
    description["shapes"] = describe_shapes(slide.shapes, "", SLIDE_FRAME, context, detail, (presentation.slide_width, presentation.slide_height))
    description["notes"] = notes_text(slide)
    transition = transition_details(slide._element)
    if transition:
        description["transition"] = transition
    comments = slide_comments(slide)
    if comments:
        description["comments"] = comments
    if detail and slide._element.find(qn("p:timing")) is not None:
        description["animated"] = sorted({target.get("spid") for target in slide._element.iter(qn("p:spTgt"))})
    return description


def describe_shapes(shapes, prefix: str, frame: Frame, context: SlideContext, detail: bool, slide_size: tuple[int, int]) -> list[dict]:
    return [describe_shape(shape, shape_address(prefix, index), frame, context, detail, slide_size) for index, shape in enumerate(shapes)]


def describe_shape(shape, address: str, frame: Frame, context: SlideContext, detail: bool, slide_size: tuple[int, int]) -> dict:
    element = shape._element
    kind = shape_kind(element)
    box = frame.to_slide(local_box(element, context))
    description = {"index": int(address) if address.isdigit() else address, "id": shape_identifier(element), "name": shape.name, "kind": kind}
    if placeholder_type(element) is not None:
        description["placeholder"] = placeholder_type(element)
    description["box"] = box.to_json()
    description["percent"] = percent_of_slide(box, *slide_size)
    if detail:
        description["points"] = points(box)
        rotation = rotation_degrees(element)
        if rotation:
            description["rotation"] = rotation
    link = link_target(shape.part, element.find(f".//{qn('p:cNvPr')}/{qn('a:hlinkClick')}"))
    if link:
        description["link"] = link
    description.update(kind_details(shape, kind, address, frame, context, detail, slide_size))
    return description


def link_target(part, link) -> str | None:
    if link is None:
        return None
    relationship_id = link.get(qn("r:id"))
    if relationship_id and relationship_id in part.rels:
        relationship = part.rels[relationship_id]
        if relationship.is_external:
            return relationship.target_ref
        slides = list(part.package.presentation_part.presentation.slides)
        number = next((index for index, slide in enumerate(slides, start=1) if slide.part is relationship.target_part), None)
        return f"slide {number}" if number else None
    return link.get("action")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def transition_details(slide_element) -> dict:
    transition = next(slide_element.iter(qn("p:transition")), None)
    if transition is None:
        return {}
    effect = next((local_name(child.tag) for child in transition if local_name(child.tag) not in TRANSITION_EXTRAS), "none")
    details = {"kind": effect, "speed": {"fast": "fast", "med": "medium", "slow": "slow"}.get(transition.get("spd", "fast"), "fast")}
    if transition.get("advTm"):
        details["advanceAfter"] = int(transition.get("advTm")) / 1000
    return details


def kind_details(shape, kind: str, address: str, frame: Frame, context: SlideContext, detail: bool, slide_size) -> dict:
    if kind == "group":
        return {"shapes": describe_shapes(shape.shapes, address, child_frame(frame, shape._element), context, detail, slide_size)}
    if kind == "table":
        return table_details(shape, detail)
    if kind == "chart":
        return {"chart": chart_details(shape.chart)}
    if kind == "connector":
        return connector_details(shape._element, address)
    details = {}
    if shape._element.find(qn("p:txBody")) is not None:
        details.update(text_details(shape, context, detail))
    if kind == "picture" and detail:
        details["picture"] = picture_details(shape)
    if detail and kind in ("shape", "text"):
        details.update(paint_details(shape, context))
    return details


def connector_details(element, address: str) -> dict:
    prefix = address.rpartition(".")[0]
    siblings = [child for child in element.getparent() if non_visual_properties(child) is not None]
    addresses = {shape_identifier(sibling): shape_address(prefix, index) for index, sibling in enumerate(siblings)}
    ends = {name: element.find(f"{qn('p:nvCxnSpPr')}/{qn('p:cNvCxnSpPr')}/{qn(tag)}") for name, tag in (("from", "a:stCxn"), ("to", "a:endCxn"))}
    connects = {name: shape_reference(addresses.get(int(end.get("id")))) for name, end in ends.items() if end is not None and int(end.get("id")) in addresses}
    return {"connects": connects} if connects else {}


def text_details(shape, context: SlideContext, detail: bool) -> dict:
    text_frame = shape.text_frame
    text = frame_text(text_frame)
    paragraphs = text_frame.paragraphs
    first_run = next((run for paragraph in paragraphs for run in paragraph.runs), None)
    first_paragraph = first_run._r.getparent() if first_run is not None else paragraphs[0]._p
    properties = first_run._r.find(qn("a:rPr")) if first_run is not None else paragraphs[0]._p.find(qn("a:endParaRPr"))
    details = {"text": text}
    if text.strip():
        details["style"] = run_style(context, shape._element, first_paragraph, properties).compact(text)
    if detail:
        details["frame"] = frame_details(shape._element)
        details["paragraphs"] = [paragraph_details(paragraph, shape._element, context) for paragraph in paragraphs]
    return details


def frame_details(element) -> dict:
    body_properties = element.find(f"{qn('p:txBody')}/{qn('a:bodyPr')}")
    autofit = next((AUTOFIT_NAMES[child.tag] for child in body_properties if child.tag in AUTOFIT_NAMES), "none")
    return {"autofit": autofit, "wrap": body_properties.get("wrap", "square") != "none", "anchor": body_properties.get("anchor", "t")}


def paragraph_details(paragraph, shape_element, context: SlideContext) -> dict:
    properties = paragraph._p.find(qn("a:pPr"))
    details = {"text": "".join(run.text for run in paragraph.runs), "level": paragraph.level}
    if properties is not None and properties.get("algn"):
        details["align"] = ALIGNMENT_NAMES.get(properties.get("algn"), properties.get("algn"))
    if properties is not None and properties.find(qn("a:buChar")) is not None:
        details["bullet"] = "bullet"
    elif properties is not None and properties.find(qn("a:buAutoNum")) is not None:
        details["bullet"] = "number"
    details["runs"] = [run_details(run, shape_element, paragraph, context) for run in paragraph.runs]
    return details


def run_details(run, shape_element, paragraph, context: SlideContext) -> dict:
    properties = run._r.find(qn("a:rPr"))
    details = {"text": run.text, **run_style(context, shape_element, paragraph._p, properties).detailed(run.text)}
    link = link_target(context.slide.part, properties.find(qn("a:hlinkClick")) if properties is not None else None)
    if link:
        details["link"] = link
    return details


def table_details(shape, detail: bool) -> dict:
    table = shape.table
    details = {"rows": [[frame_text(cell.text_frame) for cell in row.cells] for row in table.rows]}
    if detail:
        details["merged"] = [
            {"row": row_index, "column": column_index, "rows": cell.span_height, "columns": cell.span_width}
            for row_index, row in enumerate(table.rows)
            for column_index, cell in enumerate(row.cells)
            if cell.is_merge_origin
        ]
    return details


def chart_details(chart) -> dict:
    plots = list(chart.plots)
    plot_types = [plot_type(plot) for plot in plots]
    details = {"type": "+".join(dict.fromkeys(plot_types)) if plots else "unknown"}
    if chart.has_title and chart.chart_title.has_text_frame:
        details["title"] = frame_text(chart.chart_title.text_frame)
    details["categories"] = list(plots[0].categories) if plots else []
    details["series"] = [series_details(series, kind, len(plots) > 1) for plot, kind in zip(plots, plot_types) for series in plot.series]
    return details


def plot_type(plot) -> str:
    return PlotTypeInspector.chart_type(plot).name.lower()


def series_details(series, kind: str, names_plot: bool) -> dict:
    details = {"name": series.name, "values": list(series.values)}
    horizontal = series._element.find(qn("c:xVal"))
    if horizontal is not None:
        details["x"] = cached_numbers(horizontal)
    if names_plot:
        details["plot"] = kind
    return details


def cached_numbers(reference) -> list[float | None]:
    points = {int(point.get("idx")): point.findtext(qn("c:v")) for point in reference.iter(qn("c:pt"))}
    count = reference.find(f".//{qn('c:ptCount')}")
    length = int(count.get("val")) if count is not None else len(points)
    return [float(points[index]) if points.get(index) not in (None, "") else None for index in range(length)]


def picture_details(picture) -> dict:
    details = {"contentType": picture.image.content_type, "pixels": list(picture.image.size)}
    crop = {side: round(getattr(picture, f"crop_{side}"), 3) for side in ("left", "top", "right", "bottom")}
    if any(crop.values()):
        details["crop"] = crop
    return details


def paint_details(shape, context: SlideContext) -> dict:
    properties = shape._element.find(qn("p:spPr"))
    if properties is None:
        return {}
    details = {}
    fill = properties.find(qn("a:solidFill"))
    if fill is not None and len(fill):
        details["fill"] = resolve_color(context, fill[0])
    elif properties.find(qn("a:noFill")) is not None:
        details["fill"] = "none"
    line_fill = properties.find(f"{qn('a:ln')}/{qn('a:solidFill')}")
    if line_fill is not None and len(line_fill):
        details["line"] = resolve_color(context, line_fill[0])
    return details
