#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
import pypdfium2

from office_inputs import add_password_argument, office_file, require_unlocked_pdf
from office_result import INVALID_VALUE, OfficeArgumentParser, OfficeFailure, Result, run_command
from pdf_pages import select_pages


DEFAULT_PAGE_LIMIT = 12
DEFAULT_SCALE = 1.5
MINIMUM_SCALE = 0.25
MAXIMUM_SCALE = 4.0
CONTACT_SHEET_NAME = "contact-sheet.png"
CONTACT_COLUMNS = 4
CONTACT_THUMBNAIL_WIDTH = 320
CONTACT_GAP = 12
LABEL_HEIGHT = 18
BACKGROUND = (235, 235, 235)


def main() -> Result:
    arguments = parse_arguments()
    require_unlocked_pdf(arguments.pdf_path, arguments.password)
    source_path = Path(arguments.pdf_path).expanduser()
    output_directory = Path(arguments.output_directory).expanduser() if arguments.output_directory else source_path.with_name(f"{source_path.stem}-pages")
    details = render_pages(source_path, arguments.pages, arguments.scale, output_directory, arguments.password)
    return Result(summary=f"rendered {len(details['pages'])} of {details['pageCount']} pages to {output_directory}", output_path=str(output_directory), details=details)


def render_pages(source_path: Path, selection: str, scale: float, output_directory: Path, password: str | None) -> dict:
    require_scale(scale)
    document = pypdfium2.PdfDocument(str(source_path), password=password)
    try:
        page_count = len(document)
        numbers = choose_pages(selection, page_count)
        output_directory.mkdir(parents=True, exist_ok=True)
        images = {number: render_page(document, number, scale) for number in numbers}
    finally:
        document.close()
    pages = [save_page(image, number, output_directory) for number, image in images.items()]
    contact_sheet_path = output_directory / CONTACT_SHEET_NAME
    draw_contact_sheet(images).save(contact_sheet_path)
    return {
        "pageCount": page_count,
        "scale": scale,
        "truncated": not selection and len(numbers) < page_count,
        "pages": pages,
        "contactSheet": str(contact_sheet_path),
    }


def require_scale(scale: float):
    if not MINIMUM_SCALE <= scale <= MAXIMUM_SCALE:
        raise OfficeFailure(INVALID_VALUE.issue(f"--scale {scale} is outside {MINIMUM_SCALE} to {MAXIMUM_SCALE}", location="--scale", suggestion="1 is 72 dpi; use 1.5 to read text and 0.5 for a quick look"))


def choose_pages(selection: str, page_count: int) -> list[int]:
    if selection:
        return select_pages(selection, page_count)
    return list(range(1, min(page_count, DEFAULT_PAGE_LIMIT) + 1))


def render_page(document, number: int, scale: float) -> Image.Image:
    return document[number - 1].render(scale=scale).to_pil().convert("RGB")


def save_page(image: Image.Image, number: int, output_directory: Path) -> dict:
    path = output_directory / f"page-{number:03d}.png"
    image.save(path)
    return {"page": number, "path": str(path), "widthPixels": image.width, "heightPixels": image.height}


def draw_contact_sheet(images: dict[int, Image.Image]) -> Image.Image:
    thumbnails = {number: thumbnail(image) for number, image in images.items()}
    columns = min(CONTACT_COLUMNS, len(thumbnails))
    rows = -(-len(thumbnails) // columns)
    cell_height = max(image.height for image in thumbnails.values()) + LABEL_HEIGHT
    cell_width = CONTACT_THUMBNAIL_WIDTH + CONTACT_GAP
    sheet = Image.new("RGB", (columns * cell_width + CONTACT_GAP, rows * (cell_height + CONTACT_GAP) + CONTACT_GAP), BACKGROUND)
    canvas = ImageDraw.Draw(sheet)
    for position, (number, image) in enumerate(thumbnails.items()):
        left = CONTACT_GAP + (position % columns) * cell_width
        top = CONTACT_GAP + (position // columns) * (cell_height + CONTACT_GAP)
        canvas.text((left, top), str(number), fill=(0, 0, 0))
        sheet.paste(image, (left, top + LABEL_HEIGHT))
    return sheet


def thumbnail(image: Image.Image) -> Image.Image:
    height = max(1, round(image.height * CONTACT_THUMBNAIL_WIDTH / image.width))
    return image.resize((CONTACT_THUMBNAIL_WIDTH, height), Image.LANCZOS)


def parse_arguments():
    parser = OfficeArgumentParser(description="Render PDF pages to PNG files and one contact sheet with every page side by side.")
    parser.add_argument("pdf_path", type=office_file("pdf"))
    parser.add_argument("--pages", default="", help=f"pages to render, such as 1,3-5; default the first {DEFAULT_PAGE_LIMIT}")
    parser.add_argument("--scale", type=float, default=DEFAULT_SCALE, help=f"pixels per point, default {DEFAULT_SCALE}; 1 is 72 dpi")
    parser.add_argument("--output-directory", default="", help="where the PNG files go, default <pdf name>-pages beside the PDF")
    add_password_argument(parser)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
