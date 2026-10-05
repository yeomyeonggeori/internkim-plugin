from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from balance.tokens import BODY_BOTTOM_MARGIN_MILLIMETERS, BODY_TOP_MARGIN_MILLIMETERS
from core.units import MILLIMETRES_PER_INCH, POINTS_PER_INCH

TEXT_OBJECT = 1
LINE_JOIN_POINTS = 3.0
POINTS_PER_MILLIMETRE = POINTS_PER_INCH / MILLIMETRES_PER_INCH


@dataclass(frozen=True)
class PageMeasure:
    number: int
    body_height: float
    content_bottom: float
    text_lines: int | None
    largest_gap: float

    @property
    def fill(self) -> float:
        return min(1.0, self.content_bottom / self.body_height)

    @property
    def gap_ratio(self) -> float:
        return self.largest_gap / self.body_height


@dataclass(frozen=True)
class Body:
    top: float
    bottom: float

    @property
    def height(self) -> float:
        return self.bottom - self.top


def skill_body(page_height: float) -> Body:
    return Body(BODY_TOP_MARGIN_MILLIMETERS * POINTS_PER_MILLIMETRE, page_height - BODY_BOTTOM_MARGIN_MILLIMETERS * POINTS_PER_MILLIMETRE)


def measure_pdf(path: Path, body: Body | None = None) -> list[PageMeasure]:
    import pypdfium2

    document = pypdfium2.PdfDocument(str(path))
    try:
        return [measure_page(page, number, body) for number, page in enumerate(document, start=1)]
    finally:
        document.close()


def measure_page(page, number: int, fixed_body: Body | None) -> PageMeasure:
    _, page_height = page.get_size()
    body = fixed_body or skill_body(page_height)
    intervals = [(page_height - top, page_height - bottom, kind) for kind, bottom, top in object_bounds(page)]
    inside = sorted((top, bottom, kind) for top, bottom, kind in intervals if bottom <= body.bottom + 0.5)
    if not inside:
        return PageMeasure(number, body.height, 0.0, 0, 0.0)
    return PageMeasure(number, body.height, max(bottom for _, bottom, _ in inside) - body.top, count_lines(inside), widest_gap(inside))


def object_bounds(page) -> list[tuple[int, float, float]]:
    return [(obj.type, obj.get_bounds()[1], obj.get_bounds()[3]) for obj in page.get_objects()]


def count_lines(intervals: list[tuple[float, float, int]]) -> int:
    texts = sorted((top, bottom) for top, bottom, kind in intervals if kind == TEXT_OBJECT)
    return len(merged(texts, LINE_JOIN_POINTS * -1))


def widest_gap(intervals: list[tuple[float, float, int]]) -> float:
    spans = merged(sorted((top, bottom) for top, bottom, _ in intervals), 0.0)
    return max((later[0] - earlier[1] for earlier, later in zip(spans, spans[1:])), default=0.0)


def merged(spans: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for top, bottom in spans:
        if result and top <= result[-1][1] + tolerance:
            result[-1] = (result[-1][0], max(result[-1][1], bottom))
        else:
            result.append((top, bottom))
    return result


def measure_docx(path: Path) -> list[PageMeasure]:
    from doc.preview.document import DocxModelBuilder
    from doc.preview.layout import Layout
    from doc.preview.pagination import Paginator
    from fonts.preview import FontRegistry

    pages = Paginator(Layout(FontRegistry())).paginate(DocxModelBuilder(path).sections())
    return [PageMeasure(number, page.body_bottom - page.body_top, page.used + page.notes_height, None, 0.0) for number, page in enumerate(pages, start=1)]
