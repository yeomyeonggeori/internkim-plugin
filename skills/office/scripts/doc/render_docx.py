#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from doc.preview.layout import Layout
from doc.preview.pagination import Paginator, displayed_page_numbers
from doc.preview.document import DocxModelBuilder
from doc.preview.html import PageWriter
from render.office_preview import Preview, approximation_issues, blank_page_issues, draw_pages, write_preview
from core.office_outputs import preview_directory
from core.office_arguments import route_arguments
from core.office_result import Result, run_command
from fonts.preview import FontRegistry


def docx_preview(source_path: Path) -> tuple[Preview, list[dict]]:
    builder = DocxModelBuilder(source_path)
    sections = builder.sections()
    fonts = FontRegistry()
    pages = Paginator(Layout(fonts)).paginate(sections)
    preview = builder.preview
    shown_numbers = displayed_page_numbers(pages)
    preview.pages = [PageWriter(index + 1, len(pages), shown_numbers[index]).page_html(page) for index, page in enumerate(pages)]
    preview.blank_pages = [f"page {number}" for number, page in enumerate(pages, start=1) if page.is_blank]
    return preview, fonts.preview_fonts()


def main() -> Result:
    arguments = parse_arguments()
    source_path = Path(arguments.file).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(2, "no such file", str(source_path))
    output_directory = preview_directory(source_path, arguments.output_directory)
    preview, preview_fonts = docx_preview(source_path)
    preview_path = write_preview(preview, output_directory)
    drawn, drawing_issues = draw_pages(preview_path, preview_fonts, output_directory / f"{source_path.stem}.pdf")
    issues = [*approximation_issues(preview, source_path.name), *blank_page_issues(preview), *drawing_issues]
    details = {"preview": str(preview_path), "pageCount": len(preview.pages), "previewFonts": preview_fonts, "approximations": preview.approximations, **drawn}
    return Result(summary=f"laid out {source_path.name} as {len(preview.pages)} pages in {preview_path}", output_path=str(preview_path), issues=tuple(issues), details=details)


def parse_arguments():
    return route_arguments("render", "docx")


if __name__ == "__main__":
    raise SystemExit(run_command(main))
