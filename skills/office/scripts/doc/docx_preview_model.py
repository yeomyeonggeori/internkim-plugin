from __future__ import annotations

from dataclasses import dataclass, field

from office_preview import PageGeometry
from fonts.preview import FontRequest


@dataclass(frozen=True)
class TextStyle:
    font: FontRequest
    css: tuple

    def declarations(self) -> dict:
        return dict(self.css)


@dataclass
class TextItem:
    text: str
    style: TextStyle


@dataclass
class TabItem:
    style: TextStyle


@dataclass
class LineBreakItem:
    style: TextStyle


@dataclass
class PageBreakItem:
    pass


@dataclass
class ImageItem:
    source: str
    width: float
    height: float


@dataclass
class FieldItem:
    kind: str
    style: TextStyle


@dataclass
class NoteReferenceItem:
    number: int
    note_blocks: list
    style: TextStyle
    note_layouts: list = field(default_factory=list)


@dataclass
class ChartItem:
    model: object
    palette: tuple
    width: float
    height: float


@dataclass
class BoxItem:
    blocks: list
    width: float
    height: float


@dataclass
class ParagraphBlock:
    items: list
    base_style: TextStyle
    align: str = "left"
    indent_left: float = 0
    indent_right: float = 0
    first_line: float = 0
    hanging: float = 0
    space_before: float = 0
    space_after: float = 0
    line: float | None = None
    line_rule: str = "auto"
    keep_next: bool = False
    page_break_before: bool = False
    label: str = ""
    label_style: TextStyle | None = None
    background: str | None = None
    borders: dict = field(default_factory=dict)
    tab_stops: tuple = ()


@dataclass
class CellBlock:
    row: int
    column: int
    span: int
    row_span: int
    blocks: list
    padding: tuple[float, float, float, float]
    background: str | None = None
    borders: dict = field(default_factory=dict)
    vertical_align: str = "top"
    continuation_top: dict | None = None


@dataclass
class RowBlock:
    height: float = 0
    exact: bool = False
    is_header: bool = False


@dataclass
class TableBlock:
    columns: list[float]
    rows: list[RowBlock]
    cells: list[CellBlock]
    indent: float = 0
    align: str = "left"


@dataclass
class PageBreakBlock:
    pass


@dataclass
class SectionModel:
    geometry: PageGeometry
    blocks: list
    header: list
    footer: list
    starts_new_page: bool = True
    watermark: str = ""
    watermark_image: ImageItem | None = None
    page_number_start: int | None = None
