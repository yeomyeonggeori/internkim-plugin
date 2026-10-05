#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from core.office_arguments import route_arguments
from core.office_inputs import require_unlocked_pdf
from core.office_result import Issue, Result, run_command
from pdf.pdf_definitions import (
    KOREAN_FONT_MISSING,
    KOREAN_FONT_NOT_EMBEDDED,
    NO_FONT_RESOURCES,
    NO_TEXT_LAYER,
    PDF_ENCRYPTED,
    REQUIRED_FONT_MISSING,
    TEXT_TOO_SHORT,
    TOO_FEW_PAGES,
    TOO_MANY_PAGES,
)
from balance.issues import balance_details, balance_issues, is_schema_document
from balance.measure import measure_pdf
from core.text_checks import text_presence_issues
from core.text_script import has_hangul


KOREAN_CHARACTER_COLLECTION = "Korea1"


def main() -> Result:
    arguments = parse_arguments()
    require_unlocked_pdf(arguments.file, arguments.password)
    source_path = Path(arguments.file)
    reader = PdfReader(str(source_path), password=arguments.password)
    korean_fonts: list = []
    extracted_text = "\n".join(page_text(page, korean_fonts) for page in reader.pages)
    font_summary = summarize_fonts(reader)
    pages = measure_pdf(source_path, password=arguments.password)
    issues = (
        layer_issues(reader, extracted_text, arguments)
        + text_presence_issues(extracted_text, arguments.required_text, arguments.forbidden_text)
        + korean_font_issues(korean_fonts)
        + font_issues(font_summary, arguments.required_font)
        + (balance_issues(pages) if is_schema_document(source_path) else [])
    )
    details = {
        "isPDF": source_path.read_bytes()[:4] == b"%PDF",
        "pageCount": len(reader.pages),
        "pageSizes": collect_page_sizes(reader),
        "isEncrypted": bool(reader.is_encrypted),
        "extractedTextLength": len(extracted_text),
        "fonts": font_summary,
        **balance_details(pages),
    }
    return Result(summary=f"checked {source_path}: {len(issues)} issues", output_path=str(source_path), issues=tuple(issues), details=details)


def page_text(page, korean_fonts: list) -> str:
    def note_font(text, _matrix, _text_matrix, font, _size):
        if font is not None and has_hangul(text) and not any(font is known for known in korean_fonts):
            korean_fonts.append(font)

    return page.extract_text(visitor_text=note_font) or ""


def korean_font_issues(korean_fonts: list) -> list[Issue]:
    unembedded = [font for font in korean_fonts if not is_embedded_font(font)]
    undeclared = [font for font in unembedded if not declares_korean(font)]
    if undeclared:
        return [KOREAN_FONT_MISSING.issue(f"Korean text is drawn with {font_names(undeclared)}, which the PDF neither embeds nor declares as Korean", font_names(undeclared))]
    if unembedded:
        return [KOREAN_FONT_NOT_EMBEDDED.issue(f"Korean text is drawn with {font_names(unembedded)}, which the PDF does not embed", font_names(unembedded))]
    return []


def font_names(fonts: list) -> str:
    return ", ".join(dict.fromkeys(clean_pdf_name(font.get("/BaseFont")) for font in fonts))


def declares_korean(font) -> bool:
    descendants = dereference(font.get("/DescendantFonts")) or []
    for descendant in descendants:
        system = dereference(dereference(descendant).get("/CIDSystemInfo"))
        if system is not None and str(system.get("/Ordering")) == KOREAN_CHARACTER_COLLECTION:
            return True
    return False


def collect_page_sizes(reader) -> list[dict]:
    return [
        {"widthPoints": round(float(page.mediabox.width), 2), "heightPoints": round(float(page.mediabox.height), 2)}
        for page in reader.pages
    ]


def summarize_fonts(reader) -> dict:
    fonts = [font for page_index, page in enumerate(reader.pages, start=1) for font in page_fonts(page, page_index)]
    return {
        "count": len(fonts),
        "baseFonts": sorted({font["baseFont"] for font in fonts if font["baseFont"]}),
        "embeddedCount": sum(1 for font in fonts if font["isEmbedded"]),
        "resources": fonts,
    }


def page_fonts(page, page_index: int) -> list[dict]:
    resources = dereference(page.get("/Resources"))
    font_resources = dereference(resources.get("/Font")) if resources else None
    if not font_resources:
        return []
    fonts = []
    for resource_name, raw_font in font_resources.items():
        font = dereference(raw_font)
        if not font:
            continue
        fonts.append({
            "page": page_index,
            "resourceName": str(resource_name),
            "baseFont": clean_pdf_name(font.get("/BaseFont")),
            "subtype": clean_pdf_name(font.get("/Subtype")),
            "isEmbedded": is_embedded_font(font),
        })
    return fonts


def dereference(value):
    if value is None:
        return None
    if hasattr(value, "get_object"):
        return value.get_object()
    return value


def clean_pdf_name(value) -> str:
    if value is None:
        return ""
    return str(value).lstrip("/")


def is_embedded_font(font) -> bool:
    descriptor = dereference(font.get("/FontDescriptor"))
    if descriptor and font_descriptor_has_font_file(descriptor):
        return True
    descendants = dereference(font.get("/DescendantFonts"))
    if not isinstance(descendants, list):
        return False
    for descendant in descendants:
        descendant_font = dereference(descendant)
        descendant_descriptor = dereference(descendant_font.get("/FontDescriptor")) if descendant_font else None
        if descendant_descriptor and font_descriptor_has_font_file(descendant_descriptor):
            return True
    return False


def font_descriptor_has_font_file(descriptor) -> bool:
    return any(descriptor.get(name) is not None for name in ["/FontFile", "/FontFile2", "/FontFile3"])


def layer_issues(reader, extracted_text: str, arguments) -> list[Issue]:
    issues = []
    page_count = len(reader.pages)
    if reader.is_encrypted:
        issues.append(PDF_ENCRYPTED.issue("PDF is encrypted"))
    if not extracted_text.strip():
        issues.append(NO_TEXT_LAYER.issue("PDF has no extractable text layer"))
    if arguments.minimum_text_length and len(extracted_text) < arguments.minimum_text_length:
        issues.append(TEXT_TOO_SHORT.issue(f"PDF has {len(extracted_text)} extracted text characters, below the expected minimum {arguments.minimum_text_length}"))
    if arguments.minimum_pages and page_count < arguments.minimum_pages:
        issues.append(TOO_FEW_PAGES.issue(f"PDF has {page_count} pages, below the expected minimum {arguments.minimum_pages}"))
    if arguments.maximum_pages and page_count > arguments.maximum_pages:
        issues.append(TOO_MANY_PAGES.issue(f"PDF has {page_count} pages, above the expected maximum {arguments.maximum_pages}"))
    return issues


def font_issues(font_summary: dict, required_font: str | None) -> list[Issue]:
    issues = []
    if required_font and not any(required_font.lower() in name.lower() for name in font_summary["baseFonts"]):
        issues.append(REQUIRED_FONT_MISSING.issue("PDF does not use a font containing: " + required_font))
    if font_summary["count"] == 0:
        issues.append(NO_FONT_RESOURCES.issue("PDF has no inspectable font resources"))
    return issues


def parse_arguments():
    return route_arguments("check", "pdf")


if __name__ == "__main__":
    raise SystemExit(run_command(main))
