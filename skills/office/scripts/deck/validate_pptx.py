#!/usr/bin/env python3
import argparse
import json

from skill_runtime import ensure_requirements


DEFAULT_FONT_NAMES = {"Aptos", "Calibri"}
EXCESSIVE_SHAPE_COUNT = 40


def summarize_presentation(presentation_path):
    if not ensure_requirements("office"):
        raise RuntimeError("pptx dependencies are unavailable after bootstrap")

    from pptx import Presentation

    presentation = Presentation(presentation_path)
    slides = []
    warnings = []
    for index, slide in enumerate(presentation.slides, start=1):
        slide_summary = summarize_slide(slide, index, presentation.slide_width, presentation.slide_height)
        slides.append(slide_summary)
        warnings.extend(f"slide {index}: {warning}" for warning in slide_summary["warnings"])
    return {
        "slideCount": len(presentation.slides),
        "slides": slides,
        "warnings": warnings,
        "passed": len(warnings) == 0,
        "validator": "python-pptx",
    }


def summarize_slide(slide, index, slide_width, slide_height):
    text_entries = text_entries_from_slide(slide)
    title = slide_title(slide, text_entries)
    shape_count = len(slide.shapes)
    explicit_default_fonts = sorted(default_fonts_from_entries(text_entries))
    inherited_font_runs = sum(entry["inheritedFontRuns"] for entry in text_entries)
    hybrid_summary = hybrid_slide_summary(slide)
    out_of_bounds_overlays = editable_overlays_out_of_bounds(slide, slide_width, slide_height)
    warnings = slide_warnings(title, text_entries, shape_count, explicit_default_fonts, inherited_font_runs, hybrid_summary, out_of_bounds_overlays)
    return {
        "index": index,
        "title": title,
        "shapeCount": shape_count,
        "textShapeCount": len(text_entries),
        "explicitDefaultFonts": explicit_default_fonts,
        "inheritedFontRuns": inherited_font_runs,
        "hybridBackgroundPresent": hybrid_summary["hasHybridBackground"],
        "editableOverlayCount": hybrid_summary["editableOverlayCount"],
        "outOfBoundsEditableOverlays": out_of_bounds_overlays,
        "warnings": warnings,
    }


def text_entries_from_slide(slide):
    entries = []
    for shape in slide.shapes:
        if not getattr(shape, "has_text_frame", False):
            continue
        text = shape.text.strip()
        font_names = []
        inherited_font_runs = 0
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                font_name = run.font.name
                if font_name:
                    font_names.append(font_name)
                elif run.text.strip():
                    inherited_font_runs += 1
        if text:
            entries.append({
                "text": text,
                "top": int(getattr(shape, "top", 0) or 0),
                "fontNames": font_names,
                "inheritedFontRuns": inherited_font_runs,
            })
    return entries


def slide_title(slide, text_entries):
    if slide.shapes.title and slide.shapes.title.text.strip():
        return slide.shapes.title.text.strip()
    if not text_entries:
        return ""
    first_entry = sorted(text_entries, key=lambda entry: entry["top"])[0]
    return first_entry["text"].splitlines()[0].strip()


def default_fonts_from_entries(text_entries):
    fonts = set()
    for entry in text_entries:
        for font_name in entry["fontNames"]:
            if font_name in DEFAULT_FONT_NAMES:
                fonts.add(font_name)
    return fonts


def hybrid_slide_summary(slide):
    return {
        "hasHybridBackground": any(getattr(shape, "name", "") == "Hybrid Background" for shape in slide.shapes),
        "editableOverlayCount": sum(1 for shape in slide.shapes if getattr(shape, "name", "") == "Editable Overlay"),
    }


def editable_overlays_out_of_bounds(slide, slide_width, slide_height):
    indexes = []
    for index, shape in enumerate(slide.shapes, start=1):
        if getattr(shape, "name", "") != "Editable Overlay":
            continue
        if shape.left < 0 or shape.top < 0 or shape.left + shape.width > slide_width or shape.top + shape.height > slide_height:
            indexes.append(index)
    return indexes


def slide_warnings(title, text_entries, shape_count, explicit_default_fonts, inherited_font_runs, hybrid_summary, out_of_bounds_overlays):
    warnings = []
    if not text_entries:
        warnings.append("slide appears empty")
    if not title:
        warnings.append("slide is missing a title")
    if shape_count > EXCESSIVE_SHAPE_COUNT:
        warnings.append(f"slide has excessive shape count ({shape_count})")
    if explicit_default_fonts:
        warnings.append("default font remains: " + ", ".join(explicit_default_fonts))
    if inherited_font_runs:
        warnings.append(f"{inherited_font_runs} text runs inherit the theme font")
    if hybrid_summary["editableOverlayCount"] and not hybrid_summary["hasHybridBackground"]:
        warnings.append("editable overlays are present without a hybrid background image")
    if out_of_bounds_overlays:
        warnings.append("editable overlay out of bounds: " + ", ".join(str(index) for index in out_of_bounds_overlays))
    return warnings


def parse_arguments():
    parser = argparse.ArgumentParser(description="Validate and summarize a PPTX deck.")
    parser.add_argument("presentation_path")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    summary = summarize_presentation(arguments.presentation_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
