#!/usr/bin/env python3
import argparse
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import create_pdf as pdf_helper


def parse_arguments():
    parser = argparse.ArgumentParser(description="Append a new section page to an existing PDF in place.")
    parser.add_argument("pdf_path", nargs="?", help="Path to the .pdf; defaults to the newest .pdf in ~/documents")
    parser.add_argument("--heading", metavar="TEXT", help="Section heading for the appended page")
    parser.add_argument("--paragraph", action="append", default=[], metavar="TEXT", help="Paragraph to add")
    parser.add_argument("--bullet", action="append", default=[], metavar="TEXT", help="Bullet item to add")
    parser.add_argument("--section", metavar="JSON_PATH", help="JSON file with a section spec (same schema as create_pdf sections array element)")
    return parser.parse_args()


def resolve_pdf_path(given_path):
    if given_path:
        return os.path.expanduser(given_path)
    documents = sorted(
        glob.glob(os.path.expanduser("~/documents/*.pdf")),
        key=os.path.getmtime,
        reverse=True,
    )
    if not documents:
        raise SystemExit("no .pdf found in ~/documents; pass the document path explicitly")
    return documents[0]


def load_section_from_json(json_path):
    with open(os.path.expanduser(json_path), "r", encoding="utf-8") as section_file:
        section = json.load(section_file)
    if not isinstance(section, dict):
        raise ValueError("section JSON must be an object")
    return section


def build_appended_page(section_data, font_name, font_path):
    from fpdf import FPDF

    appended_pdf = FPDF(orientation="P", unit="mm", format="A4")
    appended_pdf.set_margins(18, 18, 18)
    appended_pdf.set_auto_page_break(auto=True, margin=16)
    if font_path and font_path.exists():
        appended_pdf.add_font(font_name, fname=str(font_path))
    appended_pdf.add_page()
    appended_pdf.set_font(font_name, size=11)
    appended_pdf.set_text_color(31, 41, 55)
    pdf_helper.add_section(appended_pdf, section_data, font_name)
    return bytes(appended_pdf.output())


def merge_into_original(pdf_path, appended_page_bytes):
    from pypdf import PdfReader, PdfWriter

    original_reader = PdfReader(pdf_path)
    appended_reader = PdfReader(io.BytesIO(appended_page_bytes))
    writer = PdfWriter()
    for page in original_reader.pages:
        writer.add_page(page)
    for page in appended_reader.pages:
        writer.add_page(page)
    with open(pdf_path, "wb") as output_file:
        writer.write(output_file)


def main():
    arguments = parse_arguments()
    pdf_path = resolve_pdf_path(arguments.pdf_path)

    if arguments.section:
        section_data = load_section_from_json(arguments.section)
    else:
        section_data = {
            "title": arguments.heading or "",
            "paragraphs": arguments.paragraph,
            "bullets": arguments.bullet,
        }

    font_name, font_path = pdf_helper.resolve_font({})
    appended_page_bytes = build_appended_page(section_data, font_name, font_path)
    merge_into_original(pdf_path, appended_page_bytes)
    print(pdf_path)


if __name__ == "__main__":
    main()
