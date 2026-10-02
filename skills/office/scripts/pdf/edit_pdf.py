#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from pypdf import PdfReader, PdfWriter

from core.office_inputs import add_password_argument, office_file, require_unlocked_pdf
from core.office_result import OfficeArgumentParser, Result, read_json_file, run_command
from core.office_schema import require_valid
from core.page_sizes import Paper
from core.units import MILLIMETRES_PER_INCH, POINTS_PER_INCH
from doc.document_pdf import PageLayout, render_document_pdf
from pdf.create_pdf import section_blocks
from pdf.pdf_definitions import SECTION


POINTS_TO_MILLIMETRES = MILLIMETRES_PER_INCH / POINTS_PER_INCH


def main() -> Result:
    arguments = parse_arguments()
    section = read_section(arguments)
    pdf_path = os.path.expanduser(arguments.pdf_path)
    require_unlocked_pdf(pdf_path, arguments.password)
    original_reader = PdfReader(pdf_path, password=arguments.password)
    layout = PageLayout(paper=last_page_paper(original_reader), page_numbers=False)
    with tempfile.TemporaryDirectory() as directory:
        appended_path = Path(directory) / "section.pdf"
        issues = render_document_pdf(section_blocks(section), appended_path, Path.cwd(), section.get("title") or Path(pdf_path).stem, layout=layout)
        merge_into_original(pdf_path, original_reader, appended_path, arguments.password)
    return Result(summary=f"appended a section page to {pdf_path}", output_path=pdf_path, issues=tuple(issues))


def read_section(arguments) -> dict:
    if arguments.section:
        section = read_json_file(arguments.section)
        location = "section"
    else:
        section = {"title": arguments.heading or "", "paragraphs": arguments.paragraph, "bullets": arguments.bullet}
        location = "arguments"
    require_valid(SECTION, section, location)
    return section


def last_page_paper(reader: PdfReader) -> Paper:
    box = reader.pages[-1].mediabox
    return Paper("original", float(box.width) * POINTS_TO_MILLIMETRES, float(box.height) * POINTS_TO_MILLIMETRES, 0)


def merge_into_original(pdf_path: str, original_reader: PdfReader, appended_path: Path, password: str | None) -> None:
    appended_reader = PdfReader(appended_path)
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
    parser = OfficeArgumentParser()
    parser.add_argument("pdf_path", type=office_file("pdf"), help="Path to the .pdf to edit in place")
    parser.add_argument("--heading", metavar="TEXT", help="Section heading for the appended page")
    parser.add_argument("--paragraph", action="append", default=[], metavar="TEXT", help="Paragraph to add")
    parser.add_argument("--bullet", action="append", default=[], metavar="TEXT", help="Bullet item to add")
    parser.add_argument("--section", metavar="JSON_PATH", help="JSON file with one section; office guide pdf describes it")
    add_password_argument(parser)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
