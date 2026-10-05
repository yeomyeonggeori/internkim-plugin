from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image as PillowImage, UnidentifiedImageError

from doc.blocks.writers import SizedImage, html_blocks
from doc.doc_definitions import GLYPH_NOT_COVERED, IMAGE_UNAVAILABLE
from doc.blocks.pagination import MAXIMUM_PAGINATION_PASSES, stranded_heading
from fontTools.ttLib import TTFont

from doc.blocks.latex_math import math_text, text_with_math_drawn
from doc.blocks.markdown import CodeBlock, Equation, Image, Paragraph, Table, local_image_problem
from fonts.registry import MONOSPACE, SANS_BODY, BundledFamily, default_family, resolved_face
from core.office_operations import save_atomically
from core.office_result import BOLD_FONT_UNAVAILABLE, Issue, OfficeFailure
from fonts.font_files import bold_sibling
from render.renderer import PAGE_NUMBER_FOOTER, RENDER_FAILED, RENDERER_UNAVAILABLE, DocumentPdfRequest, FontFile, RenderFailed, RendererUnavailable, render_document_pdf as render_pdf
from core.page_sizes import DEFAULT_PAPER, Paper
from core.units import CSS_PIXELS_PER_INCH, PIXELS_PER_POINT, millimetres_to_pixels
from balance.fit import fit_rhythm
from balance.measure import Body, measure_pdf
from balance.rhythm import Rhythm
from balance.tokens import BODY_BOTTOM_MARGIN_MILLIMETERS, BODY_SIDE_MARGIN_MILLIMETERS, BODY_TOP_MARGIN_MILLIMETERS
from core.skill_paths import ASSETS_PATH


CHOSEN_FAMILY = "Document"
CSS_PATH = ASSETS_PATH / "document-pdf" / "document-pdf.css"
DEFAULT_DOTS_PER_INCH = 96


def skill_margin() -> dict:
    millimetres = {"top": BODY_TOP_MARGIN_MILLIMETERS, "right": BODY_SIDE_MARGIN_MILLIMETERS, "bottom": BODY_BOTTOM_MARGIN_MILLIMETERS, "left": BODY_SIDE_MARGIN_MILLIMETERS}
    return {side: millimetres_to_pixels(value) for side, value in millimetres.items()}


@dataclass(frozen=True)
class PageLayout:
    paper: Paper = DEFAULT_PAPER
    margin: dict = field(default_factory=lambda: skill_margin())
    page_numbers: bool = True
    is_balanced: bool = True

    @property
    def body(self) -> Body:
        page_height_points = self.paper.exact_pixels["height"] / PIXELS_PER_POINT
        return Body(self.margin["top"] / PIXELS_PER_POINT, page_height_points - self.margin["bottom"] / PIXELS_PER_POINT)

    @property
    def text_width_pixels(self) -> float:
        return self.paper.exact_pixels["width"] - self.margin["left"] - self.margin["right"]


@dataclass(frozen=True)
class DocumentFonts:
    font_path: Path | None = None
    family_name: str | None = None


def render_document_pdf(blocks: list, output_path: Path, source_directory: Path, title: str, chosen: DocumentFonts = DocumentFonts(), layout: PageLayout = PageLayout()) -> list[Issue]:
    issues: list[Issue] = []
    sized = [sized_image(block, source_directory, layout, issues) if isinstance(block, Image) else block for block in blocks]
    fonts = covering_fonts(chosen, markdown_source_text(blocks), issues)
    draw(output_path, lambda drawn_path: render_fitted(sized, drawn_path, title, fonts, layout))
    return issues


def covering_fonts(chosen: DocumentFonts, text: str, issues: list[Issue]) -> list[FontFile]:
    fonts = chosen_fonts(chosen, issues) + family_fonts(default_family(MONOSPACE))
    missing = uncovered_characters(text, fonts)
    if missing:
        issues.append(GLYPH_NOT_COVERED.issue(f"no font the PDF carries draws {' '.join(missing)}; each shows as an empty box", "".join(missing)))
    return fonts


def draw(output_path: Path, render: Callable[[Path], None]) -> None:
    try:
        save_atomically(lambda temporary_path: render(Path(temporary_path)), str(output_path))
    except RendererUnavailable as reason:
        raise OfficeFailure(RENDERER_UNAVAILABLE.issue(f"{output_path.name} was not written: {reason}", str(output_path)))
    except RenderFailed as reason:
        raise OfficeFailure(RENDER_FAILED.issue(f"{output_path.name} was not drawn: {reason}", str(output_path)))


def render_fitted(blocks: list, output_path: Path, title: str, fonts: list[FontFile], layout: PageLayout) -> None:
    def draw_at(rhythm: Rhythm):
        render_keeping_headings_with_their_text(blocks, output_path, title, fonts, layout, rhythm)
        return measure_pdf(output_path, layout.body)

    draw_at(fit_rhythm(draw_at) if layout.is_balanced else Rhythm())


def render_keeping_headings_with_their_text(blocks: list, output_path: Path, title: str, fonts: list[FontFile], layout: PageLayout, rhythm: Rhythm) -> None:
    headings_on_new_page: frozenset[int] = frozenset()
    for _ in range(MAXIMUM_PAGINATION_PASSES):
        render_pdf(render_request(blocks, output_path, title, fonts, layout, rhythm, headings_on_new_page))
        stranded = stranded_heading(output_path, blocks, headings_on_new_page)
        if stranded is None:
            return
        headings_on_new_page |= {stranded}


def render_request(blocks: list, output_path: Path, title: str, fonts: list[FontFile], layout: PageLayout, rhythm: Rhythm, headings_on_new_page: frozenset[int] = frozenset()) -> DocumentPdfRequest:
    return DocumentPdfRequest(
        html="\n".join(rhythm.lifted(html_blocks(blocks, fonts[0].family, headings_on_new_page))),
        css=rhythm.css(CSS_PATH.read_text(encoding="utf-8")),
        output_path=output_path,
        title=title,
        fonts=tuple(fonts),
        size=layout.paper.exact_pixels,
        margin=layout.margin,
        footer=PAGE_NUMBER_FOOTER if layout.page_numbers else None,
    )


def chosen_fonts(chosen: DocumentFonts, issues: list[Issue]) -> list[FontFile]:
    body = family_fonts(default_family(SANS_BODY))
    if chosen.font_path is None:
        family = resolved_face(chosen.family_name).family if chosen.family_name else default_family(SANS_BODY)
        return family_fonts(family) + ([] if family is default_family(SANS_BODY) else body)
    font_path = chosen.font_path
    bold_path = bold_sibling(font_path)
    if bold_path is None:
        issues.append(BOLD_FONT_UNAVAILABLE.issue(f"no bold face found beside {font_path}; headings render without bold", str(font_path)))
        return [FontFile(CHOSEN_FAMILY, font_path, 400)] + body
    return [FontFile(CHOSEN_FAMILY, font_path, 400), FontFile(CHOSEN_FAMILY, bold_path, 700)] + body


def family_fonts(family: BundledFamily) -> list[FontFile]:
    return [FontFile(family.name, family.path(face), face.weight, generic=family.generic) for face in family.faces]


def uncovered_characters(text: str, fonts: list[FontFile]) -> list[str]:
    covered: set[int] = set()
    for path in {font.path for font in fonts}:
        covered.update(TTFont(str(path), fontNumber=0, lazy=True).getBestCmap())
    return sorted({character for character in text if not character.isspace() and ord(character) not in covered})


def sized_image(image: Image, source_directory: Path, layout: PageLayout, issues: list[Issue]):
    image_path = source_directory / image.source
    problem = local_image_problem(image.source, image_path)
    if problem is None:
        try:
            width, height = image_size_pixels(image_path)
        except (UnidentifiedImageError, OSError) as error:
            problem = f"could not be read ({error})"
    if problem is not None:
        issues.append(IMAGE_UNAVAILABLE.issue(f"image {image.source} {problem}; wrote its alt text instead", image.source))
        return replace_with_alt(image)
    scale = min(1.0, layout.text_width_pixels / width)
    return SizedImage(image.alt, image_path.read_bytes(), image_path.suffix, round(width * scale), round(height * scale))


def replace_with_alt(image: Image):
    return Paragraph(f"*{image.alt or image.source}*")


def image_size_pixels(image_path: Path) -> tuple[int, int]:
    with PillowImage.open(image_path) as image:
        dots_per_inch = float(image.info.get("dpi", (DEFAULT_DOTS_PER_INCH,))[0] or DEFAULT_DOTS_PER_INCH)
        factor = CSS_PIXELS_PER_INCH / dots_per_inch
        return round(image.width * factor), round(image.height * factor)


def markdown_source_text(blocks: list) -> str:
    return "\n".join(text for block in blocks for text in block_texts(block))


def block_texts(block) -> list[str]:
    if isinstance(block, Table):
        return [text_with_math_drawn(cell) for row in block.rows for cell in row]
    if isinstance(block, Equation):
        return [math_text(block.latex, display=True)]
    if isinstance(block, CodeBlock):
        return [block.text]
    return [text_with_math_drawn(getattr(block, "text", ""))]
