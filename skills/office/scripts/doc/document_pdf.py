from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image as PillowImage, UnidentifiedImageError

from block_writers import SizedImage, html_blocks
from doc_definitions import GLYPH_NOT_COVERED, IMAGE_UNAVAILABLE, PDF_RENDERER_FAILED
from fontTools.ttLib import TTFont

from markdown_blocks import Image, Paragraph, Table, local_image_problem
from office_result import BOLD_FONT_UNAVAILABLE, Issue, OfficeFailure
from pdf_fonts import font_file_for_face
from skill_runtime import HANGUL_FONT_PATHS, SKILL_CACHE_DIRECTORY_NAME, cache_home_path, find_bold_face


SCRIPTS_PATH = Path(__file__).resolve().parent
ASSETS_PATH = SCRIPTS_PATH.parents[1] / "assets"
MANIFEST_PATH = ASSETS_PATH / "document-pdf" / "package.json"
FONT_DIRECTORY = ASSETS_PATH / "fonts" / "paperlogy"
FONT_FAMILY = "Paperlogy"
FONT_FILES = ((400, "Paperlogy-4Regular.ttf"), (600, "Paperlogy-6SemiBold.ttf"), (700, "Paperlogy-7Bold.ttf"))
FALLBACK_FAMILY = "Korean Fallback"
CHOSEN_FAMILY = "Document"
CSS_PATH = SCRIPTS_PATH / "document_pdf.css"
RENDER_SCRIPT = SCRIPTS_PATH / "document_pdf.mjs"
PAGE_SIZES_PIXELS = {"a4": (794, 1123)}
SIDE_MARGIN_PIXELS = 64
CSS_PIXELS_PER_INCH = 96
DEFAULT_DOTS_PER_INCH = 96
RENDER_TIMEOUT_SECONDS = 180


def renderer_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["BUN_INSTALL_CACHE_DIR"] = str(cache_home_path(os.environ) / SKILL_CACHE_DIRECTORY_NAME / "bun-cache")
    return environment


def can_render() -> bool:
    return shutil.which("bun") is not None


def renderer_directory() -> Path:
    directory = cache_home_path(os.environ) / SKILL_CACHE_DIRECTORY_NAME / "node" / "document-pdf"
    manifest = directory / "package.json"
    if manifest.exists() and manifest.read_bytes() == MANIFEST_PATH.read_bytes() and (directory / "node_modules" / "takumi-pdf").is_dir():
        return directory
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(MANIFEST_PATH, manifest)
    completed = subprocess.run(["bun", "install", "--production"], cwd=directory, capture_output=True, text=True, env=renderer_environment(), timeout=RENDER_TIMEOUT_SECONDS, check=False)
    if completed.returncode != 0:
        raise OfficeFailure(PDF_RENDERER_FAILED.issue(f"bun install of takumi-pdf failed: {last_line(completed)}", str(directory)))
    return directory


def render_document_pdf(blocks: list, output_path: Path, source_directory: Path, title: str, font_path: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []
    sized = [sized_image(block, source_directory, issues) if isinstance(block, Image) else block for block in blocks]
    fallback = fallback_font()
    fonts = chosen_fonts(font_path, issues) + fallback_fonts(fallback)
    request = render_request(sized, output_path, title, fonts)
    missing = uncovered_characters(markdown_source_text(blocks), fonts)
    if missing:
        issues.append(GLYPH_NOT_COVERED.issue(f"no bundled or installed font draws {' '.join(missing)}; each shows as an empty box", "".join(missing)))
    directory = renderer_directory()
    with tempfile.TemporaryDirectory(prefix="office-document-pdf-") as work:
        request_path = Path(work) / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        completed = subprocess.run(["bun", str(RENDER_SCRIPT), str(request_path)], cwd=directory, capture_output=True, text=True, env=renderer_environment(), timeout=RENDER_TIMEOUT_SECONDS, check=False)
    if completed.returncode != 0 or not output_path.exists():
        raise OfficeFailure(PDF_RENDERER_FAILED.issue(f"takumi-pdf could not render {output_path.name}: {last_line(completed)}", str(output_path)))
    return issues


def render_request(blocks: list, output_path: Path, title: str, fonts: list[tuple[str, int, Path]]) -> dict:
    return {
        "html": "\n".join(html_blocks(blocks)),
        "cssPath": str(CSS_PATH),
        "output": str(output_path.resolve()),
        "title": title,
        "size": "a4",
        "landscape": False,
        "margin": {"left": SIDE_MARGIN_PIXELS, "right": SIDE_MARGIN_PIXELS},
        "fontFamilies": list(dict.fromkeys(family for family, _, _ in fonts)),
        "fonts": [{"family": family, "weight": weight, "path": str(path)} for family, weight, path in fonts],
    }


def fallback_font() -> Path | None:
    return next((Path(path) for path in HANGUL_FONT_PATHS if Path(path).exists()), None)


def chosen_fonts(font_path: Path | None, issues: list[Issue]) -> list[tuple[str, int, Path]]:
    if font_path is None:
        return [(FONT_FAMILY, weight, FONT_DIRECTORY / name) for weight, name in FONT_FILES]
    bold_face = find_bold_face(font_path)
    if bold_face is None:
        issues.append(BOLD_FONT_UNAVAILABLE.issue(f"no bold face found beside {font_path}; headings render without bold", str(font_path)))
        return [(CHOSEN_FAMILY, 400, font_path)]
    return [(CHOSEN_FAMILY, 400, font_path), (CHOSEN_FAMILY, 700, font_file_for_face(*bold_face))]


def fallback_fonts(fallback: Path | None) -> list[tuple[str, int, Path]]:
    return [(FALLBACK_FAMILY, 400, fallback)] if fallback is not None else []


def uncovered_characters(text: str, fonts: list[tuple[str, int, Path]]) -> list[str]:
    covered: set[int] = set()
    for path in {path for _, _, path in fonts}:
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
    text_width = PAGE_SIZES_PIXELS["a4"][0] - 2 * SIDE_MARGIN_PIXELS
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
        return [cell for row in block.rows for cell in row]
    return [getattr(block, "text", "")]


def last_line(completed) -> str:
    lines = (completed.stderr or completed.stdout or "").strip().splitlines()
    return lines[-1] if lines else f"exit code {completed.returncode}"
