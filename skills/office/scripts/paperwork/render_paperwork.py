#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from fonts.registry import SANS_BODY, default_family
from fonts.docx_embedding import save_document
from office_result import DOCUMENTS_FOLDER, MISSING_FIELD, PERMISSION_DENIED, OfficeArgumentParser, OfficeFailure, Result, read_json_file, run_command
from office_schema import require_valid
from fonts.pdf_registration import register_document_font
from paperwork_definitions import CONTRACT_DOCUMENT, PAPERWORK_CONTENT_FIELDS, PAPERWORK_DOCUMENT
from page_sizes import DEFAULT_PAPER
from paperwork_design import (
    COLOR_BORDER,
    COLOR_HEADER_FILL,
    COLOR_INK,
    COLOR_MUTED,
    COLOR_RULE,
    FONT_KOREAN_DOCX,
    LINE_SPACING,
    PDF_PAGE_MARGIN_MILLIMETERS,
    SIZE_BODY,
    SIZE_CLAUSE_HEADING,
    SIZE_LETTERHEAD_DETAIL,
    SIZE_LETTERHEAD_NAME,
    SIZE_TITLE,
)

PAGE_MARGIN_MILLIMETERS = PDF_PAGE_MARGIN_MILLIMETERS
LETTERHEAD_LOGO_HEIGHT = 10.0
APPROVAL_BOX_WIDTH = 20.0
APPROVAL_BOX_HEIGHT = 16.0
META_LABEL_WIDTH = 34.0
TABLE_LINE_HEIGHT = 5.2
TABLE_CELL_PADDING = 1.8
STAMP_SIZE_MILLIMETERS = 16.0
INK_COLOR = COLOR_INK
HEADING_COLOR = COLOR_INK
MUTED_COLOR = COLOR_MUTED
RULE_COLOR = COLOR_RULE
BORDER_COLOR = COLOR_BORDER
HEADER_FILL_COLOR = COLOR_HEADER_FILL


SPEC_HINT = "read the document type's spec at this skill's references/paperwork/<ko|en>/<type>.md and copy its Document JSON skeleton exactly"


def load_document(document_path):
    document = read_json_file(document_path)
    require_valid(PAPERWORK_DOCUMENT, document, "document")
    require_company_name(document["profile"])
    require_content(document)
    normalize_document(document)
    return document


def require_company_name(profile):
    if company_display_name(profile):
        return
    raise OfficeFailure(MISSING_FIELD.issue("document.profile.name: required; insert the company_info_get result into profile", "document.profile.name", suggestion=SPEC_HINT))


def require_content(document):
    if any(field in document for field in PAPERWORK_CONTENT_FIELDS):
        return
    raise OfficeFailure(MISSING_FIELD.issue(f"document has no content: add at least one of {', '.join(PAPERWORK_CONTENT_FIELDS)}", "document", suggestion=SPEC_HINT))


def normalize_document(document):
    signature = document.get("signature")
    if isinstance(signature, str) and signature.strip():
        lines = [line.strip() for line in signature.splitlines() if line.strip()]
        if len(lines) >= 2:
            document["signature"] = {"date": lines[0], "line": " ".join(lines[1:])}
        else:
            document["signature"] = {"line": lines[0]}
    notes = document.get("notes")
    if isinstance(notes, str) and notes.strip():
        document["notes"] = [notes.strip()]


def configured_font_path(document):
    configured_path = str(document.get("fontPath", "")).strip()
    return Path(configured_path) if configured_path else None


def render_document(document):
    from fpdf import FPDF

    footer_text = str(document.get("footer", "")).strip()

    class PaperworkPDF(FPDF):
        def footer(self):
            self.set_y(-13)
            self.set_font("Paperwork", size=7.5)
            self.set_text_color(*MUTED_COLOR)
            if footer_text:
                self.cell(0, 4, footer_text, align="C", new_x="LMARGIN", new_y="NEXT")
            if self.page_no() > 1 or self.pages_count > 1:
                self.cell(0, 4, f"- {self.page_no()} -", align="C")

        @property
        def pages_count(self):
            return len(self.pages)

    pdf = PaperworkPDF(orientation="P", unit="mm", format=DEFAULT_PAPER.millimetres)
    pdf.set_margins(PAGE_MARGIN_MILLIMETERS, PAGE_MARGIN_MILLIMETERS, PAGE_MARGIN_MILLIMETERS)
    pdf.set_auto_page_break(auto=True, margin=20)
    font_issues = register_document_font(pdf, "Paperwork", configured_font_path(document), json.dumps(document, ensure_ascii=False), default_family(SANS_BODY).name)
    pdf.add_page()

    profile = document.get("profile", {})
    add_letterhead(pdf, profile)
    add_approval_line(pdf, document.get("approvalLine", []))
    add_title(pdf, document)
    add_recipient(pdf, document.get("recipient"))
    add_meta_table(pdf, document.get("meta", []))
    add_item_table(pdf, document.get("items"))
    add_sections(pdf, document.get("sections", []))
    add_notes(pdf, document.get("notes", []))
    add_signature(pdf, document.get("signature"), profile)
    return pdf, font_issues


def content_width(pdf):
    return pdf.w - pdf.l_margin - pdf.r_margin


def set_body_font(pdf, size=10.0, color=INK_COLOR, is_bold=False):
    pdf.set_font("Paperwork", "B" if is_bold else "", size=size)
    pdf.set_text_color(*color)


def company_display_name(profile):
    if not isinstance(profile, dict):
        return ""
    return str(profile.get("name", "") or profile.get("companyName", "")).strip()


def add_letterhead(pdf, profile):
    top_y = pdf.get_y()
    logo_path = str(profile.get("logoPath", "")).strip()
    if logo_path and Path(logo_path).exists():
        pdf.image(logo_path, x=pdf.l_margin, y=top_y, h=LETTERHEAD_LOGO_HEIGHT)
    set_body_font(pdf, size=SIZE_LETTERHEAD_NAME, color=HEADING_COLOR, is_bold=True)
    pdf.set_y(top_y)
    pdf.cell(0, 5.5, company_display_name(profile), align="R", new_x="LMARGIN", new_y="NEXT")
    set_body_font(pdf, size=SIZE_LETTERHEAD_DETAIL, color=MUTED_COLOR)
    for line in letterhead_detail_lines(profile):
        pdf.cell(0, 3.8, line, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_draw_color(*RULE_COLOR)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(5)


def letterhead_detail_lines(profile):
    lines = []
    identity_parts = []
    legal_attributes = profile.get("legalAttributes")
    if isinstance(legal_attributes, list):
        for attribute in legal_attributes[:2]:
            if not isinstance(attribute, dict):
                continue
            label = str(attribute.get("label", "")).strip()
            value = str(attribute.get("value", "")).strip()
            if label and value:
                identity_parts.append(f"{label} {value}")
    legacy_registration = str(profile.get("registrationNumber", "")).strip()
    if legacy_registration and not identity_parts:
        identity_parts.append(f"사업자등록번호 {legacy_registration}")
    representative = str(profile.get("representative", "")).strip()
    if representative:
        representative_title = str(profile.get("representativeTitle", "")).strip() or "대표"
        identity_parts.append(f"{representative_title} {representative}")
    if identity_parts:
        lines.append("  ".join(identity_parts))
    address = str(profile.get("address", "")).strip()
    if address:
        lines.append(address)
    contact_parts = [str(profile.get(field, "")).strip() for field in ("phone", "email", "website")]
    contact_line = "  ".join(part for part in contact_parts if part)
    if contact_line:
        lines.append(contact_line)
    return lines


def add_approval_line(pdf, labels):
    if not labels:
        return
    table_width = APPROVAL_BOX_WIDTH * len(labels)
    start_x = pdf.w - pdf.r_margin - table_width
    start_y = pdf.get_y()
    pdf.set_draw_color(*BORDER_COLOR)
    set_body_font(pdf, size=8, color=HEADING_COLOR)
    for index, label in enumerate(labels):
        cell_x = start_x + index * APPROVAL_BOX_WIDTH
        pdf.set_fill_color(*HEADER_FILL_COLOR)
        pdf.rect(cell_x, start_y, APPROVAL_BOX_WIDTH, 6, style="DF")
        pdf.set_xy(cell_x, start_y)
        pdf.cell(APPROVAL_BOX_WIDTH, 6, label, align="C")
        pdf.rect(cell_x, start_y + 6, APPROVAL_BOX_WIDTH, APPROVAL_BOX_HEIGHT, style="D")
    pdf.set_y(start_y + 6 + APPROVAL_BOX_HEIGHT + 4)


def add_title(pdf, document):
    set_body_font(pdf, size=SIZE_TITLE + 3, color=HEADING_COLOR, is_bold=True)
    pdf.cell(0, 12, str(document["title"]).strip(), align="C", new_x="LMARGIN", new_y="NEXT")
    document_number = str(document.get("documentNumber", "")).strip()
    if document_number:
        set_body_font(pdf, size=8.5, color=MUTED_COLOR)
        pdf.cell(0, 4.5, f"문서번호 {document_number}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)


def add_recipient(pdf, recipient):
    if not isinstance(recipient, dict):
        return
    label = str(recipient.get("label", "수신")).strip()
    lines = recipient.get("lines", [])
    if not lines:
        return
    set_body_font(pdf, size=8.5, color=MUTED_COLOR)
    pdf.cell(0, 4.5, label, new_x="LMARGIN", new_y="NEXT")
    set_body_font(pdf, size=11, color=HEADING_COLOR)
    for line in lines:
        pdf.cell(0, 6, str(line).strip(), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def add_meta_table(pdf, meta_rows):
    if not meta_rows:
        return
    pdf.set_draw_color(*BORDER_COLOR)
    value_width = content_width(pdf) - META_LABEL_WIDTH
    for meta_row in meta_rows:
        label = str(meta_row.get("label", "")).strip()
        value = str(meta_row.get("value", "")).strip()
        set_body_font(pdf, size=9)
        value_lines = wrap_text_to_lines(pdf, value, value_width - TABLE_CELL_PADDING * 2)
        row_height = max(7.5, len(value_lines) * TABLE_LINE_HEIGHT + TABLE_CELL_PADDING * 2)
        ensure_room_for_row(pdf, row_height)
        row_y = pdf.get_y()
        pdf.set_fill_color(*HEADER_FILL_COLOR)
        pdf.rect(pdf.l_margin, row_y, META_LABEL_WIDTH, row_height, style="DF")
        pdf.rect(pdf.l_margin + META_LABEL_WIDTH, row_y, value_width, row_height, style="D")
        set_body_font(pdf, size=9, color=HEADING_COLOR, is_bold=True)
        pdf.set_xy(pdf.l_margin, row_y)
        pdf.cell(META_LABEL_WIDTH, row_height, label, align="C")
        set_body_font(pdf, size=9)
        draw_wrapped_lines(pdf, pdf.l_margin + META_LABEL_WIDTH, row_y, value_width, value_lines, "L")
        pdf.set_xy(pdf.l_margin, row_y + row_height)
    pdf.ln(4)


def add_item_table(pdf, items):
    if items is None:
        return
    headers = items["headers"]
    rows = items.get("rows") or []
    aligns = normalized_aligns(items.get("aligns"), len(headers))
    column_widths = compute_column_widths(pdf, headers, rows)
    add_table_row(pdf, column_widths, headers, ["C"] * len(headers), is_header=True)
    for row in rows:
        add_table_row(pdf, column_widths, row, aligns, is_header=False)
    pdf.ln(2)
    add_totals(pdf, items.get("totals", []))
    pdf.ln(3)


def normalized_aligns(aligns, column_count):
    if not isinstance(aligns, list):
        return ["L"] * column_count
    normalized = []
    for index in range(column_count):
        value = str(aligns[index]).strip().upper() if index < len(aligns) else "L"
        normalized.append(value if value in ("L", "C", "R") else "L")
    return normalized


def compute_column_widths(pdf, headers, rows):
    set_body_font(pdf, size=9)
    available_width = content_width(pdf)
    minimum_width = available_width * 0.08
    desired_widths = [pdf.get_string_width(str(header)) + TABLE_CELL_PADDING * 2 for header in headers]
    for row in rows:
        for index in range(len(headers)):
            value = row[index] if isinstance(row, list) and index < len(row) else ""
            text_width = pdf.get_string_width("" if value is None else str(value))
            desired_widths[index] = max(desired_widths[index], text_width + TABLE_CELL_PADDING * 2)
    bounded_widths = [max(minimum_width, width) for width in desired_widths]
    scale = available_width / sum(bounded_widths)
    return [width * scale for width in bounded_widths]


def add_table_row(pdf, column_widths, values, aligns, is_header):
    set_body_font(pdf, size=9, color=HEADING_COLOR if is_header else INK_COLOR, is_bold=is_header)
    texts = ["" if index >= len(values) or values[index] is None else str(values[index]) for index in range(len(column_widths))]
    wrapped_columns = [wrap_text_to_lines(pdf, text, width - TABLE_CELL_PADDING * 2) for text, width in zip(texts, column_widths)]
    row_line_count = max(len(lines) for lines in wrapped_columns)
    row_height = row_line_count * TABLE_LINE_HEIGHT + TABLE_CELL_PADDING * 2
    ensure_room_for_row(pdf, row_height)
    row_y = pdf.get_y()
    pdf.set_draw_color(*BORDER_COLOR)
    pdf.set_fill_color(*HEADER_FILL_COLOR)
    cell_x = pdf.l_margin
    for width, lines, align in zip(column_widths, wrapped_columns, aligns):
        pdf.rect(cell_x, row_y, width, row_height, style="DF" if is_header else "D")
        draw_wrapped_lines(pdf, cell_x, row_y, width, lines, align)
        cell_x += width
    pdf.set_xy(pdf.l_margin, row_y + row_height)


def add_totals(pdf, totals):
    for index, total_row in enumerate(totals):
        label = str(total_row.get("label", "")).strip()
        value = str(total_row.get("value", "")).strip()
        is_final_total = index == len(totals) - 1
        set_body_font(pdf, size=11 if is_final_total else 9.5, color=HEADING_COLOR if is_final_total else INK_COLOR, is_bold=is_final_total)
        pdf.cell(0, 7 if is_final_total else 5.5, f"{label}    {value}", align="R", new_x="LMARGIN", new_y="NEXT")


def add_sections(pdf, sections):
    for section in sections:
        title = str(section.get("title", "")).strip()
        if title:
            set_body_font(pdf, size=11, color=HEADING_COLOR, is_bold=True)
            write_multiline(pdf, 6.5, title)
            pdf.ln(0.5)
        set_body_font(pdf, size=9.5)
        for paragraph in section.get("paragraphs", []):
            write_multiline(pdf, 5.6, str(paragraph).strip())
            pdf.ln(1)
        for bullet in section.get("bullets", []):
            write_multiline(pdf, 5.6, "• " + str(bullet).strip())
        pdf.ln(3)


def add_notes(pdf, notes):
    if not notes:
        return
    pdf.ln(3)
    set_body_font(pdf, size=SIZE_BODY, color=HEADING_COLOR)
    for note in notes:
        pdf.cell(0, 7, str(note).strip(), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def add_signature(pdf, signature, profile):
    if not isinstance(signature, dict):
        return
    ensure_room_for_row(pdf, 34)
    pdf.ln(6)
    date_text = str(signature.get("date", "")).strip()
    if date_text:
        set_body_font(pdf, size=10)
        pdf.cell(0, 7, date_text, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
    line_text = str(signature.get("line", "")).strip()
    if not line_text:
        return
    seal_suffix = "  (인)"
    set_body_font(pdf, size=12, color=HEADING_COLOR, is_bold=True)
    full_line = line_text + seal_suffix
    line_y = pdf.get_y()
    pdf.cell(0, 8, full_line, align="C", new_x="LMARGIN", new_y="NEXT")
    stamp_path = str(profile.get("stampPath", "")).strip() if isinstance(profile, dict) else ""
    if signature.get("stamp") and stamp_path and Path(stamp_path).exists():
        line_width = pdf.get_string_width(full_line)
        seal_center_x = pdf.l_margin + content_width(pdf) / 2 + line_width / 2 - pdf.get_string_width(seal_suffix) / 3
        pdf.image(stamp_path, x=seal_center_x - STAMP_SIZE_MILLIMETERS / 2, y=line_y - STAMP_SIZE_MILLIMETERS / 2 + 4, w=STAMP_SIZE_MILLIMETERS)


def ensure_room_for_row(pdf, row_height):
    if pdf.get_y() + row_height > pdf.h - pdf.b_margin:
        pdf.add_page()


def draw_wrapped_lines(pdf, x, y, width, lines, align):
    for line_index, line in enumerate(lines):
        pdf.set_xy(x + TABLE_CELL_PADDING, y + TABLE_CELL_PADDING + line_index * TABLE_LINE_HEIGHT)
        pdf.cell(width - TABLE_CELL_PADDING * 2, TABLE_LINE_HEIGHT, line, align=align)


def wrap_text_to_lines(pdf, text, max_width):
    if text == "":
        return [""]
    lines = []
    for raw_line in str(text).split("\n"):
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


def write_multiline(pdf, height, text):
    pdf.multi_cell(0, height, text, new_x="LMARGIN", new_y="NEXT")


def load_contract_document(document_path):
    document = read_json_file(document_path)
    require_valid(CONTRACT_DOCUMENT, document, "document")
    return document


def generate_docx(document, output_path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt, RGBColor

    word_document = Document()
    section = word_document.sections[0]
    margin_inches = (document.get("page") or {}).get("marginInches")
    margin = Inches(float(0.9 if margin_inches is None else margin_inches))
    section.top_margin = section.bottom_margin = margin
    section.left_margin = section.right_margin = margin
    font_name = text_or_default(document.get("fontName"), FONT_KOREAN_DOCX)
    font_size = float(SIZE_BODY if document.get("fontSize") is None else document["fontSize"])
    style = word_document.styles["Normal"]
    style.font.name = font_name
    style.font.size = Pt(font_size)
    style.font.color.rgb = RGBColor(*COLOR_INK)
    style.paragraph_format.line_spacing = LINE_SPACING
    style.element.rPr.rFonts.set(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia", font_name)
    title = text_or_default(document.get("title"), "").strip()
    if title:
        paragraph = word_document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(18)
        run = paragraph.add_run(title)
        run.bold = True
        run.font.size = Pt(SIZE_TITLE)
        run.font.color.rgb = RGBColor(*COLOR_INK)
    for block in document["blocks"]:
        append_docx_block(word_document, block)
    save_document(word_document, output_path)


def text_or_default(value, default):
    return default if value is None else str(value)


def append_docx_block(word_document, block):
    from docx.shared import Pt, RGBColor

    block_type = block["type"]
    if block_type == "heading":
        paragraph = word_document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(10)
        paragraph.paragraph_format.space_after = Pt(2)
        run = paragraph.add_run(text_or_default(block.get("text"), ""))
        run.bold = True
        run.font.size = Pt(SIZE_CLAUSE_HEADING)
        run.font.color.rgb = RGBColor(*COLOR_INK)
    elif block_type == "paragraph":
        word_document.add_paragraph(text_or_default(block.get("text"), ""))
    elif block_type == "bullets":
        for item in block.get("items") or []:
            word_document.add_paragraph(str(item), style="List Bullet")
    elif block_type == "table":
        rows = block["rows"]
        table = word_document.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = "Table Grid"
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                if column_index < len(table.rows[row_index].cells):
                    table.rows[row_index].cells[column_index].text = "" if value is None else str(value)


def main():
    parser = OfficeArgumentParser(description="Render a paperwork document JSON to a letterhead PDF or a DOCX contract; office guide paperwork describes both.")
    parser.add_argument("document_path", help="Path to the document JSON file")
    parser.add_argument("output_path", help="Path to the output .pdf or .docx file")
    arguments = parser.parse_args()
    output_path = Path(os.path.expanduser(arguments.output_path))
    document_path = os.path.expanduser(arguments.document_path)
    try:
        font_issues = write_output(document_path, output_path)
    except PermissionError as error:
        raise OfficeFailure(PERMISSION_DENIED.issue(
            f"cannot write to {output_path} (permission denied)",
            location=error.filename,
            suggestion=f"rerun the SAME command with the output changed to {DOCUMENTS_FOLDER}/{output_path.parent.name}/{output_path.name}",
        )) from error
    return Result(summary=f"rendered {output_path}", output_path=str(output_path), issues=tuple(font_issues))


def write_output(document_path, output_path):
    if output_path.suffix.lower() == ".docx":
        document = load_contract_document(document_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        generate_docx(document, output_path)
        return []
    pdf, font_issues = render_document(load_document(document_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return font_issues


if __name__ == "__main__":
    raise SystemExit(run_command(main))
