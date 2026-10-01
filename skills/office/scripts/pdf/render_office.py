#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from office_render import convert_with_libreoffice
from office_result import OfficeArgumentParser, Result, run_command
from render_pdf import DEFAULT_PAGE_LIMIT, DEFAULT_SCALE, render_pages


def main() -> Result:
    arguments = parse_arguments()
    source_path = Path(arguments.path).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(2, "no such file", str(source_path))
    output_directory = Path(arguments.output_directory).expanduser() if arguments.output_directory else source_path.with_name(f"{source_path.stem}-pages")
    pdf_path = convert_with_libreoffice(source_path, "pdf", output_directory)
    details = {"pdf": str(pdf_path), "laidOutBy": "LibreOffice", **render_pages(pdf_path, arguments.pages, arguments.scale, output_directory)}
    summary = f"laid out {source_path.name} with LibreOffice and rendered {len(details['pages'])} of {details['pageCount']} pages to {output_directory}"
    return Result(summary=summary, output_path=str(output_directory), details=details)


def parse_arguments():
    parser = OfficeArgumentParser(description="Lay out a Word document or workbook with LibreOffice, then render its pages to PNG files and a contact sheet. LibreOffice's layout is close to Word's and Excel's, not identical.")
    parser.add_argument("path", help="the .docx, .xlsx, or other office file")
    parser.add_argument("--pages", default="", help=f"pages to render, such as 1,3-5; default the first {DEFAULT_PAGE_LIMIT}")
    parser.add_argument("--scale", type=float, default=DEFAULT_SCALE, help=f"pixels per point, default {DEFAULT_SCALE}; 1 is 72 dpi")
    parser.add_argument("--output-directory", default="", help="where the PDF and PNG files go, default <file name>-pages beside the file")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
