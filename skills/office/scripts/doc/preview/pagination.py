from __future__ import annotations

from dataclasses import dataclass, field

from doc.preview.layout import BreakLayout, Layout, ParagraphLayout, TableLayout
from doc.preview.model import NoteReferenceItem, SectionModel
from render.office_preview import PageGeometry


NOTE_SEPARATOR_PIXELS = 14
VISIBLE_FRAGMENT_KINDS = frozenset({"image", "chart", "box", "field"})


@dataclass
class ParagraphSlice:
    layout: ParagraphLayout
    first_line: int
    last_line: int
    space_before_suppressed: bool = False

    @property
    def with_space_before(self) -> bool:
        return self.first_line == 0 and not self.space_before_suppressed

    @property
    def with_space_after(self) -> bool:
        return self.last_line == len(self.layout.lines)

    @property
    def height(self) -> float:
        lines = self.layout.lines[self.first_line:self.last_line]
        block = self.layout.block
        return sum(line.height for line in lines) + (block.space_before if self.with_space_before else 0) + (block.space_after if self.with_space_after else 0)


@dataclass
class TableSlice:
    layout: TableLayout
    rows: list[int]

    @property
    def height(self) -> float:
        return sum(self.layout.row_heights[row] for row in self.rows)


@dataclass
class Page:
    section: SectionModel
    header: list
    footer: list
    body_top: float
    body_bottom: float
    placed: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    used: float = 0
    notes_height: float = 0
    follows_overflow: bool = False

    @property
    def geometry(self) -> PageGeometry:
        return self.section.geometry

    @property
    def remaining(self) -> float:
        return self.body_bottom - self.body_top - self.used - self.notes_height

    @property
    def is_empty(self) -> bool:
        return not self.placed

    @property
    def is_blank(self) -> bool:
        return not any(shows_something(placed) for placed in self.placed)


def shows_something(placed) -> bool:
    if isinstance(placed, TableSlice):
        return bool(placed.rows)
    if not isinstance(placed, ParagraphSlice):
        return False
    lines = placed.layout.lines[placed.first_line:placed.last_line]
    return any(fragment.kind in VISIBLE_FRAGMENT_KINDS or fragment.text.strip() for line in lines for fragment in line.fragments)


def stranded_headings(pages: list[Page]) -> list[tuple[int, ParagraphLayout]]:
    return [
        (number, page.placed[-1].layout)
        for number, (page, next_page) in enumerate(zip(pages, pages[1:]), start=1)
        if page.placed and next_page.placed and ends_on_heading(page.placed[-1])
    ]


def ends_on_heading(placed) -> bool:
    return isinstance(placed, ParagraphSlice) and placed.layout.block.is_heading and not placed.layout.block.keep_next and placed.with_space_after


def displayed_page_numbers(pages: list[Page]) -> list[int]:
    numbers: list[int] = []
    for index, page in enumerate(pages):
        starts_section = index == 0 or pages[index - 1].section is not page.section
        restarts = starts_section and page.section.page_number_start is not None
        numbers.append(page.section.page_number_start if restarts else (numbers[-1] + 1 if numbers else 1))
    return numbers


class Paginator:
    def __init__(self, layout: Layout):
        self.layout = layout
        self.pages: list[Page] = []
        self.section_frames: dict[int, tuple] = {}

    def paginate(self, sections: list[SectionModel]) -> list[Page]:
        for section in sections:
            if section.starts_new_page or not self.pages:
                self.new_page(section)
            layouts = self.layout.blocks(section.blocks, section.geometry.content_width)
            for index, block_layout in enumerate(layouts):
                following = layouts[index + 1] if index + 1 < len(layouts) else None
                self.place(block_layout, following, section)
        return self.pages

    def frame(self, section: SectionModel) -> tuple:
        key = id(section)
        if key not in self.section_frames:
            geometry = section.geometry
            header = self.layout.blocks(section.header, geometry.content_width)
            footer = self.layout.blocks(section.footer, geometry.content_width)
            header_bottom = geometry.header_distance + sum(item.height for item in header)
            footer_top = geometry.height - geometry.footer_distance - sum(item.height for item in footer)
            body_top = max(geometry.margin_top, header_bottom)
            body_bottom = min(geometry.height - geometry.margin_bottom, footer_top)
            self.section_frames[key] = (header, footer, body_top, body_bottom)
        return self.section_frames[key]

    def new_page(self, section: SectionModel, follows_overflow: bool = False) -> Page:
        header, footer, body_top, body_bottom = self.frame(section)
        page = Page(section, header, footer, body_top, body_bottom, follows_overflow=follows_overflow)
        self.pages.append(page)
        return page

    @property
    def page(self) -> Page:
        return self.pages[-1]

    def place(self, block_layout, following, section: SectionModel) -> None:
        if isinstance(block_layout, BreakLayout):
            self.new_page(section)
            return
        if isinstance(block_layout, ParagraphLayout):
            self.place_paragraph(block_layout, following, section)
            return
        self.place_table(block_layout, section)

    def place_paragraph(self, layout: ParagraphLayout, following, section: SectionModel) -> None:
        if layout.block.page_break_before and not self.page.is_empty:
            self.new_page(section)
        if layout.block.keep_next and not self.page.is_empty and self.fits_whole(layout) and not self.next_start_fits(layout, following):
            self.new_page(section, follows_overflow=True)
        first = 0
        while first < len(layout.lines):
            suppressed = first == 0 and self.page.is_empty and self.page.follows_overflow
            count = self.lines_that_fit(layout, first, suppressed)
            if count == 0 and not self.page.is_empty:
                self.new_page(section, follows_overflow=True)
                continue
            count = max(count, 1)
            self.put(ParagraphSlice(layout, first, first + count, suppressed))
            first += count
            if first < len(layout.lines):
                self.new_page(section, follows_overflow=True)

    def fits_whole(self, layout: ParagraphLayout) -> bool:
        return layout.height - layout.block.space_after + self.notes_cost(layout.lines) <= self.page.remaining

    def next_start_fits(self, layout: ParagraphLayout, following) -> bool:
        if isinstance(following, ParagraphLayout):
            needed = following.block.space_before + sum(line.height for line in following.lines[:2])
        elif isinstance(following, TableLayout) and following.row_heights:
            needed = following.row_heights[0]
        else:
            return True
        return layout.height + needed <= self.page.remaining

    def lines_that_fit(self, layout: ParagraphLayout, first: int, space_before_suppressed: bool) -> int:
        block = layout.block
        lines = layout.lines
        available = self.page.remaining - (block.space_before if first == 0 and not space_before_suppressed else 0)
        count, used, notes = 0, 0.0, []
        for line in lines[first:]:
            notes = notes + line.notes
            cost = used + line.height + self.notes_cost_for(notes)
            if cost > available + 0.5:
                break
            used += line.height
            count += 1
        remaining = len(lines) - first
        if 0 < count < remaining:
            if count == 1 and remaining > 1:
                return 0
            if remaining - count == 1 and count >= 2:
                return count - 1
        return count

    def notes_cost(self, lines: list) -> float:
        return self.notes_cost_for([note for line in lines for note in line.notes])

    def notes_cost_for(self, notes: list[NoteReferenceItem]) -> float:
        if not notes:
            return 0.0
        width = self.page.geometry.content_width
        for note in notes:
            if not note.note_layouts:
                note.note_layouts = self.layout.blocks(note.note_blocks, width)
        height = sum(layout.height for note in notes for layout in note.note_layouts)
        return height + (0 if self.page.notes else NOTE_SEPARATOR_PIXELS)

    def put(self, placed) -> None:
        page = self.page
        if isinstance(placed, ParagraphSlice):
            notes = [note for line in placed.layout.lines[placed.first_line:placed.last_line] for note in line.notes]
            page.notes_height += self.notes_cost_for(notes)
            page.notes.extend(notes)
        page.placed.append(placed)
        page.used += placed.height

    def place_table(self, layout: TableLayout, section: SectionModel) -> None:
        header_rows = leading_header_rows(layout)
        groups = row_groups(layout)
        current: list[int] = []
        for group in groups:
            group_height = sum(layout.row_heights[row] for row in group)
            current_height = sum(layout.row_heights[row] for row in current)
            if current and current_height + group_height > self.page.remaining + 0.5:
                self.put(TableSlice(layout, current))
                self.new_page(section, follows_overflow=True)
                current = [row for row in header_rows if row not in group]
            elif not current and group_height > self.page.remaining + 0.5 and not self.page.is_empty:
                self.new_page(section, follows_overflow=True)
                current = [row for row in header_rows if row not in group and group[0] > max(header_rows, default=-1)]
            current.extend(group)
        if current:
            self.put(TableSlice(layout, current))


def leading_header_rows(layout: TableLayout) -> list[int]:
    rows = []
    for index, row in enumerate(layout.block.rows):
        if not row.is_header:
            break
        rows.append(index)
    return rows


def row_groups(layout: TableLayout) -> list[list[int]]:
    reach = list(range(len(layout.block.rows)))
    for cell in layout.block.cells:
        last = min(cell.row + cell.row_span, len(reach)) - 1
        reach[cell.row] = max(reach[cell.row], last)
    groups, start, end = [], 0, -1
    for row in range(len(reach)):
        end = max(end, reach[row])
        if row == end:
            groups.append(list(range(start, end + 1)))
            start = row + 1
    return groups
