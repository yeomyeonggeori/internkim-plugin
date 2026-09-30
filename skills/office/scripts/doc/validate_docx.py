#!/usr/bin/env python3
import argparse
import json
import re

from skill_runtime import ensure_requirements


def summarize_document(document_path, required_text, forbidden_text):
    if not ensure_requirements("office"):
        raise RuntimeError("docx dependencies are unavailable after bootstrap")

    from docx import Document

    document = Document(document_path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    table_texts = [cell.text for table in document.tables for row in table.rows for cell in row.cells if cell.text.strip()]
    visible_text = "\n".join(paragraphs + table_texts)
    required_missing = [value for value in required_text if value not in visible_text]
    forbidden_present = [value for value in forbidden_text if value in visible_text]
    heading_count = sum(1 for paragraph in document.paragraphs if paragraph.style and paragraph.style.name.startswith("Heading"))
    tables = []
    for table in document.tables:
        empty_cell_count = sum(1 for row in table.rows for cell in row.cells if not cell.text.strip())
        dense_cell_count = sum(1 for row in table.rows for cell in row.cells if len(cell.text.strip()) > 90)
        tables.append({
            "rows": len(table.rows),
            "columns": len(table.columns),
            "emptyCellCount": empty_cell_count,
            "denseCellCount": dense_cell_count,
        })
    typography = collect_typography(document, visible_text)
    warnings = collect_warnings(paragraphs, tables, required_missing, forbidden_present, typography)
    return {
        "paragraphCount": len(paragraphs),
        "headingCount": heading_count,
        "tableCount": len(document.tables),
        "tables": tables,
        "firstParagraphs": paragraphs[:5],
        "visibleTextLength": len(visible_text),
        "requiredMissing": required_missing,
        "forbiddenPresent": forbidden_present,
        "typography": typography,
        "warnings": warnings,
        "warningCount": len(warnings),
    }


def collect_typography(document, visible_text):
    normal_style = document.styles["Normal"] if "Normal" in document.styles else None
    sections = [section_metrics(section) for section in document.sections]
    paragraph_metrics = [metrics_for_paragraph(paragraph) for paragraph in document.paragraphs if paragraph.text.strip()]
    font_names = sorted({font_name for font_name in collect_font_names(document) if font_name})
    font_sizes = sorted({size for size in collect_font_sizes(document, normal_style) if size is not None})
    line_spacings = sorted({metric["lineSpacing"] for metric in paragraph_metrics if metric["lineSpacing"] is not None})
    return {
        "hasKoreanText": bool(re.search(r"[\uac00-\ud7a3]", visible_text)),
        "fontNames": font_names,
        "fontSizePoints": font_sizes,
        "normalFontSizePoints": point_value(normal_style.font.size) if normal_style is not None else None,
        "normalLineSpacing": line_spacing_value(normal_style.paragraph_format.line_spacing) if normal_style is not None else None,
        "paragraphLineSpacings": line_spacings,
        "sections": sections,
    }


def section_metrics(section):
    return {
        "pageWidthInches": inch_value(section.page_width),
        "pageHeightInches": inch_value(section.page_height),
        "topMarginInches": inch_value(section.top_margin),
        "rightMarginInches": inch_value(section.right_margin),
        "bottomMarginInches": inch_value(section.bottom_margin),
        "leftMarginInches": inch_value(section.left_margin),
    }


def metrics_for_paragraph(paragraph):
    return {
        "style": paragraph.style.name if paragraph.style else "",
        "lineSpacing": line_spacing_value(paragraph.paragraph_format.line_spacing),
        "spaceAfterPoints": point_value(paragraph.paragraph_format.space_after),
    }


def collect_font_names(document):
    font_names = []
    for style in document.styles:
        font_names.extend(font_names_for_element(style.element))
        style_font = getattr(style, "font", None)
        if style_font is not None and style_font.name:
            font_names.append(style_font.name)
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            if run.font.name:
                font_names.append(run.font.name)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        if run.font.name:
                            font_names.append(run.font.name)
    return font_names


def font_names_for_element(element):
    from docx.oxml.ns import qn

    run_properties = element.rPr
    if run_properties is None or run_properties.rFonts is None:
        return []
    names = []
    for attribute_name in ["w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"]:
        value = run_properties.rFonts.get(qn(attribute_name))
        if value:
            names.append(value)
    return names


def collect_font_sizes(document, normal_style):
    sizes = []
    if normal_style is not None and getattr(normal_style, "font", None) is not None:
        sizes.append(point_value(normal_style.font.size))
    for paragraph in document.paragraphs:
        if paragraph.style is not None and getattr(paragraph.style, "font", None) is not None:
            sizes.append(point_value(paragraph.style.font.size))
        for run in paragraph.runs:
            sizes.append(point_value(run.font.size))
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        sizes.append(point_value(run.font.size))
    return sizes


def point_value(value):
    if value is None:
        return None
    return round(value.pt, 2)


def inch_value(value):
    if value is None:
        return None
    return round(value.inches, 3)


def line_spacing_value(value):
    if value is None:
        return None
    if hasattr(value, "pt"):
        return round(value.pt, 2)
    try:
        return round(float(value), 2)
    except TypeError:
        return None


def collect_warnings(paragraphs, tables, required_missing, forbidden_present, typography):
    warnings = []
    if not paragraphs:
        warnings.append("document has no visible paragraph text")
    if len(paragraphs) < 3:
        warnings.append("document has very little visible text")
    if required_missing:
        warnings.append("document is missing required source text: " + ", ".join(required_missing[:8]))
    if forbidden_present:
        warnings.append("document includes forbidden unsupported text: " + ", ".join(forbidden_present[:8]))
    if typography["hasKoreanText"] and not has_korean_capable_font(typography["fontNames"]):
        warnings.append("document contains Korean text but no Korean-capable font name was detected")
    if typography["normalFontSizePoints"] is not None and not 9.0 <= typography["normalFontSizePoints"] <= 12.5:
        warnings.append(f"normal text size is {typography['normalFontSizePoints']} pt; expected about 10-11 pt for business documents")
    if typography["normalLineSpacing"] is not None and not 1.0 <= typography["normalLineSpacing"] <= 1.25:
        warnings.append(f"normal line spacing is {typography['normalLineSpacing']}; expected about 1.05-1.2")
    for index, section in enumerate(typography["sections"], start=1):
        margins = [
            section["topMarginInches"],
            section["rightMarginInches"],
            section["bottomMarginInches"],
            section["leftMarginInches"],
        ]
        if any(value is not None and value < 0.5 for value in margins):
            warnings.append(f"section {index} has a margin under 0.5 inches")
        if any(value is not None and value > 1.25 for value in margins):
            warnings.append(f"section {index} has a margin above 1.25 inches")
    if not any(table["rows"] > 1 for table in tables):
        warnings.append("document has no multi-row table for structured facts")
    for index, table in enumerate(tables, start=1):
        if table["columns"] > 5:
            warnings.append(f"table {index} has more than 5 columns and may be too wide")
        if table["emptyCellCount"] > 0:
            warnings.append(f"table {index} has {table['emptyCellCount']} empty cells")
        if table["denseCellCount"] > 0:
            warnings.append(f"table {index} has {table['denseCellCount']} dense cells that may need wrapping or shorter labels")
    return warnings


def has_korean_capable_font(font_names):
    candidates = ["noto", "nanum", "malgun", "apple sd", "gothic", "myeongjo", "cjk", "kr", "맑은", "고딕"]
    normalized_names = " ".join(font_name.lower() for font_name in font_names)
    return any(candidate in normalized_names for candidate in candidates)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Validate and summarize a DOCX file.")
    parser.add_argument("document_path")
    parser.add_argument("--required-text", action="append", default=[])
    parser.add_argument("--forbidden-text", action="append", default=[])
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    summary = summarize_document(arguments.document_path, arguments.required_text, arguments.forbidden_text)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
