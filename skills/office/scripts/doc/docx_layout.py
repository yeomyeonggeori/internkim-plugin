from __future__ import annotations

from dataclasses import dataclass, field

from doc.docx_preview_model import (
    BoxItem, CellBlock, ChartItem, FieldItem, ImageItem, LineBreakItem, NoteReferenceItem, PageBreakBlock, ParagraphBlock, TabItem, TableBlock, TextItem, TextStyle,
)
from core.units import twips_to_pixels
from fonts.preview import FontRegistry, breakable_pieces, is_ideograph_piece


DEFAULT_TAB_PIXELS = 48
SINGLE_LINE_TWIPS = 240
LABEL_GAP_PIXELS = 6
FIELD_SAMPLE = {"page": "9", "pages": "99"}


@dataclass
class Fragment:
    kind: str
    width: float
    height: float
    text: str = ""
    style: TextStyle | None = None
    item: object = None
    is_space: bool = False
    is_ideograph: bool = False
    tab_kind: str = "left"
    inner: list = field(default_factory=list)


@dataclass
class Line:
    fragments: list[Fragment]
    start: float
    available: float
    height: float
    is_last: bool = False

    @property
    def width(self) -> float:
        return sum(fragment.width for fragment in trimmed(self.fragments))

    @property
    def notes(self) -> list[NoteReferenceItem]:
        return [fragment.item for fragment in self.fragments if isinstance(fragment.item, NoteReferenceItem)]


@dataclass
class ParagraphLayout:
    block: ParagraphBlock
    lines: list[Line]
    width: float

    @property
    def height(self) -> float:
        return self.block.space_before + sum(line.height for line in self.lines) + self.block.space_after


@dataclass
class TableLayout:
    block: TableBlock
    row_heights: list[float]
    cell_layouts: list[list]

    @property
    def height(self) -> float:
        return sum(self.row_heights)


@dataclass
class BreakLayout:
    height: float = 0


def trimmed(fragments: list[Fragment]) -> list[Fragment]:
    end = len(fragments)
    while end and fragments[end - 1].is_space:
        end -= 1
    return fragments[:end]


class Layout:
    def __init__(self, fonts: FontRegistry):
        self.fonts = fonts

    def blocks(self, blocks: list, width: float) -> list:
        return [self.block(block, width) for block in blocks]

    def block(self, block, width: float):
        if isinstance(block, ParagraphBlock):
            return self.paragraph(block, width)
        if isinstance(block, TableBlock):
            return self.table(block, width)
        if isinstance(block, PageBreakBlock):
            return BreakLayout()
        return BreakLayout()

    def paragraph(self, block: ParagraphBlock, width: float) -> ParagraphLayout:
        fragments = self.fragments(block.items, width - block.indent_left - block.indent_right)
        lines = self.break_lines(block, fragments, width)
        for line in lines:
            line.height = self.line_height(block, line)
        lines[-1].is_last = True
        return ParagraphLayout(block, lines, width)

    def fragments(self, items: list, available: float) -> list[Fragment]:
        fragments = []
        for item in items:
            fragments.extend(self.item_fragments(item, available))
        return fragments

    def item_fragments(self, item, available: float) -> list[Fragment]:
        if isinstance(item, TextItem):
            return [self.text_fragment(piece, item.style) for piece in breakable_pieces(item.text)]
        if isinstance(item, TabItem):
            return [Fragment("tab", 0, 0, style=item.style)]
        if isinstance(item, LineBreakItem):
            return [Fragment("break", 0, self.fonts.line_height(item.style.font), style=item.style)]
        if isinstance(item, ImageItem):
            scale = min(1.0, available / item.width) if item.width > available > 0 else 1.0
            return [Fragment("image", item.width * scale, item.height * scale, item=item)]
        if isinstance(item, ChartItem):
            scale = min(1.0, available / item.width) if item.width > available > 0 else 1.0
            return [Fragment("chart", item.width * scale, item.height * scale, item=item, text=self.fonts.korean_family())]
        if isinstance(item, BoxItem):
            inner = self.blocks(item.blocks, item.width)
            height = max(item.height, sum(layout.height for layout in inner))
            return [Fragment("box", min(item.width, available), height, item=item, inner=inner)]
        if isinstance(item, FieldItem):
            return [Fragment("field", self.fonts.width(item.style.font, FIELD_SAMPLE[item.kind]), self.fonts.line_height(item.style.font, "9"), style=item.style, item=item)]
        if isinstance(item, NoteReferenceItem):
            text = str(item.number)
            return [Fragment("note", self.fonts.width(item.style.font, text), self.fonts.line_height(item.style.font, text), text=text, style=item.style, item=item)]
        return []

    def text_fragment(self, piece: str, style: TextStyle) -> Fragment:
        return Fragment(
            "text",
            self.fonts.width(style.font, piece),
            self.fonts.line_height(style.font, piece),
            text=piece,
            style=style,
            is_space=piece.isspace(),
            is_ideograph=is_ideograph_piece(piece),
        )

    def label_fragment(self, block: ParagraphBlock) -> list[Fragment]:
        if not block.label or block.label_style is None:
            return []
        width = self.fonts.width(block.label_style.font, block.label)
        slot = block.hanging if width < block.hanging else width + LABEL_GAP_PIXELS
        return [Fragment("label", slot, self.fonts.line_height(block.label_style.font, block.label), text=block.label, style=block.label_style)]

    def break_lines(self, block: ParagraphBlock, fragments: list[Fragment], width: float) -> list[Line]:
        label = self.label_fragment(block)
        first_start = block.indent_left - block.hanging if block.hanging else block.indent_left + block.first_line
        other_start = block.indent_left
        right_limit = width - block.indent_right
        lines: list[Line] = []
        current = list(label)
        start = first_start
        for index, fragment in enumerate(fragments):
            if fragment.kind == "break":
                lines.append(Line(current, start, right_limit - start, 0))
                current, start = [], other_start
                continue
            if fragment.kind == "tab":
                fragment.width = self.tab_width(block, start + sum(item.width for item in current), fragments[index + 1:], right_limit)
            current.append(fragment)
            if fragment.is_space or sum(item.width for item in trimmed(current)) <= right_limit - start:
                continue
            cut = last_break(current)
            if cut:
                lines.append(Line(current[:cut], start, right_limit - start, 0))
                current, start = current[cut:], other_start
        lines.append(Line(current, start, right_limit - start, 0))
        return lines

    def tab_width(self, block: ParagraphBlock, position: float, following: list[Fragment], right_limit: float) -> float:
        stop, kind = next(((stop, kind) for stop, kind in block.tab_stops if stop > position + 0.5), (None, "left"))
        if stop is None:
            stop = (int(position // DEFAULT_TAB_PIXELS) + 1) * DEFAULT_TAB_PIXELS
            kind = "left"
        if kind in ("right", "center", "decimal"):
            segment = 0.0
            for fragment in following:
                if fragment.kind in ("tab", "break"):
                    break
                segment += fragment.width
            shift = segment if kind in ("right", "decimal") else segment / 2
            return max(0.0, min(stop, right_limit) - position - shift)
        return max(0.0, stop - position)

    def line_height(self, block: ParagraphBlock, line: Line) -> float:
        natural = max((fragment.height for fragment in line.fragments if fragment.height), default=0) or self.fonts.line_height(block.base_style.font)
        if not block.line:
            return natural
        if block.line_rule == "auto":
            return natural * block.line / SINGLE_LINE_TWIPS
        exact = twips_to_pixels(block.line)
        return exact if block.line_rule == "exact" else max(exact, natural)

    def table(self, block: TableBlock, available: float) -> TableLayout:
        cell_layouts = [self.blocks(cell.blocks, cell_content_width(block, cell)) for cell in block.cells]
        heights = [row.height for row in block.rows]
        for cell, layouts in zip(block.cells, cell_layouts):
            if cell.row_span == 1 and not block.rows[cell.row].exact:
                heights[cell.row] = max(heights[cell.row], cell_height(cell, layouts))
        for cell, layouts in zip(block.cells, cell_layouts):
            if cell.row_span > 1:
                spanned = range(cell.row, min(cell.row + cell.row_span, len(heights)))
                shortfall = cell_height(cell, layouts) - sum(heights[row] for row in spanned)
                if shortfall > 0:
                    heights[spanned[-1]] += shortfall
        return TableLayout(block, heights, cell_layouts)


def cell_content_width(table: TableBlock, cell: CellBlock) -> float:
    return max(1.0, sum(table.columns[cell.column:cell.column + cell.span]) - cell.padding[1] - cell.padding[3])


def cell_height(cell: CellBlock, layouts: list) -> float:
    return sum(layout.height for layout in layouts) + cell.padding[0] + cell.padding[2]


def last_break(fragments: list[Fragment]) -> int:
    for index in range(len(fragments) - 1, 0, -1):
        previous, fragment = fragments[index - 1], fragments[index]
        if not fragment.is_space and (previous.is_space or previous.is_ideograph or fragment.is_ideograph or previous.kind in ("image", "box", "chart", "tab")):
            return index
    return 0
