from __future__ import annotations

import colorsys
from dataclasses import dataclass

from pptx.oxml.ns import qn

from pptx_inheritance import SlideContext, master_text_style
from pptx_shape_kinds import placeholder_of


DEFAULT_SIZE = 18.0
DEFAULT_LATIN_FONT = "+mn-lt"
DEFAULT_EAST_ASIAN_FONT = "+mn-ea"
DEFAULT_TEXT_COLOR = "tx1"
HANGUL_SCRIPT = "Hang"
TRUE_VALUES = ("1", "true")
PERCENT_SCALE = 100000
SHAPE_ORIGINS = {"run", "paragraph", "shape"}


@dataclass(frozen=True)
class Styled:
    value: object
    origin: str

    def to_json(self) -> dict:
        return {"value": self.value, "from": self.origin}


@dataclass(frozen=True)
class RunStyle:
    latin_font: Styled
    east_asian_font: Styled
    size: Styled
    bold: Styled
    italic: Styled
    color: Styled

    def font_for(self, text: str) -> Styled:
        return self.east_asian_font if has_east_asian(text) else self.latin_font

    def compact(self, text: str) -> dict:
        return {"font": self.font_for(text).value, "size": self.size.value, "bold": self.bold.value, "color": self.color.value}

    def detailed(self, text: str) -> dict:
        details = {name: getattr(self, name).to_json() for name in ("size", "bold", "italic", "color")}
        details["font"] = self.font_for(text).to_json()
        return details


@dataclass(frozen=True)
class ParagraphLevel:
    origin: str
    paragraph_properties: object


def has_east_asian(text: str) -> bool:
    return any(is_east_asian(character) for character in text)


def is_east_asian(character: str) -> bool:
    code = ord(character)
    return 0x1100 <= code <= 0x11FF or 0x2E80 <= code <= 0x9FFF or 0xAC00 <= code <= 0xD7AF or 0xF900 <= code <= 0xFAFF or 0xFF00 <= code <= 0xFFEF


def paragraph_chain(context: SlideContext | None, shape_element, paragraph_element) -> list[ParagraphLevel]:
    level = int(own_paragraph_properties(paragraph_element).get("lvl", "0")) if own_paragraph_properties(paragraph_element) is not None else 0
    level_tag = qn(f"a:lvl{level + 1}pPr")
    chain = [ParagraphLevel("paragraph", own_paragraph_properties(paragraph_element))]
    chain.append(ParagraphLevel("shape", list_style_level(shape_element, level_tag)))
    if context is None:
        return [entry for entry in chain if entry.paragraph_properties is not None]
    if placeholder_of(shape_element) is not None:
        chain.extend(ParagraphLevel(origin, list_style_level(inherited, level_tag)) for origin, inherited in context.placeholder_chain(shape_element))
        master_style = master_text_style(context, shape_element)
        chain.append(ParagraphLevel("master", master_style.find(level_tag) if master_style is not None else None))
    else:
        chain.append(ParagraphLevel("theme", context.theme_element.find(f"{qn('a:objectDefaults')}/{qn('a:txDef')}/{qn('a:lstStyle')}/{level_tag}")))
        chain.append(ParagraphLevel("presentation", context.presentation_element.find(f"{qn('p:defaultTextStyle')}/{level_tag}")))
    return [entry for entry in chain if entry.paragraph_properties is not None]


def own_paragraph_properties(paragraph_element):
    return paragraph_element.find(qn("a:pPr"))


def list_style_level(shape_element, level_tag):
    body = shape_element.find(qn("p:txBody"))
    if body is None:
        return None
    return body.find(f"{qn('a:lstStyle')}/{level_tag}")


def run_style(context: SlideContext | None, shape_element, paragraph_element, run_properties) -> RunStyle:
    levels = [("run", run_properties)] if run_properties is not None else []
    levels.extend((entry.origin, entry.paragraph_properties.find(qn("a:defRPr"))) for entry in paragraph_chain(context, shape_element, paragraph_element))
    levels = [(origin, element) for origin, element in levels if element is not None]
    size = first_attribute(levels, "sz", lambda value: int(value) / 100, DEFAULT_SIZE)
    bold = first_attribute(levels, "b", lambda value: value in TRUE_VALUES, False)
    italic = first_attribute(levels, "i", lambda value: value in TRUE_VALUES, False)
    latin = first_typeface(levels, "a:latin", DEFAULT_LATIN_FONT)
    east_asian = first_typeface(levels, "a:ea", DEFAULT_EAST_ASIAN_FONT)
    color = first_color(levels, shape_element)
    if context is None:
        return RunStyle(latin, east_asian, size, bold, italic, color)
    return RunStyle(
        resolve_typeface(context, latin, ""),
        resolve_typeface(context, east_asian, HANGUL_SCRIPT),
        size,
        bold,
        italic,
        Styled(resolve_color(context, color.value), color.origin) if color.value is not None else color,
    )


def first_attribute(levels: list, attribute: str, convert, default) -> Styled:
    for origin, element in levels:
        value = element.get(attribute)
        if value is not None:
            return Styled(convert(value), origin)
    return Styled(default, "default")


def first_typeface(levels: list, tag: str, default: str) -> Styled:
    for origin, element in levels:
        font = element.find(qn(tag))
        if font is not None and font.get("typeface"):
            return Styled(font.get("typeface"), origin)
    return Styled(default, "theme")


def first_color(levels: list, shape_element) -> Styled:
    own_levels = [level for level in levels if level[0] in SHAPE_ORIGINS]
    inherited_levels = [level for level in levels if level[0] not in SHAPE_ORIGINS]
    font_reference = shape_element.find(f"{qn('p:style')}/{qn('a:fontRef')}")
    shape_style = [("shape", font_reference)] if font_reference is not None else []
    for origin, element in own_levels + shape_style + inherited_levels:
        color = element if element.tag == qn("a:fontRef") else element.find(qn("a:solidFill"))
        if color is not None and len(color):
            return Styled(color[0], origin)
    return Styled(DEFAULT_TEXT_COLOR, "theme")


def resolve_typeface(context: SlideContext, typeface: Styled, script: str) -> Styled:
    name = typeface.value
    if not name.startswith("+"):
        return typeface
    scheme = "a:majorFont" if name.startswith("+mj") else "a:minorFont"
    slot = {"lt": "a:latin", "ea": "a:ea", "cs": "a:cs"}.get(name[-2:], "a:latin")
    font_scheme = context.theme_element.find(f"{qn('a:themeElements')}/{qn('a:fontScheme')}/{qn(scheme)}")
    if font_scheme is None:
        return Styled(name, "theme")
    resolved = font_scheme.find(qn(slot)).get("typeface", "") if font_scheme.find(qn(slot)) is not None else ""
    if not resolved and script:
        script_font = next((font for font in font_scheme.findall(qn("a:font")) if font.get("script") == script), None)
        resolved = script_font.get("typeface", "") if script_font is not None else ""
    if not resolved:
        resolved = font_scheme.find(qn("a:latin")).get("typeface", name)
    return Styled(resolved, "theme")


def resolve_color(context: SlideContext, color) -> str | None:
    if isinstance(color, str):
        return theme_slot_color(context, color)
    tag = color.tag
    if tag == qn("a:srgbClr"):
        base = color.get("val")
    elif tag == qn("a:schemeClr"):
        base = theme_slot_color(context, color.get("val"))
    elif tag == qn("a:sysClr"):
        base = color.get("lastClr")
    else:
        return None
    return "#" + adjusted_color(base, color).upper() if base else None


def theme_slot_color(context: SlideContext, slot: str) -> str | None:
    mapped = context.color_map().get(slot, slot)
    scheme = context.theme_element.find(f"{qn('a:themeElements')}/{qn('a:clrScheme')}/{qn('a:' + mapped)}")
    if scheme is None or not len(scheme):
        return None
    definition = scheme[0]
    return definition.get("val") if definition.tag == qn("a:srgbClr") else definition.get("lastClr")


def adjusted_color(hex_color: str, color_element) -> str:
    hex_color = hex_color.lstrip("#")
    red, green, blue = (int(hex_color[index:index + 2], 16) / 255 for index in (0, 2, 4))
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    for modifier in color_element:
        amount = int(modifier.get("val", PERCENT_SCALE)) / PERCENT_SCALE
        if modifier.tag == qn("a:lumMod"):
            lightness *= amount
        elif modifier.tag == qn("a:lumOff"):
            lightness += amount
        elif modifier.tag == qn("a:shade"):
            lightness *= amount
        elif modifier.tag == qn("a:tint"):
            lightness += (1 - lightness) * (1 - amount)
    red, green, blue = colorsys.hls_to_rgb(hue, min(max(lightness, 0.0), 1.0), saturation)
    return "".join(f"{round(channel * 255):02X}" for channel in (red, green, blue))
