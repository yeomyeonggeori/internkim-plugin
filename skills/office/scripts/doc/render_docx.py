#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS_PATH = Path(__file__).resolve().parents[1]
sys.path[1:1] = [str(SCRIPTS_PATH / "deck")]

from docx_layout import Layout  # noqa: E402
from docx_pagination import Paginator  # noqa: E402
from docx_preview import DocxModelBuilder  # noqa: E402
from docx_preview_html import PageWriter  # noqa: E402
from office_preview import Preview, approximation_issues, blank_page_issues, draw_pages, write_preview  # noqa: E402
from office_inputs import office_file
from office_result import OfficeArgumentParser, Result, run_command  # noqa: E402
from fonts.preview import FontRegistry  # noqa: E402


def docx_preview(source_path: Path) -> tuple[Preview, list[dict]]:
    builder = DocxModelBuilder(source_path)
    sections = builder.sections()
    fonts = FontRegistry()
    pages = Paginator(Layout(fonts)).paginate(sections)
    preview = builder.preview
    preview.pages = [PageWriter(number, len(pages)).page_html(page) for number, page in enumerate(pages, start=1)]
    preview.blank_pages = [f"page {number}" for number, page in enumerate(pages, start=1) if page.is_blank]
    return preview, fonts.preview_fonts()


def main() -> Result:
    arguments = parse_arguments()
    source_path = Path(arguments.source_path).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(2, "no such file", str(source_path))
    output_directory = Path(arguments.output_directory).expanduser() if arguments.output_directory else source_path.with_name(f"{source_path.stem}-preview")
    preview, preview_fonts = docx_preview(source_path)
    preview_path = write_preview(preview, output_directory)
    drawn, drawing_issues = draw_pages(preview_path, preview_fonts, output_directory / f"{source_path.stem}.pdf")
    issues = [*approximation_issues(preview, source_path.name), *blank_page_issues(preview), *drawing_issues]
    details = {"preview": str(preview_path), "pageCount": len(preview.pages), "previewFonts": preview_fonts, "approximations": preview.approximations, **drawn}
    return Result(summary=f"laid out {source_path.name} as {len(preview.pages)} pages in {preview_path}", output_path=str(preview_path), issues=tuple(issues), details=details)


def parse_arguments():
    parser = OfficeArgumentParser(description="Lay out a .docx page by page as preview HTML, then draw each page as a PNG, contact sheets and a PDF: page size and margins, styles, numbering, tables, pictures, headers, footers and footnotes.")
    parser.add_argument("source_path", type=office_file("docx"), help="the .docx to lay out")
    parser.add_argument("--output-directory", help="where preview.html, the page images and the PDF go; default <name>-preview beside the file")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
