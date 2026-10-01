from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw
import pypdfium2


SOFFICE_NAMES = ("soffice", "libreoffice")
MACOS_SOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
CONVERSION_TIMEOUT_SECONDS = 240
RENDER_SCALE = 1.0
CONTACT_COLUMNS = 3
CONTACT_THUMBNAIL_WIDTH = 480
CONTACT_GAP = 16
LABEL_HEIGHT = 22
CONTACT_BACKGROUND = (236, 239, 243)
CONTACT_SHEET_NAME = "contact-sheet.png"
PDF_EXPORT_WITH_HIDDEN_SLIDES = 'pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}'
SUBSTITUTION_PATH = "/org.openoffice.Office.Common/Font/Substitution"


@dataclass(frozen=True)
class Rendering:
    pages: list[dict]
    contact_sheet: str


class RenderFailure(Exception):
    pass


def soffice_command() -> str | None:
    found = next((shutil.which(name) for name in SOFFICE_NAMES if shutil.which(name)), None)
    if found:
        return found
    return str(MACOS_SOFFICE) if MACOS_SOFFICE.exists() else None


def render_presentation(command: str, presentation_path: Path, output_directory: Path, slide_numbers: list[int], slide_count: int, faces: frozenset) -> Rendering:
    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="office-render-") as scratch:
        prepare_profile(Path(scratch) / "profile", faces)
        pdf_path = convert_to_pdf(command, presentation_path, Path(scratch))
        images = render_pages(pdf_path, slide_numbers, slide_count)
    pages = [save_page(image, number, output_directory) for number, image in images.items()]
    contact_sheet_path = output_directory / CONTACT_SHEET_NAME
    draw_contact_sheet(images).save(contact_sheet_path)
    return Rendering(pages, str(contact_sheet_path))


def prepare_profile(profile: Path, faces: frozenset) -> None:
    fonts = profile / "user" / "fonts"
    fonts.mkdir(parents=True)
    for index, path in enumerate(sorted({face.path for _, face in faces})):
        (fonts / f"{index:03d}-{Path(path).name}").symlink_to(path)
    pairs = sorted({(requested, face.family) for requested, face in faces if face.substituted})
    (profile / "user" / "registrymodifications.xcu").write_text(replacement_table(pairs), encoding="utf-8")


def replacement_table(pairs: list[tuple[str, str]]) -> str:
    entries = "".join(
        f'<item oor:path="{SUBSTITUTION_PATH}/FontPairs"><node oor:name="_{index}" oor:op="replace">'
        f'<prop oor:name="Always" oor:op="fuse"><value>true</value></prop>'
        f'<prop oor:name="OnScreenOnly" oor:op="fuse"><value>false</value></prop>'
        f'<prop oor:name="ReplaceFont" oor:op="fuse"><value>{escape(requested)}</value></prop>'
        f'<prop oor:name="SubstituteFont" oor:op="fuse"><value>{escape(used)}</value></prop>'
        "</node></item>"
        for index, (requested, used) in enumerate(pairs)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<item oor:path="{SUBSTITUTION_PATH}"><prop oor:name="Replacement" oor:op="fuse"><value>true</value></prop></item>'
        f"{entries}</oor:items>"
    )


def convert_to_pdf(command: str, presentation_path: Path, scratch: Path) -> Path:
    profile = (scratch / "profile").as_uri()
    arguments = [command, f"-env:UserInstallation={profile}", "--headless", "--convert-to", PDF_EXPORT_WITH_HIDDEN_SLIDES, "--outdir", str(scratch), str(presentation_path)]
    try:
        completed = subprocess.run(arguments, capture_output=True, text=True, timeout=CONVERSION_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise RenderFailure(f"LibreOffice did not finish within {CONVERSION_TIMEOUT_SECONDS} seconds") from error
    pdf_path = scratch / f"{presentation_path.stem}.pdf"
    if completed.returncode != 0 or not pdf_path.exists():
        raise RenderFailure(f"LibreOffice exited {completed.returncode}: {(completed.stderr or completed.stdout).strip()[:400]}")
    return pdf_path


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
