from __future__ import annotations

from chart_svg import chart_svg
from docx_layout import BreakLayout, Fragment, Line, ParagraphLayout, TableLayout, trimmed
from docx_pagination import NOTE_SEPARATOR_PIXELS, Page, ParagraphSlice, TableSlice
from docx_preview_css import border_value
from docx_preview_model import FieldItem, TableBlock
from office_preview import escaped, page_section, pixels, positioned, style_attribute


FLEX_ALIGNMENT = {"center": "center", "right": "flex-end"}
VERTICAL_JUSTIFY = {"top": "flex-start", "center": "center", "bottom": "flex-end"}


class PageWriter:
    def __init__(self, page_number: int, page_count: int):
        self.page_number = page_number
        self.page_count = page_count

    def page_html(self, page: Page) -> str:
        geometry = page.geometry
        width = geometry.content_width
        parts = [positioned(geometry.margin_left, page.body_top, width, "".join(self.placed_html(item) for item in page.placed))]
        if page.header:
            parts.append(positioned(geometry.margin_left, geometry.header_distance, width, self.layouts_html(page.header)))
        if page.footer:
            footer_height = sum(layout.height for layout in page.footer)
            parts.append(positioned(geometry.margin_left, geometry.height - geometry.footer_distance - footer_height, width, self.layouts_html(page.footer)))
        if page.notes:
            parts.append(self.notes_html(page))
        if page.section.watermark:
            parts.append(watermark_html(page))
        return page_section(self.page_number, geometry, "".join(parts))

    def notes_html(self, page: Page) -> str:
        geometry = page.geometry
        note_layouts = [layout for note in page.notes for layout in note.note_layouts]
        top = page.body_bottom - page.notes_height
        separator = f'<div{style_attribute({"width": "33%", "height": pixels(NOTE_SEPARATOR_PIXELS), "border-top": "1px solid #000000", "box-sizing": "border-box", "margin-top": "6px"})}></div>'
        return positioned(geometry.margin_left, top, geometry.content_width, separator + self.layouts_html(note_layouts))

    def placed_html(self, placed) -> str:
        if isinstance(placed, ParagraphSlice):
            return self.paragraph_html(placed.layout, placed.first_line, placed.last_line, placed.space_before_suppressed)
        if isinstance(placed, TableSlice):
            return self.table_html(placed.layout, placed.rows)
        return ""

    def layouts_html(self, layouts: list) -> str:
        return "".join(self.layout_html(layout) for layout in layouts)

    def layout_html(self, layout) -> str:
        if isinstance(layout, ParagraphLayout):
            return self.paragraph_html(layout, 0, len(layout.lines))
        if isinstance(layout, TableLayout):
            return self.table_html(layout, list(range(len(layout.row_heights))))
        if isinstance(layout, BreakLayout):
            return ""
        return ""

    def paragraph_html(self, layout: ParagraphLayout, first: int, last: int, space_before_suppressed: bool = False) -> str:
        block = layout.block
        declarations = {
            "padding-top": pixels(block.space_before) if first == 0 and block.space_before and not space_before_suppressed else None,
            "padding-bottom": pixels(block.space_after) if last == len(layout.lines) and block.space_after else None,
            "background": block.background,
            **{f"border-{side}": border_value(block.borders.get(side)) for side in ("top", "bottom", "left", "right") if border_value(block.borders.get(side))},
        }
        lines = "".join(self.line_html(block.align, line) for line in layout.lines[first:last])
        return f"<div{style_attribute(declarations)}>{lines}</div>"

    def line_html(self, align: str, line: Line) -> str:
        fragments = trimmed(line.fragments)
        declarations = {
            "height": pixels(line.height),
            "line-height": pixels(line.height),
            "white-space": "pre",
            "margin-left": pixels(line.start) if line.start else None,
            "width": pixels(max(line.available, 0)),
            "text-align": "left" if align == "justify" else align,
            "overflow": "visible",
        }
        if align == "justify" and not line.is_last:
            declarations["word-spacing"] = justify_spacing(fragments, line.available)
        if any(fragment.kind in ("image", "box", "chart") for fragment in fragments):
            declarations.update({"display": "flex", "align-items": "flex-end", "justify-content": FLEX_ALIGNMENT.get(align, "flex-start")})
        return f"<div{style_attribute(declarations)}>{self.fragments_html(fragments)}</div>"

    def fragments_html(self, fragments: list[Fragment]) -> str:
        pieces, text, style = [], "", None
        for fragment in fragments:
            if fragment.kind in ("text", "label", "note", "field") and fragment.style is not None:
                piece = self.field_text(fragment) if fragment.kind == "field" else fragment.text
                if fragment.kind == "label":
                    pieces.append(span(text, style))
                    pieces.append(f'<span{style_attribute({**fragment.style.declarations(), "display": "inline-block", "width": pixels(fragment.width)})}>{escaped(piece)}</span>')
                    text, style = "", None
                    continue
                if style is not None and fragment.style is not style:
                    pieces.append(span(text, style))
                    text = ""
                text, style = text + piece, fragment.style
                continue
            pieces.append(span(text, style))
            text, style = "", None
            pieces.append(self.object_html(fragment))
        pieces.append(span(text, style))
        return "".join(pieces)

    def field_text(self, fragment: Fragment) -> str:
        item = fragment.item
        return str(self.page_number if isinstance(item, FieldItem) and item.kind == "page" else self.page_count)

    def object_html(self, fragment: Fragment) -> str:
        if fragment.kind == "tab":
            return f'<span{style_attribute({"display": "inline-block", "width": pixels(fragment.width)})}></span>'
        if fragment.kind == "image":
            return f'<img src="{fragment.item.source}"{style_attribute({"width": pixels(fragment.width), "height": pixels(fragment.height), "vertical-align": "bottom"})}>'
        if fragment.kind == "chart":
            item = fragment.item
            box = {"display": "inline-block", "width": pixels(fragment.width), "height": pixels(fragment.height), "vertical-align": "bottom"}
            return f"<div{style_attribute(box)}>{chart_svg(item.model, fragment.width, fragment.height, fragment.text, item.palette)}</div>"
        if fragment.kind == "box":
            box = {"display": "inline-block", "width": pixels(fragment.width), "height": pixels(fragment.height), "vertical-align": "bottom", "overflow": "hidden", "white-space": "normal"}
            return f"<div{style_attribute(box)}>{self.layouts_html(fragment.inner)}</div>"
        return ""

    def table_html(self, layout: TableLayout, rows: list[int]) -> str:
        block = layout.block
        positions = {row: index for index, row in enumerate(rows)}
        declarations = {
            "display": "grid",
            "grid-template-columns": " ".join(pixels(width) for width in block.columns),
            "grid-template-rows": " ".join(pixels(layout.row_heights[row]) for row in rows),
            "width": pixels(sum(block.columns)),
            "margin-left": table_offset(block),
        }
        first_shown = rows[0] if rows else 0
        cells = "".join(
            self.cell_html(cell, cell_layouts, positions, first_shown)
            for cell, cell_layouts in zip(block.cells, layout.cell_layouts)
            if cell.row in positions
        )
        return f"<div{style_attribute(declarations)}>{cells}</div>"

    def cell_html(self, cell, layouts: list, positions: dict, first_shown: int) -> str:
        borders = dict(cell.borders)
        if positions[cell.row] == 0 and cell.row != 0 and "top" not in borders:
            borders["top"] = cell.continuation_top
        row_span = sum(1 for row in range(cell.row, cell.row + cell.row_span) if row in positions)
        declarations = {
            "grid-column": f"{cell.column + 1} / span {cell.span}",
            "grid-row": f"{positions[cell.row] + 1} / span {max(row_span, 1)}",
            "box-sizing": "border-box",
            "padding": " ".join(pixels(value) for value in cell.padding),
            "background": cell.background,
            "display": "flex",
            "flex-direction": "column",
            "justify-content": VERTICAL_JUSTIFY.get(cell.vertical_align, "flex-start"),
            "overflow": "hidden",
            **{f"border-{side}": border_value(value) for side, value in borders.items() if border_value(value)},
        }
        return f"<div{style_attribute(declarations)}>{self.layouts_html(layouts)}</div>"


def span(text: str, style) -> str:
    if not text:
        return ""
    return f"<span{style_attribute(style.declarations())}>{escaped(text)}</span>" if style is not None else escaped(text)


def justify_spacing(fragments: list[Fragment], available: float) -> str | None:
    spaces = sum(1 for fragment in fragments if fragment.is_space)
    slack = available - sum(fragment.width for fragment in fragments)
    if spaces == 0 or slack <= 0:
        return None
    return pixels(slack / spaces)


def table_offset(block: TableBlock) -> str | None:
    if block.align == "center":
        return "auto"
    return pixels(block.indent) if block.indent else None


def watermark_html(page: Page) -> str:
    geometry = page.geometry
    declarations = {"text-align": "center", "font-size": "96px", "font-weight": "700", "color": "#d9d9d9", "transform": "rotate(-45deg)", "white-space": "pre"}
    return positioned(0, geometry.height / 2 - 60, geometry.width, escaped(page.section.watermark), declarations)
