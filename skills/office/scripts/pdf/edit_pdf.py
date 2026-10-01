#!/usr/bin/env python3
from __future__ import annotations

import io
import json

from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

import create_pdf as pdf_helper
from office_inputs import add_password_argument, office_file, require_unlocked_pdf, resolve_document_path
from office_result import DOCUMENTS_FOLDER, OfficeArgumentParser, Result, read_json_file, run_command
from office_schema import require_valid
from pdf_definitions import SECTION
from fonts.pdf_registration import register_document_font
from page_sizes import DEFAULT_PAPER


def main() -> Result:
    arguments = parse_arguments()
    section = read_section(arguments)
    pdf_path = resolve_document_path(arguments.pdf_path, "pdf")
    require_unlocked_pdf(pdf_path, arguments.password)
    font_name, font_path = pdf_helper.resolve_font({})
    appended_page_bytes, font_issues = build_appended_page(section, font_name, font_path)
    merge_into_original(pdf_path, appended_page_bytes, arguments.password)
    return Result(summary=f"appended a section page to {pdf_path}", output_path=pdf_path, issues=tuple(font_issues))


def read_section(arguments) -> dict:
    if arguments.section:
        section = read_json_file(arguments.section)
        location = "section"
    else:
        section = {"title": arguments.heading or "", "paragraphs": arguments.paragraph, "bullets": arguments.bullet}
        location = "arguments"
    require_valid(SECTION, section, location)
    return section


def build_appended_page(section: dict, font_name: str, font_path) -> tuple[bytes, list]:
    appended_pdf = FPDF(orientation="P", unit="mm", format=DEFAULT_PAPER.millimetres)
    appended_pdf.set_margins(18, 18, 18)
    appended_pdf.set_auto_page_break(auto=True, margin=16)
    font_issues = register_document_font(appended_pdf, font_name, font_path, json.dumps(section, ensure_ascii=False))
    appended_pdf.add_page()
    appended_pdf.set_font(font_name, size=11)
    appended_pdf.set_text_color(31, 41, 55)
    pdf_helper.add_section(appended_pdf, section, font_name)
    return bytes(appended_pdf.output()), font_issues


def merge_into_original(pdf_path: str, appended_page_bytes: bytes, password: str | None) -> None:
    original_reader = PdfReader(pdf_path, password=password)
    appended_reader = PdfReader(io.BytesIO(appended_page_bytes))
    writer = PdfWriter()
    for page in original_reader.pages:
        writer.add_page(page)
    for page in appended_reader.pages:
        writer.add_page(page)
    if password and original_reader.is_encrypted:
        writer.encrypt(password)
    with open(pdf_path, "wb") as output_file:
        writer.write(output_file)


def parse_arguments():
    parser = OfficeArgumentParser(description="Append a new section page to an existing PDF in place.")
    parser.add_argument("pdf_path", nargs="?", type=office_file("pdf"), help=f"Path to the .pdf; defaults to the newest .pdf in {DOCUMENTS_FOLDER}")
    parser.add_argument("--heading", metavar="TEXT", help="Section heading for the appended page")
    parser.add_argument("--paragraph", action="append", default=[], metavar="TEXT", help="Paragraph to add")
    parser.add_argument("--bullet", action="append", default=[], metavar="TEXT", help="Bullet item to add")
    parser.add_argument("--section", metavar="JSON_PATH", help="JSON file with one section; office guide pdf describes it")
    add_password_argument(parser)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
