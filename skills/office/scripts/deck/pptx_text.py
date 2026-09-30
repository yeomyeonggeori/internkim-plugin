from __future__ import annotations

from dataclasses import dataclass
import html
import re

from css_color import Color, parse_css_color
from pptx_fonts import RunFont, run_font
from pptx_package import PRESENTATION_HEIGHT_EMU, PRESENTATION_WIDTH_EMU


EMU_PER_POINT = 12700
SINGLE_LINE_SLACK_RATIO = 0.1
SINGLE_LINE_SLACK_MINIMUM_PIXELS = 8
INVALID_XML_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
LANGUAGE_TAGS = {"ko": "ko-KR", "en": "en-US", "ja": "ja-JP", "zh": "zh-CN"}
BASELINE_SHIFTS = {"super": "30000", "sub": "-25000"}
KERNING_FROM_ONE_POINT = "100"
HYPERLINK_IN_TEXT_COLOR = (
    '<a:extLst><a:ext uri="{A12FA001-AC4F-418D-AE19-62706E023703}">'
    '<ahyp:hlinkClr xmlns:ahyp="http://schemas.microsoft.com/office/drawing/2018/hyperlinkcolor" val="tx"/>'
    "</a:ext></a:extLst>"
)


@dataclass(frozen=True)
class SlideScale:
    width_pixels: float
    height_pixels: float

    def x(self, pixels: float) -> int:
        return round(pixels * PRESENTATION_WIDTH_EMU / self.width_pixels)

    def y(self, pixels: float) -> int:
        return round(pixels * PRESENTATION_HEIGHT_EMU / self.height_pixels)

    def hundredths_of_point(self, pixels: float) -> int:
        return round(pixels * PRESENTATION_WIDTH_EMU / self.width_pixels / EMU_PER_POINT * 100)


@dataclass(frozen=True)
class Rectangle:
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class TextContext:
    scale: SlideScale
    language: str
    link_ids: dict[str, str]


def language_tag(document_language: str) -> str:
    if "-" in document_language:
        return document_language
    return LANGUAGE_TAGS.get(document_language.casefold(), "en-US")


def text_box_xml(shape_id: int, block: dict, context: TextContext) -> str:
    frame, insets = placed_frame(block, context.scale)
    scale = context.scale
    body_properties = (
        f'<a:bodyPr wrap="{"none" if block["noWrap"] else "square"}" lIns="{scale.x(insets.left)}" tIns="{scale.y(insets.top)}" '
        f'rIns="{scale.x(insets.right)}" bIns="{scale.y(insets.bottom)}" anchor="{block["anchor"]}" rtlCol="0"><a:noAutofit/></a:bodyPr>'
    )
    paragraphs = "".join(paragraph_xml(paragraph, block, context) for paragraph in block["paragraphs"])
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Editable Overlay"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{scale.x(frame.left)}" y="{scale.y(frame.top)}"/>'
        f'<a:ext cx="{scale.x(frame.right - frame.left)}" cy="{scale.y(frame.bottom - frame.top)}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
        f"<p:txBody>{body_properties}<a:lstStyle/>{paragraphs}</p:txBody></p:sp>"
    )


def placed_frame(block: dict, scale: SlideScale) -> tuple[Rectangle, Rectangle]:
    box, insets = block["box"], block["insets"]
    shift = block["firstLineHalfLeading"]
    left, top, right, bottom = box["left"], box["top"], box["right"], box["bottom"]
    top_inset, bottom_inset = insets["top"] - shift, insets["bottom"] + shift
    if top_inset < 0:
        top, top_inset = top + top_inset, 0
    if bottom_inset < 0:
        bottom, bottom_inset = bottom - bottom_inset, 0
    left, right = widened_for_single_line(block, left, right)
    frame = Rectangle(max(0, left), max(0, top), min(scale.width_pixels, right), min(scale.height_pixels, bottom))
    return frame, Rectangle(insets["left"], top_inset, insets["right"], bottom_inset)


def widened_for_single_line(block: dict, left: float, right: float) -> tuple[float, float]:
    if not block["singleLine"] or block["noWrap"]:
        return left, right
    slack = max(SINGLE_LINE_SLACK_MINIMUM_PIXELS, (right - left) * SINGLE_LINE_SLACK_RATIO)
    alignment = block["paragraphs"][0]["alignment"]
    if alignment == "r":
        return left - slack, right
    if alignment == "ctr":
        return left - slack / 2, right + slack / 2
    return left, right + slack


def paragraph_xml(paragraph: dict, block: dict, context: TextContext) -> str:
    text_runs = [run for run in paragraph["runs"] if not run.get("isBreak")]
    runs = "".join(line_break_xml(paragraph["runs"], index, context) if run.get("isBreak") else run_xml(run, context) for index, run in enumerate(paragraph["runs"]))
    end_properties = run_properties_xml(text_runs[-1], context, "a:endParaRPr", with_link=False) if text_runs else ""
    return f"<a:p>{paragraph_properties_xml(paragraph, block, context)}{runs}{end_properties}</a:p>"


def paragraph_properties_xml(paragraph: dict, block: dict, context: TextContext) -> str:
    scale = context.scale
    attributes = f' marL="{scale.x(paragraph.get("marginLeftPx", 0))}" indent="{scale.x(paragraph.get("indentPx", 0))}" algn="{paragraph["alignment"]}"'
    attributes += f' eaLnBrk="{"0" if block["keepWords"] else "1"}" latinLnBrk="0"'
    line_spacing = f'<a:lnSpc><a:spcPts val="{scale.hundredths_of_point(paragraph["lineHeightPx"])}"/></a:lnSpc>' if paragraph["lineHeightPx"] else ""
    spacing = f'<a:spcBef><a:spcPts val="{scale.hundredths_of_point(paragraph["spaceBeforePx"])}"/></a:spcBef><a:spcAft><a:spcPts val="0"/></a:spcAft>'
    return f"<a:pPr{attributes}>{line_spacing}{spacing}{bullet_xml(paragraph)}</a:pPr>"


def bullet_xml(paragraph: dict) -> str:
    bullet = paragraph["bullet"]
    if not bullet:
        return "<a:buNone/>"
    first_run = next(run for run in paragraph["runs"] if not run.get("isBreak"))
    font = run_font(first_run["fontFamily"], first_run["fontWeight"])
    color = f'<a:buClr>{color_xml(parse_css_color(bullet["color"]), 1.0)}</a:buClr><a:buSzPct val="100000"/><a:buFont typeface="{attribute(font.east_asian)}"/>'
    if bullet["numbering"]:
        return f'{color}<a:buAutoNum type="{bullet["numbering"]}" startAt="{bullet["startAt"]}"/>'
    return f'{color}<a:buChar char="{attribute(bullet["character"])}"/>'


def run_xml(run: dict, context: TextContext) -> str:
    return f"<a:r>{run_properties_xml(run, context, 'a:rPr', with_link=True)}<a:t>{text_content(run['text'])}</a:t></a:r>"


def line_break_xml(runs: list[dict], index: int, context: TextContext) -> str:
    neighbor = next((run for run in reversed(runs[:index]) if not run.get("isBreak")), None) or next((run for run in runs[index:] if not run.get("isBreak")), None)
    if neighbor is None:
        return "<a:br/>"
    return f"<a:br>{run_properties_xml(neighbor, context, 'a:rPr', with_link=False)}</a:br>"


def run_properties_xml(run: dict, context: TextContext, tag: str, with_link: bool) -> str:
    font = run_font(run["fontFamily"], run["fontWeight"])
    color = parse_css_color(run["color"])
    link = context.link_ids.get(run.get("href") or "") if with_link else None
    return (
        f"<{tag}{run_attributes(run, font, context)}>"
        f'<a:solidFill>{color_xml(color, run["opacity"])}</a:solidFill>'
        f'<a:latin typeface="{attribute(font.latin)}"/><a:ea typeface="{attribute(font.east_asian)}"/><a:cs typeface="{attribute(font.latin)}"/>'
        + (f'<a:hlinkClick r:id="{link}">{HYPERLINK_IN_TEXT_COLOR}</a:hlinkClick>' if link else "")
        + f"</{tag}>"
    )


def run_attributes(run: dict, font: RunFont, context: TextContext) -> str:
    attributes = [f'lang="{context.language}"', f'sz="{max(100, context.scale.hundredths_of_point(run["sizePx"]))}"']
    if font.bold:
        attributes.append('b="1"')
    if run["italic"]:
        attributes.append('i="1"')
    if run["underline"]:
        attributes.append('u="sng"')
    if run["strike"]:
        attributes.append('strike="sngStrike"')
    if run["letterSpacingPx"]:
        attributes.append(f'spc="{context.scale.hundredths_of_point(run["letterSpacingPx"])}"')
    if run["baseline"]:
        attributes.append(f'baseline="{BASELINE_SHIFTS[run["baseline"]]}"')
    attributes.append(f'kern="{KERNING_FROM_ONE_POINT}" dirty="0"')
    return " " + " ".join(attributes)


def color_xml(color: Color, opacity: float) -> str:
    alpha = color.alpha * opacity
    alpha_xml = f'<a:alpha val="{round(alpha * 100000)}"/>' if alpha < 1 else ""
    return f'<a:srgbClr val="{color.hex_value}">{alpha_xml}</a:srgbClr>'


def text_content(text: str) -> str:
    return html.escape(INVALID_XML_CHARACTERS.sub("", text), quote=False)


def attribute(text: str) -> str:
    return html.escape(text, quote=True)
