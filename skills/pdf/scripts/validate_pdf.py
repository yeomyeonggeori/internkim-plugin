#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from skill_runtime import ensure_requirements


def summarize_pdf(pdf_path, min_pages, max_pages, minimum_text_length, required_text, forbidden_text, required_font_substring):
    if not ensure_requirements("pdf"):
        raise RuntimeError("pdf dependencies are unavailable after bootstrap")

    from pypdf import PdfReader

    source_path = Path(pdf_path)
    reader = PdfReader(str(source_path))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    extracted_text = "\n".join(page_texts)
    required_missing = [value for value in required_text if value not in extracted_text]
    forbidden_present = [value for value in forbidden_text if value in extracted_text]
    font_summary = summarize_fonts(reader)
    warnings = collect_warnings(
        reader,
        extracted_text,
        min_pages,
        max_pages,
        minimum_text_length,
        required_missing,
        forbidden_present,
        font_summary,
        required_font_substring,
    )
    return {
        "isPDF": source_path.read_bytes()[:4] == b"%PDF",
        "pageCount": len(reader.pages),
        "pageSizes": collect_page_sizes(reader),
        "isEncrypted": bool(reader.is_encrypted),
        "extractedTextLength": len(extracted_text),
        "requiredMissing": required_missing,
        "forbiddenPresent": forbidden_present,
        "fonts": font_summary,
        "warnings": warnings,
        "warningCount": len(warnings),
    }


def collect_page_sizes(reader):
    page_sizes = []
    for page in reader.pages:
        media_box = page.mediabox
        page_sizes.append({
            "widthPoints": round(float(media_box.width), 2),
            "heightPoints": round(float(media_box.height), 2),
        })
    return page_sizes


def summarize_fonts(reader):
    fonts = []
    for page_index, page in enumerate(reader.pages, start=1):
        resources = dereference(page.get("/Resources"))
        if not resources:
            continue
        font_resources = dereference(resources.get("/Font"))
        if not font_resources:
            continue
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
    base_fonts = sorted({font["baseFont"] for font in fonts if font["baseFont"]})
    return {
        "count": len(fonts),
        "baseFonts": base_fonts,
        "embeddedCount": sum(1 for font in fonts if font["isEmbedded"]),
        "resources": fonts,
    }


def dereference(value):
    if value is None:
        return None
    if hasattr(value, "get_object"):
        return value.get_object()
    return value


def clean_pdf_name(value):
    if value is None:
        return ""
    return str(value).lstrip("/")


def is_embedded_font(font):
    descriptor = dereference(font.get("/FontDescriptor"))
    if descriptor and font_descriptor_has_font_file(descriptor):
        return True
    descendants = dereference(font.get("/DescendantFonts"))
    if isinstance(descendants, list):
        for descendant in descendants:
            descendant_font = dereference(descendant)
            if not descendant_font:
                continue
            descendant_descriptor = dereference(descendant_font.get("/FontDescriptor"))
            if descendant_descriptor and font_descriptor_has_font_file(descendant_descriptor):
                return True
    return False


def font_descriptor_has_font_file(descriptor):
    return any(descriptor.get(name) is not None for name in ["/FontFile", "/FontFile2", "/FontFile3"])


def collect_warnings(
    reader,
    extracted_text,
    min_pages,
    max_pages,
    minimum_text_length,
    required_missing,
    forbidden_present,
    font_summary,
    required_font_substring,
):
    warnings = []
    if reader.is_encrypted:
        warnings.append("PDF is encrypted")
    if not extracted_text.strip():
        warnings.append("PDF has no extractable text layer")
    if minimum_text_length > 0 and len(extracted_text) < minimum_text_length:
        warnings.append(f"PDF has {len(extracted_text)} extracted text characters, below the expected minimum {minimum_text_length}")
    if min_pages > 0 and len(reader.pages) < min_pages:
        warnings.append(f"PDF has {len(reader.pages)} pages, below the expected minimum {min_pages}")
    if max_pages > 0 and len(reader.pages) > max_pages:
        warnings.append(f"PDF has {len(reader.pages)} pages, above the expected maximum {max_pages}")
    if required_missing:
        warnings.append("PDF is missing required text: " + ", ".join(required_missing[:8]))
    if forbidden_present:
        warnings.append("PDF includes forbidden unsupported text: " + ", ".join(forbidden_present[:8]))
    if contains_korean(extracted_text) and not has_korean_capable_font(font_summary["baseFonts"]):
        warnings.append("PDF contains Korean text but no Korean-capable font name was detected")
    if required_font_substring and not font_summary_contains(font_summary, required_font_substring):
        warnings.append("PDF does not use a font containing: " + required_font_substring)
    if font_summary["count"] == 0:
        warnings.append("PDF has no inspectable font resources")
    if font_summary["count"] > 0 and font_summary["embeddedCount"] == 0 and contains_korean(extracted_text):
        warnings.append("PDF contains Korean text but no embedded font resources were detected")
    return warnings


def contains_korean(text):
    return any("\uac00" <= character <= "\ud7a3" for character in text)


def has_korean_capable_font(font_names):
    candidates = ["noto", "nanum", "malgun", "apple sd", "applegothic", "arialunicode", "arial unicode", "gothic", "myeongjo", "cjk", "kr"]
    normalized_names = " ".join(font_name.lower() for font_name in font_names)
    return any(candidate in normalized_names for candidate in candidates)


def font_summary_contains(font_summary, required_font_substring):
    normalized_required_value = required_font_substring.lower()
    return any(normalized_required_value in font_name.lower() for font_name in font_summary["baseFonts"])


def parse_arguments():
    parser = argparse.ArgumentParser(description="Validate a PDF document.")
    parser.add_argument("pdf_path")
    parser.add_argument("--min-pages", type=int, default=0)
    parser.add_argument("--max-pages", type=int, default=0)
    parser.add_argument("--minimum-text-length", type=int, default=0)
    parser.add_argument("--required-text", action="append", default=[])
    parser.add_argument("--forbidden-text", action="append", default=[])
    parser.add_argument("--required-font-substring", default="")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    summary = summarize_pdf(
        arguments.pdf_path,
        arguments.min_pages,
        arguments.max_pages,
        arguments.minimum_text_length,
        arguments.required_text,
        arguments.forbidden_text,
        arguments.required_font_substring,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
