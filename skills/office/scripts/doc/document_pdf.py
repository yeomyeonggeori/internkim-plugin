from __future__ import annotations

from pathlib import Path

from PIL import Image as PillowImage, UnidentifiedImageError

from doc.block_writers import SizedImage, html_blocks
from doc.doc_definitions import GLYPH_NOT_COVERED, IMAGE_UNAVAILABLE, PDF_RENDERER_FAILED
from doc.document_pagination import MAXIMUM_PAGINATION_PASSES, stranded_heading
from fontTools.ttLib import TTFont

from doc.latex_math import math_text, text_with_math_drawn
from doc.markdown_blocks import Equation, Image, Paragraph, Table, local_image_problem
from fonts.registry import MONOSPACE, SANS_BODY, BundledFamily, default_family
from core.office_result import BOLD_FONT_UNAVAILABLE, Issue, OfficeFailure
from fonts.pdf_registration import bold_sibling
from render.renderer import DocumentPdfRequest, FontFile, RenderFailed, RendererUnavailable, javascript_runtime, render_document_pdf as render_pdf
from core.page_sizes import DEFAULT_PAPER
from core.units import CSS_PIXELS_PER_INCH


SCRIPTS_PATH = Path(__file__).resolve().parent
CHOSEN_FAMILY = "Document"
CSS_PATH = SCRIPTS_PATH / "document_pdf.css"
SIDE_MARGIN_PIXELS = 64
DEFAULT_DOTS_PER_INCH = 96


def can_render() -> bool:
    try:
        javascript_runtime()
    except RendererUnavailable:
        return False
    return True


def render_document_pdf(blocks: list, output_path: Path, source_directory: Path, title: str, font_path: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []
    sized = [sized_image(block, source_directory, issues) if isinstance(block, Image) else block for block in blocks]
    fonts = chosen_fonts(font_path, issues) + family_fonts(default_family(MONOSPACE))
    missing = uncovered_characters(markdown_source_text(blocks), fonts)
    if missing:
        issues.append(GLYPH_NOT_COVERED.issue(f"no font the PDF carries draws {' '.join(missing)}; each shows as an empty box", "".join(missing)))
    try:
        render_keeping_headings_with_their_text(sized, output_path, title, fonts)
    except (RendererUnavailable, RenderFailed) as reason:
        raise OfficeFailure(PDF_RENDERER_FAILED.issue(f"{output_path.name} was not drawn: {reason}", str(output_path)))
    return issues


def render_keeping_headings_with_their_text(blocks: list, output_path: Path, title: str, fonts: list[FontFile]) -> None:
    headings_on_new_page: frozenset[int] = frozenset()
    for _ in range(MAXIMUM_PAGINATION_PASSES):
        render_pdf(render_request(blocks, output_path, title, fonts, headings_on_new_page))
        stranded = stranded_heading(output_path, blocks, headings_on_new_page)
        if stranded is None:
            return
        headings_on_new_page |= {stranded}


def render_request(blocks: list, output_path: Path, title: str, fonts: list[FontFile], headings_on_new_page: frozenset[int] = frozenset()) -> DocumentPdfRequest:
    return DocumentPdfRequest(
        html="\n".join(html_blocks(blocks, fonts[0].family, headings_on_new_page)),
        css=CSS_PATH.read_text(encoding="utf-8"),
        output_path=output_path,
        title=title,
        fonts=tuple(fonts),
        margin={"left": SIDE_MARGIN_PIXELS, "right": SIDE_MARGIN_PIXELS},
    )


def chosen_fonts(font_path: Path | None, issues: list[Issue]) -> list[FontFile]:
    body = family_fonts(default_family(SANS_BODY))
    if font_path is None:
        return body
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


def sized_image(image: Image, source_directory: Path, issues: list[Issue]):
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
    text_width = DEFAULT_PAPER.pixels[0] - 2 * SIDE_MARGIN_PIXELS
    scale = min(1.0, text_width / width)
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
    return [text_with_math_drawn(getattr(block, "text", ""))]
