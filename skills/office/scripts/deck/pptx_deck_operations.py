from __future__ import annotations

from lxml import etree
from pptx.opc.constants import RELATIONSHIP_TYPE
from pptx.oxml.ns import qn
from pptx.util import Emu

from core.office_operations import Change
from core.office_result import INVALID_VALUE, OfficeFailure
from core.office_schema import closest_suggestion
from core.office_theme import THEME_SLOTS
from deck.pptx_element_operations import SHAPE_TAGS, write_local_box
from deck.pptx_geometry import Box, own_box
from deck.pptx_style import HANGUL_SCRIPT
from deck.pptx_targets import PptxEditing, live_slides


def theme_parts(presentation) -> list:
    parts = []
    for master in presentation.slide_masters:
        part = master.part.part_related_by(RELATIONSHIP_TYPE.THEME)
        if all(existing is not part for existing in parts):
            parts.append(part)
    return parts


def plan_set_theme(editing: PptxEditing, operation: dict, location: str) -> Change:
    colors = operation.get("colors") or {}
    unknown = [slot for slot in colors if slot not in THEME_SLOTS]
    if unknown:
        fallback = "use " + ", ".join(THEME_SLOTS)
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.colors.{unknown[0]}: not a theme color slot", f"{location}.colors.{unknown[0]}", closest_suggestion(unknown[0], list(THEME_SLOTS), "did you mean {match!r}?") or fallback))
    if not colors and all(operation.get(name) is None for name in ("headingFont", "bodyFont", "koreanFont")):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: set_theme changes nothing", location, "give colors, headingFont, bodyFont or koreanFont"))

    def change() -> str:
        parts = theme_parts(editing.presentation)
        for part in parts:
            theme = etree.fromstring(part.blob)
            set_theme_colors(theme, colors)
            set_theme_fonts(theme, operation)
            part._blob = etree.tostring(theme, xml_declaration=True, encoding="UTF-8", standalone=True)
        for slide in live_slides(editing):
            editing.mark_edited(slide)
        return f"changed {len(parts)} theme{'s' if len(parts) != 1 else ''}"
    return change


def set_theme_colors(theme, colors: dict) -> None:
    scheme = theme.find(f"{qn('a:themeElements')}/{qn('a:clrScheme')}")
    for slot, color in colors.items():
        entry = scheme.find(qn(f"a:{slot}"))
        for child in list(entry):
            entry.remove(child)
        etree.SubElement(entry, qn("a:srgbClr")).set("val", color.lstrip("#").upper())


def set_theme_fonts(theme, operation: dict) -> None:
    font_scheme = theme.find(f"{qn('a:themeElements')}/{qn('a:fontScheme')}")
    for scheme_name, latin_field in (("a:majorFont", "headingFont"), ("a:minorFont", "bodyFont")):
        fonts = font_scheme.find(qn(scheme_name))
        if operation.get(latin_field):
            fonts.find(qn("a:latin")).set("typeface", operation[latin_field])
        if operation.get("koreanFont"):
            fonts.find(qn("a:ea")).set("typeface", operation["koreanFont"])
            script_font(fonts, HANGUL_SCRIPT).set("typeface", operation["koreanFont"])


def script_font(fonts, script: str):
    existing = next((font for font in fonts.findall(qn("a:font")) if font.get("script") == script), None)
    if existing is not None:
        return existing
    created = etree.SubElement(fonts, qn("a:font"))
    created.set("script", script)
    return created


def plan_set_slide_size(editing: PptxEditing, operation: dict, location: str) -> Change:
    presentation = editing.presentation

    def change() -> str:
        width_ratio = operation["width"] / presentation.slide_width
        height_ratio = operation["height"] / presentation.slide_height
        presentation.slide_width, presentation.slide_height = Emu(operation["width"]), Emu(operation["height"])
        if operation.get("scaleContent", True) is not False:
            for owner in scaled_owners(editing):
                scale_shapes(owner._element, width_ratio, height_ratio)
        for slide in live_slides(editing):
            editing.mark_edited(slide)
        return f"set the slide size to {operation['width']} x {operation['height']} EMU"
    return change


def scaled_owners(editing: PptxEditing) -> list:
    masters = list(editing.presentation.slide_masters)
    layouts = [layout for master in masters for layout in master.slide_layouts]
    return [*live_slides(editing), *layouts, *masters]


def scale_shapes(owner_element, width_ratio: float, height_ratio: float) -> None:
    tree = owner_element.find(f"{qn('p:cSld')}/{qn('p:spTree')}")
    for element in [child for child in tree if child.tag in SHAPE_TAGS]:
        box = own_box(element)
        if box is not None:
            write_local_box(element, Box(round(box.x * width_ratio), round(box.y * height_ratio), round(box.w * width_ratio), round(box.h * height_ratio)))


DECK_PLANNERS = {
    "set_theme": plan_set_theme,
    "set_slide_size": plan_set_slide_size,
}
