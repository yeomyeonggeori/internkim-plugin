from __future__ import annotations

from dataclasses import dataclass
import html

from pptx.oxml.ns import qn

from pptx_preview_paint import element, pixels, point_pixels
from pptx_style import is_east_asian, paragraph_chain, resolve_color, run_style
from pptx_text_measure import DEFAULT_INSETS, autofit_scale, font_face, line_height_points, line_spacing, paragraph_spacing, paragraph_value


ALIGNMENTS = {"l": "left", "ctr": "center", "r": "right", "just": "justify", "dist": "justify"}
ANCHORS = {"t": "flex-start", "ctr": "center", "b": "flex-end"}
BULLET_TAGS = (qn("a:buNone"), qn("a:buChar"), qn("a:buAutoNum"), qn("a:buBlip"))
TEXT_TAGS = (qn("a:r"), qn("a:fld"))
NUMBER_FORMATS = {
    "arabicPeriod": "{number}.",
    "arabicParenR": "{number})",
    "arabicParenBoth": "({number})",
    "arabicPlain": "{number}",
    "alphaLcPeriod": "{lower}.",
    "alphaLcParenR": "{lower})",
    "alphaUcPeriod": "{upper}.",
    "alphaUcParenR": "{upper})",
}
NON_BREAKING_SPACE = " "


@dataclass(frozen=True)
class BodyLayout:
    insets: dict
    anchor: str
    wraps: bool
    font_scale: float
    spacing_reduction: float


@dataclass(frozen=True)
class TextPaint:
    context: object
    shape_element: object
    faces: set
    color_override: str | None = None
    bold_by_default: bool = False


def body_layout(context, shape_element, body, inherited_bodies: list, cell_properties=None) -> BodyLayout:
    candidates = [body.find(qn("a:bodyPr")), *(inherited.find(qn("a:bodyPr")) for inherited in inherited_bodies)]
    candidates = [candidate for candidate in candidates if candidate is not None]

    def attribute(name: str, default: str) -> str:
        return next((candidate.get(name) for candidate in candidates if candidate.get(name) is not None), default)
    insets = {name: int(attribute(name, str(default))) for name, default in DEFAULT_INSETS.items()}
    anchor = attribute("anchor", "t")
    if cell_properties is not None:
        insets = {"lIns": int(cell_properties.get("marL", "91440")), "rIns": int(cell_properties.get("marR", "91440")), "tIns": int(cell_properties.get("marT", "45720")), "bIns": int(cell_properties.get("marB", "45720"))}
        anchor = cell_properties.get("anchor", "t")
    font_scale, spacing_reduction = autofit_scale(candidates[0]) if candidates else (1.0, 0.0)
    return BodyLayout(insets, anchor, attribute("wrap", "square") != "none", font_scale, spacing_reduction)


def body_html(paint: TextPaint, body, layout: BodyLayout) -> str:
    paragraphs, counters = [], {}
    for paragraph in body.findall(qn("a:p")):
        paragraphs.append(paragraph_html(paint, paragraph, layout, counters))
    container = {
        "position": "absolute",
        "left": "0px",
        "top": "0px",
        "width": "100%",
        "height": "100%",
        "box-sizing": "border-box",
        "display": "flex",
        "flex-direction": "column",
        "justify-content": ANCHORS.get(layout.anchor, "flex-start"),
        "padding": " ".join(f"{pixels(layout.insets[name])}px" for name in ("tIns", "rIns", "bIns", "lIns")),
    }
    return element("div", container, "".join(paragraphs))


def paragraph_html(paint: TextPaint, paragraph, layout: BodyLayout, counters: dict) -> str:
    chain = paragraph_chain(paint.context, paint.shape_element, paragraph)
    spans, first_size = runs_html(paint, paragraph, chain, layout)
    margin = paragraph_value(chain, "marL", 0)
    indent = paragraph_value(chain, "indent", 0)
    properties = {
        "position": "relative",
        "text-align": ALIGNMENTS.get(paragraph_text_attribute(chain, "algn", "l"), "left"),
        "padding-left": f"{pixels(margin)}px",
        "margin-top": f"{point_pixels(paragraph_spacing(chain, 'a:spcBef', first_size))}px",
        "margin-bottom": f"{point_pixels(paragraph_spacing(chain, 'a:spcAft', first_size))}px",
        "white-space": "pre-wrap" if layout.wraps else "pre",
        "word-break": "keep-all",
        "overflow-wrap": "break-word",
    }
    marker = bullet_text(chain, paragraph, counters)
    if marker and paragraph_has_text(paragraph):
        spans = bullet_html(paint, marker, paragraph, chain, layout, margin + indent) + spans
    elif indent > 0:
        properties["text-indent"] = f"{pixels(indent)}px"
    return element("div", properties, spans)


def paragraph_text_attribute(chain: list, name: str, default: str) -> str:
    return next((level.paragraph_properties.get(name) for level in chain if level.paragraph_properties.get(name) is not None), default)


def paragraph_has_text(paragraph) -> bool:
    return any((node.text or "").strip() for node in paragraph.iter(qn("a:t")))


def runs_html(paint: TextPaint, paragraph, chain: list, layout: BodyLayout) -> tuple[str, float]:
    pieces, first_size = [], None
    spacing = line_spacing(chain, layout.spacing_reduction)
    for child in paragraph:
        if child.tag == qn("a:br"):
            pieces.append("<br/>")
        elif child.tag in TEXT_TAGS:
            style = run_style(paint.context, paint.shape_element, paragraph, child.find(qn("a:rPr")))
            first_size = first_size if first_size is not None else style.size.value
            pieces.extend(segment_html(paint, segment, style, child.find(qn("a:rPr")), layout, spacing) for segment in script_segments(child.findtext(qn("a:t")) or ""))
    if first_size is None:
        style = run_style(paint.context, paint.shape_element, paragraph, paragraph.find(qn("a:endParaRPr")))
        first_size = style.size.value
        pieces.append(segment_html(paint, NON_BREAKING_SPACE, style, None, layout, spacing))
    return "".join(pieces), first_size


def script_segments(text: str) -> list[str]:
    segments = []
    for character in text:
        if segments and is_east_asian(segments[-1][-1]) == is_east_asian(character):
            segments[-1] += character
        else:
            segments.append(character)
    return segments


def segment_html(paint: TextPaint, text: str, style, run_properties, layout: BodyLayout, spacing: tuple[str, float]) -> str:
    bold = style.bold.value or paint.bold_by_default and (run_properties is None or run_properties.get("b") is None)
    east_asian = any(is_east_asian(character) for character in text)
    face = font_face(style.font_for(text).value, bold, east_asian)
    paint.faces.add((style.font_for(text).value, face))
    size = style.size.value * layout.font_scale
    mode, amount = spacing
    line_height = amount if mode == "points" else line_height_points(face, size) * amount
    color = style.color.value
    if paint.color_override and (run_properties is None or run_properties.find(qn("a:solidFill")) is None):
        color = paint.color_override
    properties = {
        "font-family": f"'{face.family}'",
        "font-size": f"{point_pixels(size)}px",
        "font-weight": "700" if bold else "400",
        "font-style": "italic" if style.italic.value else None,
        "text-decoration": "underline" if run_properties is not None and run_properties.get("u", "none") != "none" else None,
        "color": color or "#000000",
        "line-height": f"{point_pixels(line_height)}px",
        "letter-spacing": f"{point_pixels(style.character_spacing.value * layout.font_scale)}px" if style.character_spacing.value else None,
    }
    return element("span", properties, html.escape(text))


def bullet_text(chain: list, paragraph, counters: dict) -> str:
    level = int(paragraph.find(qn("a:pPr")).get("lvl", "0")) if paragraph.find(qn("a:pPr")) is not None else 0
    marker = next((child for entry in chain for child in entry.paragraph_properties if child.tag in BULLET_TAGS), None)
    if marker is None or marker.tag in (qn("a:buNone"), qn("a:buBlip")):
        counters.pop(level, None)
        return ""
    if marker.tag == qn("a:buChar"):
        counters.pop(level, None)
        return marker.get("char", "•")
    number = counters.get(level, int(marker.get("startAt", "1")) - 1) + 1
    counters[level] = number
    letter = chr(ord("a") + (number - 1) % 26)
    return NUMBER_FORMATS.get(marker.get("type", "arabicPeriod"), "{number}.").format(number=number, lower=letter, upper=letter.upper())


def bullet_html(paint: TextPaint, marker: str, paragraph, chain: list, layout: BodyLayout, left: int) -> str:
    first = next((child for child in paragraph if child.tag in TEXT_TAGS), None)
    style = run_style(paint.context, paint.shape_element, paragraph, first.find(qn("a:rPr")) if first is not None else None)
    color_element = next((child.find(qn("a:buClr")) for child in (entry.paragraph_properties for entry in chain) if child.find(qn("a:buClr")) is not None), None)
    color = resolve_color(paint.context, color_element[0]) if color_element is not None and len(color_element) else style.color.value
    face = font_face(style.latin_font.value, style.bold.value, False)
    size = style.size.value * layout.font_scale
    properties = {
        "position": "absolute",
        "left": f"{pixels(left)}px",
        "top": "0px",
        "font-family": f"'{face.family}'",
        "font-size": f"{point_pixels(size)}px",
        "line-height": f"{point_pixels(line_height_points(face, size))}px",
        "color": color or "#000000",
    }
    return element("span", properties, html.escape(marker))

