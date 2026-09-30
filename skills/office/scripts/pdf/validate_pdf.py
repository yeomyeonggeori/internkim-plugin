#!/usr/bin/env python3
from pathlib import Path

from pypdf import PdfReader

from office_result import Issue, OfficeArgumentParser, Result, run_command
from pdf_definitions import (
    KOREAN_FONT_NOT_EMBEDDED,
    NO_FONT_RESOURCES,
    NO_TEXT_LAYER,
    PDF_ENCRYPTED,
    REQUIRED_FONT_MISSING,
    TEXT_TOO_SHORT,
    TOO_FEW_PAGES,
    TOO_MANY_PAGES,
)
from text_checks import contains_korean, korean_font_issues, text_presence_issues


def main() -> Result:
    arguments = parse_arguments()
    source_path = Path(arguments.pdf_path)
    reader = PdfReader(str(source_path))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    font_summary = summarize_fonts(reader)
    issues = (
        layer_issues(reader, extracted_text, arguments)
        + text_presence_issues(extracted_text, arguments.required_text, arguments.forbidden_text)
        + korean_font_issues(extracted_text, font_summary["baseFonts"])
        + font_issues(font_summary, extracted_text, arguments.required_font_substring)
    )
    details = {
        "isPDF": source_path.read_bytes()[:4] == b"%PDF",
        "pageCount": len(reader.pages),
        "pageSizes": collect_page_sizes(reader),
        "isEncrypted": bool(reader.is_encrypted),
        "extractedTextLength": len(extracted_text),
        "fonts": font_summary,
    }
    return Result(summary=f"checked {source_path}: {len(issues)} issues", output_path=str(source_path), issues=tuple(issues), details=details)


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
    if arguments.minimum_text_length > 0 and len(extracted_text) < arguments.minimum_text_length:
        issues.append(TEXT_TOO_SHORT.issue(f"PDF has {len(extracted_text)} extracted text characters, below the expected minimum {arguments.minimum_text_length}"))
    if arguments.min_pages > 0 and page_count < arguments.min_pages:
        issues.append(TOO_FEW_PAGES.issue(f"PDF has {page_count} pages, below the expected minimum {arguments.min_pages}"))
    if arguments.max_pages > 0 and page_count > arguments.max_pages:
        issues.append(TOO_MANY_PAGES.issue(f"PDF has {page_count} pages, above the expected maximum {arguments.max_pages}"))
    return issues


def font_issues(font_summary: dict, extracted_text: str, required_font_substring: str) -> list[Issue]:
    issues = []
    if required_font_substring and not any(required_font_substring.lower() in name.lower() for name in font_summary["baseFonts"]):
        issues.append(REQUIRED_FONT_MISSING.issue("PDF does not use a font containing: " + required_font_substring))
    if font_summary["count"] == 0:
        issues.append(NO_FONT_RESOURCES.issue("PDF has no inspectable font resources"))
    if font_summary["count"] > 0 and font_summary["embeddedCount"] == 0 and contains_korean(extracted_text):
        issues.append(KOREAN_FONT_NOT_EMBEDDED.issue("PDF contains Korean text but no embedded font resources were detected"))
    return issues


def parse_arguments():
    parser = OfficeArgumentParser(description="Validate a PDF document.")
    parser.add_argument("pdf_path")
    parser.add_argument("--min-pages", type=int, default=0)
    parser.add_argument("--max-pages", type=int, default=0)
    parser.add_argument("--minimum-text-length", type=int, default=0)
    parser.add_argument("--required-text", action="append", default=[])
    parser.add_argument("--forbidden-text", action="append", default=[])
    parser.add_argument("--required-font-substring", default="")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
