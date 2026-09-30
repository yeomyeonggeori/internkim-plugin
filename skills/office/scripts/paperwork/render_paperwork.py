#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

from skill_runtime import cache_home_path, ensure_requirements
from paperwork_design import (
    COLOR_BORDER,
    COLOR_HEADER_FILL,
    COLOR_INK,
    COLOR_MUTED,
    COLOR_RULE,
    FONT_CANDIDATE_PATHS_PDF,
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


ALLOWED_TOP_LEVEL_KEYS = {
    "title", "documentNumber", "profile", "approvalLine", "recipient",
    "meta", "items", "sections", "notes", "signature", "footer", "fontPath",
}
CONTENT_KEYS = {"recipient", "meta", "items", "sections", "notes", "signature"}
SPEC_HINT = "read the document type's spec at this skill's references/paperwork/<ko|en>/<type>.md and copy its Document JSON skeleton exactly"


def load_document(document_path):
    with open(document_path, "r", encoding="utf-8") as document_file:
        document = json.load(document_file)
    if not isinstance(document, dict):
        raise ValueError("document must be a JSON object")
    normalize_document(document)
    validate_document(document)
    return document


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


def validate_document(document):
    problems = []
    if not str(document.get("title", "")).strip():
        problems.append("document.title is required")
    unknown_keys = set(document) - ALLOWED_TOP_LEVEL_KEYS
    if unknown_keys:
        problems.append(f"unknown document fields {sorted(unknown_keys)}; allowed fields are {sorted(ALLOWED_TOP_LEVEL_KEYS - {'fontPath'})}")
    if not any(key in document for key in CONTENT_KEYS):
        problems.append(f"document has no content blocks ({sorted(CONTENT_KEYS)} all missing)")
    items = document.get("items")
    if items is not None and (not isinstance(items, dict) or not isinstance(items.get("headers"), list) or not isinstance(items.get("rows"), list)):
        problems.append("items must be an object with headers[], rows[][], optional aligns[] and totals[]")
    totals = items.get("totals") if isinstance(items, dict) else None
    if totals is not None and (not isinstance(totals, list) or any(not isinstance(row, dict) for row in totals)):
        problems.append('items.totals must be an ARRAY of objects like [{"label": "공급가액 합계", "value": "12,000,000원"}, {"label": "부가세(10%)", "value": "1,200,000원"}, {"label": "총 합계", "value": "13,200,000원"}]')
    meta = document.get("meta")
    if meta is not None and (not isinstance(meta, list) or any(not isinstance(row, dict) for row in meta)):
        problems.append("meta must be an array of {label, value} objects")
    sections = document.get("sections")
    if sections is not None and (not isinstance(sections, list) or any(not isinstance(section, dict) for section in sections)):
        problems.append("sections must be an array of {title, paragraphs, bullets} objects")
    signature = document.get("signature")
    if signature is not None and not isinstance(signature, dict):
        problems.append('signature must be an object like {"date": "2026년 7월 7일", "line": "주식회사 던 대표이사 이샘플", "stamp": true}')
    recipient = document.get("recipient")
    if recipient is not None and (not isinstance(recipient, dict) or not isinstance(recipient.get("lines", []), list)):
        problems.append("recipient must be an object {label, lines[]}")
    notes = document.get("notes")
    if notes is not None and not isinstance(notes, list):
        problems.append("notes must be an array of strings")
    if problems:
        raise ValueError("fix ALL of these in document.json, then rerun: " + " | ".join(problems) + f" — {SPEC_HINT}")


def resolve_font(document):
    configured_path = str(document.get("fontPath", "")).strip()
    if configured_path:
        return Path(configured_path)
    for candidate in candidate_font_paths():
        if candidate.exists() and is_embeddable_font(candidate):
            return candidate
    raise ValueError("no Korean-capable font found; pass fontPath in the document JSON")


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


def candidate_font_paths():
    return cached_font_paths() + [Path(candidate) for candidate in FONT_CANDIDATE_PATHS_PDF]


def cached_font_paths():
    fonts_directory = cache_home_path(os.environ) / "fonts"
    return [fonts_directory / "NanumGothic.ttf", fonts_directory / "NotoSansKR-Regular.ttf"]


def render_document(document):
    if not ensure_requirements("office"):
        raise RuntimeError("paperwork dependencies are unavailable after bootstrap")

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

    pdf = PaperworkPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(PAGE_MARGIN_MILLIMETERS, PAGE_MARGIN_MILLIMETERS, PAGE_MARGIN_MILLIMETERS)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_font("Paperwork", fname=str(resolve_font(document)))
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
    return pdf


def content_width(pdf):
    return pdf.w - pdf.l_margin - pdf.r_margin


def set_body_font(pdf, size=10.0, color=INK_COLOR):
    pdf.set_font("Paperwork", size=size)
    pdf.set_text_color(*color)


def company_display_name(profile):
    if not isinstance(profile, dict):
        return ""
    return str(profile.get("name", "") or profile.get("companyName", "")).strip()


def add_letterhead(pdf, profile):
    if not company_display_name(profile):
        raise ValueError("profile.name is required — insert the company_info_get result into profile")
    top_y = pdf.get_y()
    logo_path = str(profile.get("logoPath", "")).strip()
    if logo_path and Path(logo_path).exists():
        pdf.image(logo_path, x=pdf.l_margin, y=top_y, h=LETTERHEAD_LOGO_HEIGHT)
    set_body_font(pdf, size=SIZE_LETTERHEAD_NAME, color=HEADING_COLOR)
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
    if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
        raise ValueError("approvalLine must be an array of strings")
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
    set_body_font(pdf, size=SIZE_TITLE + 3, color=HEADING_COLOR)
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
        set_body_font(pdf, size=9, color=HEADING_COLOR)
        pdf.set_xy(pdf.l_margin, row_y)
        pdf.cell(META_LABEL_WIDTH, row_height, label, align="C")
        set_body_font(pdf, size=9)
        draw_wrapped_lines(pdf, pdf.l_margin + META_LABEL_WIDTH, row_y, value_width, value_lines, "L")
        pdf.set_xy(pdf.l_margin, row_y + row_height)
    pdf.ln(4)


def add_item_table(pdf, items):
    if not isinstance(items, dict):
        return
    headers = items.get("headers", [])
    rows = items.get("rows", [])
    if not headers:
        raise ValueError("items.headers must be a non-empty array")
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
    set_body_font(pdf, size=9, color=HEADING_COLOR if is_header else INK_COLOR)
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
        set_body_font(pdf, size=11 if is_final_total else 9.5, color=HEADING_COLOR if is_final_total else INK_COLOR)
        pdf.cell(0, 7 if is_final_total else 5.5, f"{label}    {value}", align="R", new_x="LMARGIN", new_y="NEXT")


def add_sections(pdf, sections):
    for section in sections:
        title = str(section.get("title", "")).strip()
        if title:
            set_body_font(pdf, size=11, color=HEADING_COLOR)
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
    set_body_font(pdf, size=10.5, color=HEADING_COLOR)
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
    set_body_font(pdf, size=12, color=HEADING_COLOR)
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


DOCX_ALLOWED_KEYS = {"title", "fontName", "fontSize", "page", "blocks"}
DOCX_HINT = 'a .docx document JSON must look like {"title": "...", "fontName": "맑은 고딕", "blocks": [{"type": "heading", "level": 2, "text": "제1조 (목적)"}, {"type": "paragraph", "text": "..."}, {"type": "bullets", "items": ["..."]}, {"type": "table", "rows": [["...", "..."]]}]} — copy the spec\'s DOCX blocks skeleton'


def load_docx_document(document_path):
    with open(document_path, "r", encoding="utf-8") as document_file:
        document = json.load(document_file)
    if not isinstance(document, dict):
        raise ValueError(f"document must be a JSON object; {DOCX_HINT}")
    unknown_keys = set(document) - DOCX_ALLOWED_KEYS
    if unknown_keys:
        raise ValueError(f"unknown document fields {sorted(unknown_keys)}; {DOCX_HINT}")
    blocks = document.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError(f"document has no content: blocks must be a non-empty array; {DOCX_HINT}")
    page = document.get("page")
    if page is not None and not isinstance(page, dict):
        raise ValueError('page must be an object like {"marginInches": 0.9} or omitted; ' + DOCX_HINT)
    return document


def generate_docx(document, output_path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt, RGBColor

    word_document = Document()
    section = word_document.sections[0]
    margin_inches = float((document.get("page") or {}).get("marginInches", 0.9))
    section.top_margin = section.bottom_margin = Inches(margin_inches)
    section.left_margin = section.right_margin = Inches(margin_inches)
    font_name = str(document.get("fontName", FONT_KOREAN_DOCX))
    font_size = float(document.get("fontSize", SIZE_BODY))
    style = word_document.styles["Normal"]
    style.font.name = font_name
    style.font.size = Pt(font_size)
    style.font.color.rgb = RGBColor(*COLOR_INK)
    style.paragraph_format.line_spacing = LINE_SPACING
    style.element.rPr.rFonts.set(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia", font_name)
    title = str(document.get("title", "")).strip()
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
    word_document.save(str(output_path))


def append_docx_block(word_document, block):
    from docx.shared import Pt, RGBColor

    if not isinstance(block, dict):
        raise ValueError(f"each block must be an object; {DOCX_HINT}")
    block_type = str(block.get("type", "")).strip()
    if block_type == "heading":
        paragraph = word_document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(10)
        paragraph.paragraph_format.space_after = Pt(2)
        run = paragraph.add_run(str(block.get("text", "")))
        run.bold = True
        run.font.size = Pt(SIZE_CLAUSE_HEADING)
        run.font.color.rgb = RGBColor(*COLOR_INK)
    elif block_type == "paragraph":
        word_document.add_paragraph(str(block.get("text", "")))
    elif block_type == "bullets":
        for item in block.get("items", []):
            word_document.add_paragraph(str(item), style="List Bullet")
    elif block_type == "table":
        rows = block.get("rows", [])
        if not rows or not isinstance(rows[0], list):
            raise ValueError(f"table.rows must be a non-empty array of row arrays; {DOCX_HINT}")
        table = word_document.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = "Table Grid"
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                if column_index < len(table.rows[row_index].cells):
                    table.rows[row_index].cells[column_index].text = "" if value is None else str(value)
    else:
        raise ValueError(f"unknown block type {block_type!r}; {DOCX_HINT}")


def main():
    parser = argparse.ArgumentParser(description="Render a paperwork document JSON to a letterhead PDF or a DOCX contract.")
    parser.add_argument("document_path", help="Path to the document JSON file")
    parser.add_argument("output_path", help="Path to the output .pdf or .docx file")
    arguments = parser.parse_args()
    output_path = Path(os.path.expanduser(arguments.output_path))
    is_docx = output_path.suffix.lower() == ".docx"
    try:
        if is_docx:
            if not ensure_requirements("office"):
                raise RuntimeError("paperwork dependencies are unavailable after bootstrap")
            document = load_docx_document(os.path.expanduser(arguments.document_path))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            generate_docx(document, output_path)
            print(output_path)
            return
        document = load_document(os.path.expanduser(arguments.document_path))
        pdf = render_document(document)
    except FileNotFoundError:
        print(f"paperwork renderer error: document JSON not found at {arguments.document_path}; write it with write first, following the spec's skeleton", file=sys.stderr)
        raise SystemExit(1)
    except PermissionError:
        print(f"paperwork renderer error: cannot write to {output_path} (permission denied); rerun the SAME command with the output changed to ~/documents/{output_path.parent.name}/{output_path.name}", file=sys.stderr)
        raise SystemExit(1)
    except (ValueError, json.JSONDecodeError) as validation_error:
        print(f"paperwork renderer error: {validation_error}", file=sys.stderr)
        raise SystemExit(1)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(output_path))
    except PermissionError:
        print(f"paperwork renderer error: cannot write to {output_path} (permission denied); rerun the SAME command with the output changed to ~/documents/{output_path.parent.name}/{output_path.name}", file=sys.stderr)
        raise SystemExit(1)
    print(output_path)


if __name__ == "__main__":
    main()
