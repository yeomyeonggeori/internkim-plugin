from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw
import pypdfium2

from office_render import RenderFailure, convert_to


RENDER_SCALE = 1.0
CONTACT_COLUMNS = 3
CONTACT_THUMBNAIL_WIDTH = 480
CONTACT_GAP = 16
LABEL_HEIGHT = 22
CONTACT_BACKGROUND = (236, 239, 243)
CONTACT_SHEET_NAME = "contact-sheet.png"
PDF_EXPORT_WITH_HIDDEN_SLIDES = 'pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}'


@dataclass(frozen=True)
class Rendering:
    pages: list[dict]
    contact_sheet: str


def render_presentation(command: str, presentation_path: Path, output_directory: Path, slide_numbers: list[int], slide_count: int, faces: frozenset) -> Rendering:
    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="office-render-") as scratch:
        font_paths = [Path(face.path) for _, face in faces]
        substitutions = [(requested, face.family) for requested, face in faces if face.substituted]
        pdf_path = convert_to(command, presentation_path, PDF_EXPORT_WITH_HIDDEN_SLIDES, Path(scratch), font_paths, substitutions)
        images = render_pages(pdf_path, slide_numbers, slide_count)
    pages = [save_page(image, number, output_directory) for number, image in images.items()]
    contact_sheet_path = output_directory / CONTACT_SHEET_NAME
    draw_contact_sheet(images).save(contact_sheet_path)
    return Rendering(pages, str(contact_sheet_path))


def render_pages(pdf_path: Path, slide_numbers: list[int], slide_count: int) -> dict[int, Image.Image]:
    document = pypdfium2.PdfDocument(str(pdf_path))
    try:
        if len(document) != slide_count:
            raise RenderFailure(f"LibreOffice wrote {len(document)} pages for {slide_count} slides, so pages cannot be matched to slides")
        return {number: document[number - 1].render(scale=RENDER_SCALE).to_pil().convert("RGB") for number in slide_numbers}
    finally:
        document.close()


def save_page(image: Image.Image, number: int, output_directory: Path) -> dict:
    path = output_directory / f"slide-{number:03d}.png"
    image.save(path)
    return {"slide": number, "path": str(path)}


def draw_contact_sheet(images: dict[int, Image.Image]) -> Image.Image:
    columns = min(CONTACT_COLUMNS, len(images))
    first = next(iter(images.values()))
    thumbnail_height = round(first.height * CONTACT_THUMBNAIL_WIDTH / first.width)
    rows = -(-len(images) // columns)
    cell_width, cell_height = CONTACT_THUMBNAIL_WIDTH + CONTACT_GAP, thumbnail_height + LABEL_HEIGHT + CONTACT_GAP
    sheet = Image.new("RGB", (columns * cell_width + CONTACT_GAP, rows * cell_height + CONTACT_GAP), CONTACT_BACKGROUND)
    canvas = ImageDraw.Draw(sheet)
    for position, (number, image) in enumerate(images.items()):
        left = CONTACT_GAP + (position % columns) * cell_width
        top = CONTACT_GAP + (position // columns) * cell_height
        canvas.text((left, top), f"slide {number}", fill=(0, 0, 0))
        sheet.paste(image.resize((CONTACT_THUMBNAIL_WIDTH, thumbnail_height), Image.LANCZOS), (left, top + LABEL_HEIGHT))
    return sheet
