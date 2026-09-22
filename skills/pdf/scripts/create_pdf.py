#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from skill_runtime import HANGUL_FONT_PATHS, cache_home_path, ensure_requirements


def load_specification(specification_path):
    with open(specification_path, "r", encoding="utf-8") as specification_file:
        specification = json.load(specification_file)
    if not isinstance(specification, dict):
        raise ValueError("PDF specification must be an object")
    return specification


def require_text(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def optional_text(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("text fields must be strings")
    return value.strip()


def build_specification(arguments):
    sections = []
    for heading_text in arguments.heading:
        sections.append({"title": heading_text, "paragraphs": [], "bullets": []})
    if not sections and (arguments.paragraph or arguments.bullet):
        sections.append({"title": "", "paragraphs": [], "bullets": []})
    if sections:
        last_section = sections[-1]
        last_section["paragraphs"] = arguments.paragraph
        last_section["bullets"] = arguments.bullet
    return {
        "title": arguments.title or "",
        "subtitle": arguments.subtitle or "",
        "sections": sections,
    }


def create_pdf(specification):
    if not ensure_requirements("pdf"):
        raise RuntimeError("pdf dependencies are unavailable after bootstrap")

    from fpdf import FPDF

    class DocumentPDF(FPDF):
        def footer(self):
            if not specification.get("pageNumbers", True):
                return
            self.set_y(-14)
            self.set_font(active_font_name, size=8)
            self.set_text_color(92, 99, 112)
            self.cell(0, 8, f"{self.page_no()}", align="C")

    active_font_name, font_path = resolve_font(specification)
    validate_font_availability(specification, font_path)

    pdf = DocumentPDF(orientation="P", unit="mm", format=specification.get("format", "A4"))
    margin = float(specification.get("marginMillimeters", 18))
    pdf.set_margins(margin, margin, margin)
    pdf.set_auto_page_break(auto=True, margin=16)
    if font_path:
        pdf.add_font(active_font_name, fname=str(font_path))
    pdf.add_page()
    pdf.set_font(active_font_name, size=11)
    pdf.set_text_color(31, 41, 55)

    add_title(pdf, specification, active_font_name)
    for section in specification.get("sections", []):
        add_section(pdf, section, active_font_name)
    return pdf


def add_title(pdf, specification, font_name):
    title = optional_text(specification.get("title"))
    if not title:
        return
    pdf.set_font(font_name, size=18)
    pdf.set_text_color(17, 24, 39)
    write_multiline(pdf, 0, 9, title, align="L")
    subtitle = optional_text(specification.get("subtitle"))
    if subtitle:
        pdf.set_font(font_name, size=10)
        pdf.set_text_color(75, 85, 99)
        write_multiline(pdf, 0, 6, subtitle)
    pdf.set_draw_color(203, 213, 225)
    pdf.ln(2)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(7)


def add_section(pdf, section, font_name):
    if not isinstance(section, dict):
        raise ValueError("each section must be an object")
    title = optional_text(section.get("title"))
    if title:
        pdf.set_font(font_name, size=13)
        pdf.set_text_color(17, 24, 39)
        write_multiline(pdf, 0, 7, title)
        pdf.ln(1)
    pdf.set_font(font_name, size=10.5)
    pdf.set_text_color(31, 41, 55)
    for paragraph in section.get("paragraphs", []):
        write_multiline(pdf, 0, 6.2, require_text(paragraph, "paragraph"))
        pdf.ln(1.5)
    for item in section.get("bullets", []):
        write_multiline(pdf, 0, 6.2, "• " + require_text(item, "bullet"))
    table = section.get("table")
    if table:
        add_table(pdf, table, font_name)
    pdf.ln(4)


def add_table(pdf, table, font_name):
    if not isinstance(table, dict):
        raise ValueError("table must be an object")
    headers = table.get("headers", [])
    rows = table.get("rows", [])
    if not isinstance(headers, list) or not headers:
        raise ValueError("table.headers must be a non-empty array")
    if not isinstance(rows, list):
        raise ValueError("table.rows must be an array")
    pdf.set_font(font_name, size=9.5)
    column_widths = compute_column_widths(pdf, headers, rows)
    add_table_row(pdf, column_widths, headers, is_header=True)
    for row in rows:
        if not isinstance(row, list):
            raise ValueError("table rows must be arrays")
        add_table_row(pdf, column_widths, row, is_header=False)
    pdf.ln(1)


def compute_column_widths(pdf, headers, rows):
    available_width = pdf.w - pdf.l_margin - pdf.r_margin
    column_count = len(headers)
    cell_padding = 3
    minimum_width = available_width * 0.12
    desired_widths = [pdf.get_string_width(str(headers[index])) + cell_padding * 2 for index in range(column_count)]
    for row in rows:
        for index in range(column_count):
            value = row[index] if index < len(row) else ""
            text_width = pdf.get_string_width("" if value is None else str(value))
            desired_widths[index] = max(desired_widths[index], text_width + cell_padding * 2)
    bounded_widths = [max(minimum_width, width) for width in desired_widths]
    scale = available_width / sum(bounded_widths)
    return [width * scale for width in bounded_widths]


def add_table_row(pdf, column_widths, values, is_header):
    cell_padding = 1.6
    line_height = 5.0
    texts = row_cell_texts(values, len(column_widths))
    wrapped_columns = [wrap_text_to_lines(pdf, text, width - cell_padding * 2) for text, width in zip(texts, column_widths)]
    row_line_count = max(len(lines) for lines in wrapped_columns)
    row_height = row_line_count * line_height + cell_padding * 2
    ensure_room_for_row(pdf, row_height)
    row_x = pdf.l_margin
    row_y = pdf.get_y()
    set_row_colors(pdf, is_header)
    cell_x = row_x
    for width, lines in zip(column_widths, wrapped_columns):
        pdf.rect(cell_x, row_y, width, row_height, style="DF" if is_header else "D")
        draw_wrapped_lines(pdf, cell_x, row_y, width, lines, line_height, cell_padding)
        cell_x += width
    pdf.set_xy(row_x, row_y + row_height)


def row_cell_texts(values, column_count):
    return ["" if index >= len(values) or values[index] is None else str(values[index]) for index in range(column_count)]


def set_row_colors(pdf, is_header):
    if is_header:
        pdf.set_fill_color(235, 241, 247)
        pdf.set_text_color(17, 24, 39)
        return
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(31, 41, 55)


def ensure_room_for_row(pdf, row_height):
    if pdf.get_y() + row_height > pdf.h - pdf.b_margin:
        pdf.add_page()


def draw_wrapped_lines(pdf, x, y, width, lines, line_height, cell_padding):
    for line_index, line in enumerate(lines):
        pdf.set_xy(x + cell_padding, y + cell_padding + line_index * line_height)
        pdf.cell(width - cell_padding * 2, line_height, line, border=0)


def wrap_text_to_lines(pdf, text, max_width):
    if text == "":
        return [""]
    lines = []
    for raw_line in text.split("\n"):
        lines.extend(wrap_single_line(pdf, raw_line, max_width))
    return lines or [""]


def wrap_single_line(pdf, line, max_width):
    words = line.split(" ")
    wrapped_lines = []
    current_line = ""
    for word in words:
        candidate_line = word if current_line == "" else f"{current_line} {word}"
        if pdf.get_string_width(candidate_line) <= max_width:
            current_line = candidate_line
            continue
        if current_line:
            wrapped_lines.append(current_line)
        current_line = break_long_word(pdf, word, max_width, wrapped_lines)
    wrapped_lines.append(current_line)
    return wrapped_lines


def break_long_word(pdf, word, max_width, wrapped_lines):
    remaining_word = word
    while pdf.get_string_width(remaining_word) > max_width and len(remaining_word) > 1:
        split_index = find_character_split_index(pdf, remaining_word, max_width)
        wrapped_lines.append(remaining_word[:split_index])
        remaining_word = remaining_word[split_index:]
    return remaining_word


def find_character_split_index(pdf, text, max_width):
    for index in range(len(text), 0, -1):
        if pdf.get_string_width(text[:index]) <= max_width:
            return index
    return 1


def write_multiline(pdf, width, height, text, **options):
    pdf.multi_cell(width, height, text, new_x="LMARGIN", new_y="NEXT", **options)


def resolve_font(specification):
    configured_font = optional_text(specification.get("fontPath"))
    font_name = optional_text(specification.get("fontName")) or "ArtifactFont"
    if configured_font:
        return font_name, Path(configured_font)
    for candidate in candidate_font_paths():
        if candidate.exists() and is_embeddable_font(candidate):
            return font_name, candidate
    return "Helvetica", None


def validate_font_availability(specification, font_path):
    if font_path and font_path.exists():
        return
    text = json.dumps(specification, ensure_ascii=False)
    if contains_non_latin_text(text):
        raise ValueError("non-Latin PDF text requires fontPath or an installed Korean-capable font")


def is_embeddable_font(font_path):
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return True
    try:
        font = TTFont(str(font_path), fontNumber=0, lazy=True)
    except Exception:
        return False
    return "OS/2" in font and "cmap" in font


def cached_font_paths():
    fonts_directory = cache_home_path(os.environ) / "fonts"
    return [fonts_directory / "NanumGothic.ttf", fonts_directory / "NotoSansKR-Regular.ttf"]


LATIN_FALLBACK_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def candidate_font_paths():
    host_paths = HANGUL_FONT_PATHS + [LATIN_FALLBACK_FONT_PATH]
    return cached_font_paths() + [Path(candidate) for candidate in host_paths]


def contains_non_latin_text(text):
    return any(ord(character) > 127 for character in text)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Create a PDF from arguments or a JSON spec.")
    parser.add_argument("output_path", help="Path to the output .pdf file")
    parser.add_argument("--title", metavar="TEXT", default="", help="Document title")
    parser.add_argument("--subtitle", metavar="TEXT", default="", help="Document subtitle (optional)")
    parser.add_argument("--heading", action="append", default=[], metavar="TEXT", help="Add a section heading (repeatable)")
    parser.add_argument("--paragraph", action="append", default=[], metavar="TEXT", help="Add a paragraph (repeatable)")
    parser.add_argument("--bullet", action="append", default=[], metavar="TEXT", help="Add a bullet item (repeatable)")
    parser.add_argument("--spec", metavar="JSON_PATH", help="JSON spec file for rich PDFs (tables, multi-section layouts)")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    has_inline_content = arguments.title or arguments.subtitle or arguments.heading or arguments.paragraph or arguments.bullet
    if not arguments.spec and not has_inline_content:
        raise ValueError("provide at least --title, --heading, --paragraph, or --bullet; or pass --spec <file>")
    specification = load_specification(arguments.spec) if arguments.spec else build_specification(arguments)
    pdf = create_pdf(specification)
    output_path = Path(os.path.expanduser(arguments.output_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    print(output_path)


if __name__ == "__main__":
    main()
