#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from docx_markdown import DEFAULT_DOCUMENT_FONT, DEFAULT_DOCUMENT_FONT_SIZE, markdown_document
from doc_definitions import PDF_RENDERER_UNAVAILABLE
from document_pdf import can_render, render_document_pdf
from markdown_blocks import Heading, parse_markdown
from markdown_charts import require_valid_charts
from office_result import KOREAN_FONT_UNAVAILABLE, Issue, OfficeArgumentParser, OfficeFailure, Result, run_command
from pdf_fonts import register_regular_and_bold
from pdf_markdown import MarkdownPdf
from skill_runtime import HANGUL_FONT_PATHS, cache_home_path


PDF_FONT_CANDIDATES = [Path(candidate) for candidate in HANGUL_FONT_PATHS]
PDF_FONT_FAMILY = "DocumentFont"


def main() -> Result:
    arguments = parse_arguments()
    markdown_path = Path(arguments.markdown_path)
    markdown_text = markdown_path.read_text(encoding="utf-8")
    output_path = Path(arguments.output) if arguments.output else markdown_path.with_suffix("." + arguments.format)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    blocks = parse_markdown(markdown_text)
    require_valid_charts(blocks, markdown_path.name)
    if arguments.format == "pdf":
        issues = export_pdf(blocks, markdown_text, output_path, markdown_path.parent, arguments.font_path, arguments.font_size)
    else:
        document, issues = markdown_document(blocks, arguments.font, arguments.font_size, markdown_path.parent)
        document.save(output_path)
    return Result(summary=f"exported {output_path} from {markdown_path}", output_path=str(output_path), issues=tuple(issues))


def export_pdf(blocks: list, markdown_text: str, output_path: Path, source_directory: Path, font_path_argument: str, font_size: float) -> list[Issue]:
    if can_render():
        return render_document_pdf(blocks, output_path, source_directory, document_title(blocks, output_path), Path(font_path_argument) if font_path_argument else None)
    issues = export_plain_pdf(blocks, markdown_text, output_path, source_directory, font_path_argument, font_size)
    return [PDF_RENDERER_UNAVAILABLE.issue("neither bun nor node 18 is on PATH, so the plain fallback renderer drew the PDF", str(output_path)), *issues]


def document_title(blocks: list, output_path: Path) -> str:
    return next((block.text for block in blocks if isinstance(block, Heading)), output_path.stem)


def export_plain_pdf(blocks: list, markdown_text: str, output_path: Path, source_directory: Path, font_path_argument: str, font_size: float) -> list[Issue]:
    font_path = resolve_pdf_font(font_path_argument)
    has_font = bool(font_path and font_path.exists())
    if not has_font and any(ord(character) > 0x2000 for character in markdown_text):
        raise OfficeFailure(KOREAN_FONT_UNAVAILABLE.issue("non-Latin PDF text requires --font-path or an installed Korean-capable font"))
    renderer = MarkdownPdf(PDF_FONT_FAMILY if has_font else "Helvetica", font_size, source_directory)
    font_issues = register_document_fonts(renderer.pdf, font_path) if has_font else []
    issues = font_issues + [issue for block in blocks for issue in renderer.add_block(block)]
    renderer.pdf.output(str(output_path))
    return issues


def register_document_fonts(pdf, font_path: Path) -> list[Issue]:
    issues = register_regular_and_bold(pdf, PDF_FONT_FAMILY, font_path)
    pdf.add_font(PDF_FONT_FAMILY, "I", str(font_path))
    return issues


def is_embeddable_font(font_path: Path) -> bool:
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return True
    try:
        font = TTFont(str(font_path), fontNumber=0, lazy=True)
    except Exception:
        return False
    return "OS/2" in font and "cmap" in font


def cached_font_paths() -> list[Path]:
    fonts_directory = cache_home_path(os.environ) / "fonts"
    return [fonts_directory / "NanumGothic.ttf", fonts_directory / "NotoSansKR-Regular.ttf"]


def resolve_pdf_font(font_path_argument: str) -> Path | None:
    if font_path_argument:
        return Path(font_path_argument)
    for candidate in cached_font_paths() + PDF_FONT_CANDIDATES:
        if candidate.exists() and is_embeddable_font(candidate):
            return candidate
    return None


def parse_arguments():
    parser = OfficeArgumentParser(description="Render a Markdown source of truth into a .docx or .pdf deliverable, keeping links, local images, and nested lists.")
    parser.add_argument("markdown_path", help="path to content.md")
    parser.add_argument("--output", help="output path; defaults next to the markdown")
    parser.add_argument("--format", default="docx", choices=["docx", "pdf"], help="deliverable format")
    parser.add_argument("--font", default=DEFAULT_DOCUMENT_FONT, help="base font family name for docx")
    parser.add_argument("--font-size", type=float, default=DEFAULT_DOCUMENT_FONT_SIZE)
    parser.add_argument("--font-path", default="", help="Korean-capable TTF for pdf output instead of the bundled Paperlogy; a Bold file beside it is used for bold")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
