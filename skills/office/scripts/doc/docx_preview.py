from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from chart_svg import DEFAULT_PALETTE
from docx.oxml.ns import qn
from lxml import etree

from docx_package import open_document
from docx_preview_css import DEFAULT_FONT_SIZE_POINTS, HIGHLIGHT_COLORS, hex_color, text_decoration
from docx_preview_graphics import GRAPHIC_TAGS, graphic_items
from docx_preview_math import MATH_TAGS, linear_math
from docx_preview_model import (
    FieldItem, LineBreakItem, NoteReferenceItem, PageBreakBlock, PageBreakItem, ParagraphBlock, SectionModel, TabItem, TextItem, TextStyle,
)
from docx_preview_numbering import Numbering, readable_symbol
from docx_preview_sections import document_sections, page_number_start, section_geometry
from docx_preview_styles import StyleSheet, merged, paragraph_properties, run_properties
from docx_preview_tables import TableLayers, table_block
from office_preview import Preview, points_to_pixels, twips_to_pixels
from preview_fonts import DEFAULT_FAMILY, FontRequest, css_font_family


ACCENT_SLOTS = ("accent1", "accent2", "accent3", "accent4", "accent5", "accent6")
DRAWING_MAIN = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
THEME_RELATIONSHIP = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
MARKUP_COLORS = {"inserted": "#1d4ed8", "deleted": "#b42318"}
COMMENT_BACKGROUND = "#fff1b8"
SCRIPT_SIZE_RATIO = 0.65
ALIGNMENTS = {"left": "left", "start": "left", "center": "center", "right": "right", "end": "right", "both": "justify", "distribute": "justify"}
TRANSPARENT_CONTAINERS = frozenset(qn(tag) for tag in ("w:hyperlink", "w:smartTag", "w:customXml", "w:sdtContent", "w:fldSimple", "w:dir", "w:bdo"))
REVISION_CONTAINERS = {qn("w:ins"): "inserted", qn("w:moveTo"): "inserted", qn("w:del"): "deleted", qn("w:moveFrom"): "deleted"}
FIELD_KINDS = {"PAGE": "page", "NUMPAGES": "pages", "SECTIONPAGES": "pages"}


@dataclass
class Field:
    instruction: str = ""
    in_result: bool = False
    emitted: bool = False

    def kind(self) -> str | None:
        words = self.instruction.split()
        return FIELD_KINDS.get(words[0].upper()) if words else None


@dataclass
class InlineState:
    fields: list[Field] = field(default_factory=list)
    open_comments: set = field(default_factory=set)
    revision: str | None = None

    def hides_text(self) -> bool:
        return any(not item.in_result or item.kind() for item in self.fields)


class DocxModelBuilder:
    def __init__(self, path: Path):
        self.document = open_document(str(path))
        theme = self.theme_root()
        self.styles = StyleSheet(self.document.styles.element, theme)
        self.chart_palette = theme_accents(theme)
        self.numbering = Numbering(self.numbering_root())
        self.preview = Preview(title=path.stem)
        self.footnotes = self.notes("footnotes", "w:footnote")
        self.footnote_count = 0
        self.current_footnote = 0
        self.watermark = ""
        self.watermark_image = None

    def related_part(self, suffix: str):
        return next((relationship.target_part for relationship in self.document.part.rels.values() if relationship.reltype.endswith(suffix)), None)

    def theme_root(self):
        part = self.related_part("/theme")
        return etree.fromstring(part.blob) if part is not None else None

    def numbering_root(self):
        part = self.related_part("/numbering")
        return etree.fromstring(part.blob) if part is not None else None

    def notes(self, kind: str, tag: str) -> dict:
        part = self.related_part(f"/{kind}")
        if part is None:
            return {}
        return {note.get(qn("w:id")): (note, part) for note in etree.fromstring(part.blob).iter(qn(tag))}

    def sections(self) -> list[SectionModel]:
        models, header, footer = [], [], []
        for section in document_sections(self.document.element.body):
            header = self.header_footer(section.properties, "w:headerReference", header)
            footer = self.header_footer(section.properties, "w:footerReference", footer)
            geometry = section_geometry(section.properties, self.preview)
            blocks = self.blocks(section.elements, self.document.part, TableLayers())
            models.append(SectionModel(
                geometry, blocks, header, footer,
                starts_new_page=not section.continues_page,
                watermark=self.watermark,
                watermark_image=self.watermark_image,
                page_number_start=page_number_start(section.properties),
            ))
        self.count_comments()
        return models

    def header_footer(self, properties, tag: str, inherited: list) -> list:
        if properties is None:
            return inherited
        references = {reference.get(qn("w:type")): reference.get(qn("r:id")) for reference in properties.findall(qn(tag))}
        if "first" in references and properties.find(qn("w:titlePg")) is not None:
            self.preview.approximate("first-page headers or footers shown as the default one")
        relationship_id = references.get("default")
        if relationship_id is None:
            return inherited
        part = self.document.part.related_parts[relationship_id]
        return self.blocks(list(etree.fromstring(part.blob)), part, TableLayers())

    def blocks(self, elements: list, part, layers: TableLayers) -> list:
        blocks = []
        for element in elements:
            blocks.extend(self.element_blocks(element, part, layers))
        return blocks

    def element_blocks(self, element, part, layers: TableLayers) -> list:
        if element.tag == qn("w:p"):
            return self.paragraph_blocks(element, part, layers)
        if element.tag == qn("w:tbl"):
            return [table_block(element, part, self, layers)]
        if element.tag in (qn("w:sdt"), qn("w:customXml")):
            content = element.find(qn("w:sdtContent"))
            return self.blocks(list(content if content is not None else element), part, layers)
        return []

    def paragraph_blocks(self, paragraph, part, layers: TableLayers) -> list:
        direct = paragraph_properties(paragraph.find(qn("w:pPr")))
        style_paragraph, style_run = self.styles.paragraph_layers(direct.get("style"))
        base_run = merged(self.styles.default_run, layers.run, style_run)
        properties = merged(self.styles.default_paragraph, layers.paragraph, style_paragraph, direct)
        label = self.numbering.label(properties.get("num_id"), properties.get("level", 0))
        if label is not None:
            properties = merged(self.styles.default_paragraph, layers.paragraph, style_paragraph, label.paragraph, direct)
        items = self.inline_items(list(paragraph), part, InlineState(), base_run)
        pieces = split_at_page_breaks(items)
        blocks = []
        for index, piece in enumerate(pieces):
            if index:
                blocks.append(PageBreakBlock())
            blocks.append(self.paragraph_block(piece, properties, base_run, label if index == 0 else None, paragraph, index == 0))
        return blocks

    def paragraph_block(self, items: list, properties: dict, base_run: dict, label, paragraph, is_first: bool) -> ParagraphBlock:
        hanging = properties.get("hanging") or 0
        return ParagraphBlock(
            items=items,
            base_style=self.text_style(base_run),
            align=ALIGNMENTS.get(properties.get("align") or "left", "left"),
            indent_left=twips_to_pixels(properties.get("indent_left") or 0),
            indent_right=twips_to_pixels(properties.get("indent_right") or 0),
            first_line=twips_to_pixels(properties.get("first_line") or 0) if is_first else 0,
            hanging=twips_to_pixels(hanging) if is_first else 0,
            space_before=twips_to_pixels(properties.get("space_before") or 0) if is_first else 0,
            space_after=twips_to_pixels(properties.get("space_after") or 0),
            line=properties.get("line"),
            line_rule=properties.get("line_rule") or "auto",
            keep_next=bool(properties.get("keep_next")),
            page_break_before=bool(properties.get("page_break_before")) and is_first,
            label=label.text if label is not None else "",
            label_style=self.text_style(merged(base_run, label.run)) if label is not None else None,
            background=hex_color(properties.get("shading")),
            borders=properties.get("borders") or {},
            tab_stops=tuple((twips_to_pixels(position), kind) for position, kind in properties.get("tab_stops") or ()),
        )

    def text_style(self, properties: dict, revision: str | None = None, commented: bool = False) -> TextStyle:
        latin, east_asia = self.styles.resolved_font(properties)
        latin, east_asia = latin or east_asia or DEFAULT_FAMILY, east_asia or latin or DEFAULT_FAMILY
        size = properties.get("size") or DEFAULT_FONT_SIZE_POINTS
        vertical = properties.get("vertical")
        measured_size = size * SCRIPT_SIZE_RATIO if vertical in ("superscript", "subscript") else size
        bold = bool(properties.get("bold"))
        declarations = {
            "font-family": css_font_family(latin, east_asia),
            "font-size": f"{round(points_to_pixels(measured_size), 2)}px",
            "font-weight": "700" if bold else None,
            "font-style": "italic" if properties.get("italic") else None,
            "text-decoration": text_decoration(properties),
            "color": hex_color(properties.get("color")),
            "background": HIGHLIGHT_COLORS.get(properties.get("highlight") or "") or hex_color(properties.get("shading")),
            "text-transform": "uppercase" if properties.get("caps") else None,
            "position": "relative" if vertical in ("superscript", "subscript") else None,
            "top": "-0.45em" if vertical == "superscript" else "0.2em" if vertical == "subscript" else None,
        }
        if revision:
            declarations.update({"color": MARKUP_COLORS[revision], "text-decoration": "underline" if revision == "inserted" else "line-through"})
        if commented:
            declarations["background"] = COMMENT_BACKGROUND
        css = tuple((name, value) for name, value in declarations.items() if value)
        return TextStyle(FontRequest(latin, east_asia, measured_size, bold), css)

    def inline_items(self, elements: list, part, state: InlineState, base_run: dict) -> list:
        items = []
        for element in elements:
            items.extend(self.inline_element_items(element, part, state, base_run))
        return items

    def inline_element_items(self, element, part, state: InlineState, base_run: dict) -> list:
        if element.tag == qn("w:r"):
            return self.run_items(element, part, state, base_run)
        if element.tag in REVISION_CONTAINERS:
            previous, state.revision = state.revision, REVISION_CONTAINERS[element.tag]
            items = self.inline_items(list(element), part, state, base_run)
            state.revision = previous
            return items
        if element.tag == qn("w:fldSimple") and Field(element.get(qn("w:instr")) or "").kind():
            return [FieldItem(Field(element.get(qn("w:instr"))).kind(), self.text_style(base_run))]
        if element.tag in MATH_TAGS:
            self.preview.approximate("equations drawn as linear text")
            return [TextItem(linear_math(element), self.text_style(base_run))]
        if element.tag == qn("w:sdt"):
            content = element.find(qn("w:sdtContent"))
            return self.inline_items(list(content) if content is not None else [], part, state, base_run)
        if element.tag in TRANSPARENT_CONTAINERS:
            return self.inline_items(list(element), part, state, base_run)
        if element.tag == qn("w:commentRangeStart"):
            state.open_comments.add(element.get(qn("w:id")))
        if element.tag == qn("w:commentRangeEnd"):
            state.open_comments.discard(element.get(qn("w:id")))
        return []

    def run_items(self, run, part, state: InlineState, base_run: dict) -> list:
        direct = run_properties(run.find(qn("w:rPr")))
        properties = merged(base_run, self.styles.character_layer(direct.get("style")), direct)
        if properties.get("hidden"):
            return []
        style = self.text_style(properties, state.revision, bool(state.open_comments))
        items = []
        for child in run:
            items.extend(self.run_child_items(child, part, state, style))
        return items

    def run_child_items(self, child, part, state: InlineState, style: TextStyle) -> list:
        if child.tag == qn("w:fldChar"):
            return self.field_character(child, state, style)
        if child.tag == qn("w:instrText"):
            if state.fields:
                state.fields[-1].instruction += child.text or ""
            return []
        if state.hides_text():
            return []
        return self.visible_child_items(child, part, style)

    def field_character(self, child, state: InlineState, style: TextStyle) -> list:
        kind = child.get(qn("w:fldCharType"))
        if kind == "begin":
            state.fields.append(Field())
            return []
        if not state.fields:
            return []
        current = state.fields[-1]
        if kind == "separate":
            current.in_result = True
        if kind == "end":
            state.fields.pop()
        if current.kind() and not current.emitted and kind in ("separate", "end"):
            current.emitted = True
            return [FieldItem(current.kind(), style)]
        return []

    def visible_child_items(self, child, part, style: TextStyle) -> list:
        tag = child.tag
        if tag in (qn("w:t"), qn("w:delText")):
            return [TextItem(child.text or "", style)]
        if tag == qn("w:tab"):
            return [TabItem(style)]
        if tag == qn("w:br"):
            return [PageBreakItem()] if child.get(qn("w:type")) == "page" else [LineBreakItem(style)]
        if tag == qn("w:cr"):
            return [LineBreakItem(style)]
        if tag == qn("w:noBreakHyphen"):
            return [TextItem("‑", style)]
        if tag == qn("w:sym"):
            return [TextItem(readable_symbol(chr(int(child.get(qn("w:char"), "0"), 16))), style)]
        if tag == qn("w:footnoteReference"):
            return [self.note_reference(child, style)]
        if tag == qn("w:footnoteRef"):
            return [TextItem(str(self.current_footnote), self.superscript(style))]
        if tag == qn("w:endnoteReference"):
            self.preview.approximate("endnotes")
        if tag in GRAPHIC_TAGS:
            return graphic_items(child, part, self)
        if tag == qn("w:object"):
            self.preview.approximate("embedded objects")
        return []

    def superscript(self, style: TextStyle) -> TextStyle:
        font = style.font
        css = dict(style.css)
        css.update({"font-size": f"{round(points_to_pixels(font.size * SCRIPT_SIZE_RATIO), 2)}px", "position": "relative", "top": "-0.45em"})
        return TextStyle(FontRequest(font.latin, font.east_asia, font.size * SCRIPT_SIZE_RATIO, font.bold), tuple(css.items()))

    def note_reference(self, child, style: TextStyle) -> NoteReferenceItem:
        self.footnote_count += 1
        number = self.footnote_count
        note, part = self.footnotes.get(child.get(qn("w:id")), (None, None))
        self.current_footnote = number
        blocks = self.blocks(list(note), part, TableLayers()) if note is not None else []
        return NoteReferenceItem(number, blocks, self.superscript(style))

    def count_comments(self) -> None:
        part = self.related_part("/comments")
        if part is None:
            return
        count = len(etree.fromstring(part.blob).findall(qn("w:comment")))
        if count:
            self.preview.approximate("comments shown only as highlighted anchor text", count)


def split_at_page_breaks(items: list) -> list[list]:
    pieces = [[]]
    for item in items:
        if isinstance(item, PageBreakItem):
            pieces.append([])
        else:
            pieces[-1].append(item)
    return pieces


def theme_accents(theme_root) -> tuple[str, ...]:
    if theme_root is None:
        return DEFAULT_PALETTE
    colors = []
    for slot in ACCENT_SLOTS:
        element = theme_root.find(f".//{DRAWING_MAIN}{slot}")
        color = next((child.get("val") or child.get("lastClr") for child in element), None) if element is not None else None
        colors.append(f"#{color.lower()}" if color else None)
    return tuple(color for color in colors if color) or DEFAULT_PALETTE
