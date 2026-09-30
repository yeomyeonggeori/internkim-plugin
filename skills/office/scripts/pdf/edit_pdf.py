#!/usr/bin/env python3
import io

from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

import create_pdf as pdf_helper
from documents_folder import resolve_document_path
from office_result import OfficeArgumentParser, Result, read_json_file, run_command
from office_schema import require_valid
from pdf_definitions import SECTION


def main() -> Result:
    arguments = parse_arguments()
    section = read_section(arguments)
    pdf_path = resolve_document_path(arguments.pdf_path, "pdf")
    font_name, font_path = pdf_helper.resolve_font({})
    appended_page_bytes = build_appended_page(section, font_name, font_path)
    merge_into_original(pdf_path, appended_page_bytes)
    return Result(summary=f"appended a section page to {pdf_path}", output_path=pdf_path)


def read_section(arguments) -> dict:
    if arguments.section:
        section = read_json_file(arguments.section)
        location = "section"
    else:
        section = {"title": arguments.heading or "", "paragraphs": arguments.paragraph, "bullets": arguments.bullet}
        location = "arguments"
    require_valid(SECTION, section, location)
    return section


def build_appended_page(section: dict, font_name: str, font_path) -> bytes:
    appended_pdf = FPDF(orientation="P", unit="mm", format="A4")
    appended_pdf.set_margins(18, 18, 18)
    appended_pdf.set_auto_page_break(auto=True, margin=16)
    if font_path and font_path.exists():
        appended_pdf.add_font(font_name, fname=str(font_path))
    appended_pdf.add_page()
    appended_pdf.set_font(font_name, size=11)
    appended_pdf.set_text_color(31, 41, 55)
    pdf_helper.add_section(appended_pdf, section, font_name)
    return bytes(appended_pdf.output())


def merge_into_original(pdf_path: str, appended_page_bytes: bytes) -> None:
    original_reader = PdfReader(pdf_path)
    appended_reader = PdfReader(io.BytesIO(appended_page_bytes))
    writer = PdfWriter()
    for page in original_reader.pages:
        writer.add_page(page)
    for page in appended_reader.pages:
        writer.add_page(page)
    with open(pdf_path, "wb") as output_file:
        writer.write(output_file)


def parse_arguments():
    parser = OfficeArgumentParser(description="Append a new section page to an existing PDF in place.")
    parser.add_argument("pdf_path", nargs="?", help="Path to the .pdf; defaults to the newest .pdf in ~/documents")
    parser.add_argument("--heading", metavar="TEXT", help="Section heading for the appended page")
    parser.add_argument("--paragraph", action="append", default=[], metavar="TEXT", help="Paragraph to add")
    parser.add_argument("--bullet", action="append", default=[], metavar="TEXT", help="Bullet item to add")
    parser.add_argument("--section", metavar="JSON_PATH", help="JSON file with one section; office guide pdf describes it")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
