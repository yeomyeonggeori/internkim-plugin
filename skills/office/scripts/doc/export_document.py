#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from fonts.docx_embedding import save_document
from doc.blocks.writers import embedded_image, html_document
from doc.blocks.docx import DEFAULT_DOCUMENT_FONT, markdown_document
from doc.blocks.pdf import DocumentFonts, render_document_pdf
from doc.blocks.latex_math import math_issues
from doc.blocks.markdown import Heading, parse_markdown
from doc.blocks.charts import require_valid_charts
from core.office_arguments import route_arguments
from core.office_inputs import read_text_input
from fonts.registry import BODY_SIZE_POINTS
from core.office_result import Issue, Result, run_command


def main() -> Result:
    arguments = route_arguments("create", "md", font=DEFAULT_DOCUMENT_FONT, font_size=BODY_SIZE_POINTS)
    markdown_path = Path(arguments.source)
    output_path = Path(arguments.output)
    output_format = output_path.suffix.lower().lstrip(".")
    blocks = parse_markdown(read_text_input(arguments.source))
    require_valid_charts(blocks, markdown_path.name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    issues = WRITERS[output_format](blocks, output_path, markdown_path.parent, arguments)
    return Result(summary=f"created {output_path} from {markdown_path}", output_path=str(output_path), issues=(*math_issues(blocks, output_format), *issues))


def write_docx(blocks: list, output_path: Path, source_directory: Path, arguments) -> list[Issue]:
    document, issues = markdown_document(blocks, arguments.font, arguments.font_size, source_directory)
    save_document(document, output_path)
    return issues


def write_pdf(blocks: list, output_path: Path, source_directory: Path, arguments) -> list[Issue]:
    return export_pdf(blocks, output_path, source_directory, arguments.font_path or "")


def write_html(blocks: list, output_path: Path, source_directory: Path, arguments) -> list[Issue]:
    page = html_document([embedded_image(block, source_directory) for block in blocks], document_title(blocks, output_path))
    output_path.write_text(page, encoding="utf-8")
    return []


def export_pdf(blocks: list, output_path: Path, source_directory: Path, font_path_argument: str) -> list[Issue]:
    return render_document_pdf(blocks, output_path, source_directory, document_title(blocks, output_path), DocumentFonts(font_path=Path(font_path_argument) if font_path_argument else None))


def document_title(blocks: list, output_path: Path) -> str:
    return next((block.text for block in blocks if isinstance(block, Heading)), output_path.stem)


WRITERS = {"docx": write_docx, "pdf": write_pdf, "html": write_html}


if __name__ == "__main__":
    raise SystemExit(run_command(main))
