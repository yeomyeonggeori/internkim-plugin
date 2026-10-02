from __future__ import annotations

from docx.oxml.ns import qn


THEME_NAMESPACE = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
FALSE_VALUES = ("0", "false", "off", "none")
NO_COLOR = ("auto", None, "")


def on(element, tag: str) -> bool | None:
    child = element.find(qn(tag)) if element is not None else None
    if child is None:
        return None
    return child.get(qn("w:val"), "true").lower() not in FALSE_VALUES


def attribute(element, tag: str, name: str) -> str | None:
    child = element.find(qn(tag)) if element is not None else None
    return child.get(qn(name)) if child is not None else None


def number(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def defined(properties: dict) -> dict:
    return {name: value for name, value in properties.items() if value is not None}


def run_properties(element) -> dict:
    if element is None:
        return {}
    size = number(attribute(element, "w:sz", "w:val"))
    color = attribute(element, "w:color", "w:val")
    underline = attribute(element, "w:u", "w:val")
    shading = attribute(element, "w:shd", "w:fill")
    fonts = element.find(qn("w:rFonts"))
    return defined({
        "bold": on(element, "w:b"),
        "italic": on(element, "w:i"),
        "strike": on(element, "w:strike") or on(element, "w:dstrike"),
        "caps": on(element, "w:caps"),
        "small_caps": on(element, "w:smallCaps"),
        "hidden": on(element, "w:vanish"),
        "underline": None if underline is None else underline.lower() not in FALSE_VALUES,
        "size": size / 2 if size else None,
        "color": None if color in NO_COLOR else color,
        "highlight": attribute(element, "w:highlight", "w:val"),
        "shading": None if shading in NO_COLOR else shading,
        "vertical": attribute(element, "w:vertAlign", "w:val"),
        "letter_spacing": number(attribute(element, "w:spacing", "w:val")),
        "style": attribute(element, "w:rStyle", "w:val"),
        **font_properties(fonts),
    })


def font_properties(fonts) -> dict:
    if fonts is None:
        return {}
    return defined({
        "font_latin": fonts.get(qn("w:ascii")) or fonts.get(qn("w:hAnsi")),
        "font_latin_theme": fonts.get(qn("w:asciiTheme")) or fonts.get(qn("w:hAnsiTheme")),
        "font_east_asia": fonts.get(qn("w:eastAsia")),
        "font_east_asia_theme": fonts.get(qn("w:eastAsiaTheme")),
    })


def paragraph_properties(element) -> dict:
    if element is None:
        return {}
    indent = element.find(qn("w:ind"))
    spacing = element.find(qn("w:spacing"))
    numbering = element.find(qn("w:numPr"))
    shading = attribute(element, "w:shd", "w:fill")
    return defined({
        "align": attribute(element, "w:jc", "w:val"),
        "style": attribute(element, "w:pStyle", "w:val"),
        "page_break_before": on(element, "w:pageBreakBefore"),
        "keep_next": on(element, "w:keepNext"),
        "contextual_spacing": on(element, "w:contextualSpacing"),
        "outline_level": number(attribute(element, "w:outlineLvl", "w:val")),
        "tab_stops": tab_stops(element.find(qn("w:tabs"))),
        "shading": None if shading in NO_COLOR else shading,
        "borders": border_set(element.find(qn("w:pBdr"))),
        **indent_properties(indent),
        **spacing_properties(spacing),
        **numbering_properties(numbering),
    })


def tab_stops(tabs) -> tuple | None:
    if tabs is None:
        return None
    stops = [(number(tab.get(qn("w:pos"))) or 0, tab.get(qn("w:val"), "left")) for tab in tabs.findall(qn("w:tab"))]
    return tuple(sorted(stop for stop in stops if stop[1] != "clear"))


def indent_properties(indent) -> dict:
    if indent is None:
        return {}
    return defined({
        "indent_left": number(indent.get(qn("w:left")) or indent.get(qn("w:start"))),
        "indent_right": number(indent.get(qn("w:right")) or indent.get(qn("w:end"))),
        "first_line": number(indent.get(qn("w:firstLine"))),
        "hanging": number(indent.get(qn("w:hanging"))),
    })


def spacing_properties(spacing) -> dict:
    if spacing is None:
        return {}
    return defined({
        "space_before": number(spacing.get(qn("w:before"))),
        "space_after": number(spacing.get(qn("w:after"))),
        "line": number(spacing.get(qn("w:line"))),
        "line_rule": spacing.get(qn("w:lineRule")),
    })


def numbering_properties(numbering) -> dict:
    if numbering is None:
        return {}
    return defined({
        "num_id": attribute(numbering, "w:numId", "w:val"),
        "level": int(attribute(numbering, "w:ilvl", "w:val") or 0),
    })


def border_set(element) -> dict | None:
    if element is None:
        return None
    borders = {child.tag.split("}")[1]: border(child) for child in element}
    return borders or None


def border(element) -> dict:
    return {
        "style": element.get(qn("w:val"), "single"),
        "size": number(element.get(qn("w:sz"))) or 4,
        "color": element.get(qn("w:color")),
    }


def merged(*layers: dict) -> dict:
    result: dict = {}
    for layer in layers:
        for name, value in layer.items():
            if name == "borders" and isinstance(result.get(name), dict):
                result[name] = {**result[name], **value}
            else:
                result[name] = value
    return result


class StyleSheet:
    def __init__(self, styles_root, theme_root):
        self.styles = {style.get(qn("w:styleId")): style for style in styles_root.iter(qn("w:style"))} if styles_root is not None else {}
        defaults = styles_root.find(qn("w:docDefaults")) if styles_root is not None else None
        self.default_run = run_properties(defaults.find(f"{qn('w:rPrDefault')}/{qn('w:rPr')}")) if defaults is not None else {}
        self.default_paragraph = paragraph_properties(defaults.find(f"{qn('w:pPrDefault')}/{qn('w:pPr')}")) if defaults is not None else {}
        self.default_paragraph_style = self.default_style_id("paragraph")
        self.default_table_style = self.default_style_id("table")
        self.theme_fonts = theme_fonts(theme_root)

    def default_style_id(self, kind: str) -> str | None:
        return next((identifier for identifier, style in self.styles.items() if style.get(qn("w:type")) == kind and on_value(style.get(qn("w:default")))), None)

    def chain(self, style_id: str | None) -> list:
        chain, seen = [], set()
        while style_id and style_id in self.styles and style_id not in seen:
            seen.add(style_id)
            style = self.styles[style_id]
            chain.insert(0, style)
            style_id = attribute(style, "w:basedOn", "w:val")
        return chain

    def paragraph_layers(self, style_id: str | None) -> tuple[dict, dict]:
        chain = self.chain(style_id or self.default_paragraph_style)
        paragraph = merged(*(paragraph_properties(style.find(qn("w:pPr"))) for style in chain))
        run = merged(*(run_properties(style.find(qn("w:rPr"))) for style in chain))
        return paragraph, run

    def character_layer(self, style_id: str | None) -> dict:
        return merged(*(run_properties(style.find(qn("w:rPr"))) for style in self.chain(style_id)))

    def table_layers(self, style_id: str | None) -> list:
        return self.chain(style_id or self.default_table_style)

    def resolved_font(self, properties: dict) -> tuple[str | None, str | None]:
        latin = properties.get("font_latin") or self.theme_fonts.get(properties.get("font_latin_theme"))
        east_asia = properties.get("font_east_asia") or self.theme_fonts.get(properties.get("font_east_asia_theme"))
        return latin, east_asia


def on_value(value: str | None) -> bool:
    return value is not None and value.lower() not in FALSE_VALUES


def theme_fonts(theme_root) -> dict:
    if theme_root is None:
        return {}
    fonts = {}
    for scheme, prefix in (("majorFont", "major"), ("minorFont", "minor")):
        element = theme_root.find(f".//{THEME_NAMESPACE}{scheme}")
        if element is None:
            continue
        latin = element.find(f"{THEME_NAMESPACE}latin")
        east_asia = element.find(f"{THEME_NAMESPACE}ea")
        hangul = next((font.get("typeface") for font in element.iter(f"{THEME_NAMESPACE}font") if font.get("script") == "Hang"), None)
        latin_face = latin.get("typeface") if latin is not None else None
        fonts[f"{prefix}HAnsi"] = fonts[f"{prefix}Ascii"] = latin_face
        fonts[f"{prefix}EastAsia"] = (east_asia.get("typeface") if east_asia is not None else None) or hangul
        fonts[f"{prefix}Bidi"] = latin_face
    return fonts
