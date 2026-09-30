#!/usr/bin/env python3
from dataclasses import dataclass
import json
import os
import pathlib
import subprocess
import sys
import time

from browser_render import clear_stale_render_evidence, rendered_slide_image_paths, try_html_render, write_render_source
from image_pptx import write_image_backed_pptx
from native_pptx import write_native_text_pptx
from native_preview import write_native_review_images
from resource_inlining import inject_vendored_paperlogy_fallback, inline_local_fonts, inline_local_images
from slide_model import SlideModel, create_slide_models, extract_notes, extract_slide_sources, read_design_tokens
from slide_viewer import inject_screen_slide_viewer


ALLOWED_FORMATS = {"html", "pdf", "pptx", "notes", "review"}
USAGE = "Usage: html_export.py <source.html> <deck-name> <build-dir> <formats> <render-review-script> <html-render-script>"


@dataclass(frozen=True)
class ExportRequest:
    source_path: pathlib.Path
    deck_name: str
    build_path: pathlib.Path
    formats: set[str]
    render_review_script: pathlib.Path
    html_render_script: pathlib.Path

    @property
    def review_path(self) -> pathlib.Path:
        return self.build_path / "review"


def main() -> int:
    if len(sys.argv) != 7:
        print(USAGE, file=sys.stderr)
        return 2
    request = parse_export_request(sys.argv)
    validate_source(request.source_path)
    request.build_path.mkdir(parents=True, exist_ok=True)
    html_output_path = request.build_path / f"{request.deck_name}.html"
    html_output_path.write_text(deck_html_text(request.source_path), encoding="utf-8")
    slide_sources = extract_slide_sources(request.source_path)
    if not slide_sources:
        print("Error: slides.html must contain at least one <section> slide", file=sys.stderr)
        return 1
    write_derived_outputs(request, html_output_path, slide_sources)
    return 0


def parse_export_request(arguments: list[str]) -> ExportRequest:
    return ExportRequest(
        source_path=pathlib.Path(arguments[1]).resolve(),
        deck_name=arguments[2],
        build_path=pathlib.Path(arguments[3]).resolve(),
        formats=enabled_formats(arguments[4]),
        render_review_script=pathlib.Path(arguments[5]).resolve(),
        html_render_script=pathlib.Path(arguments[6]).resolve(),
    )


def write_derived_outputs(request: ExportRequest, html_output_path: pathlib.Path, slide_sources: list[str]) -> None:
    design = read_design_tokens(request.source_path.with_name("DESIGN.md"))
    slide_models = create_slide_models(slide_sources)
    slide_image_paths = render_slide_images(request, html_output_path, slide_models, design)
    pptx_output_mode = ""
    if "pptx" in request.formats:
        print_stage("pptx")
        pptx_output_mode = write_pptx(slide_models, design, slide_image_paths, request.build_path / f"{request.deck_name}.pptx")
    if "notes" in request.formats:
        print_stage("notes")
        write_notes(slide_sources, request.build_path / f"{request.deck_name}-notes.txt")
    if "review" in request.formats:
        print_stage("review")
        run_render_review(request.render_review_script, request.source_path, request.deck_name, request.review_path)
    print_outputs(request.build_path, request.deck_name, request.formats, pptx_output_mode)
    if "review" in request.formats:
        print_review_gate_summary(request.review_path)


def enabled_formats(raw_formats: str) -> set[str]:
    formats = {value.strip().casefold() for value in raw_formats.split(",") if value.strip()}
    if not formats:
        formats = {"html"}
    if "all" in formats:
        formats.remove("all")
        formats.update(ALLOWED_FORMATS)
    if "pptx" in formats:
        formats.update({"html", "pdf"})
    formats.update({"review", "html"})
    unknown_formats = sorted(formats - ALLOWED_FORMATS)
    if unknown_formats:
        raise SystemExit("Error: unknown presentation format(s): " + ", ".join(unknown_formats))
    return formats


def needs_rendered_slides(formats: set[str]) -> bool:
    if "pdf" in formats or "review" in formats:
        return True
    return "pptx" in formats and pptx_mode() == "image"


def pptx_mode() -> str:
    mode = os.environ.get("PRESENTATION_PPTX_MODE", "image").strip().casefold()
    if mode in {"image", "native"}:
        return mode
    return "image"


def validate_source(source_path: pathlib.Path) -> None:
    if not source_path.exists():
        raise SystemExit(f"Error: {source_path.name} not found. Create slides.html or set SRC=yourfile.html")
    if not source_path.with_name("DESIGN.md").exists():
        print("[warning] DESIGN.md not found; continuing with HTML source and native defaults", file=sys.stderr, flush=True)
    if "design-source: DESIGN.md" not in source_path.read_text(encoding="utf-8"):
        print(f"[warning] {source_path.name} does not include design-source: DESIGN.md", file=sys.stderr, flush=True)


def deck_html_text(source_path: pathlib.Path) -> str:
    source_text = source_path.read_text(encoding="utf-8")
    source_text = inject_vendored_paperlogy_fallback(source_text)
    source_text = inline_local_images(source_text, source_path.parent)
    source_text = inline_local_fonts(source_text, source_path.parent)
    return inject_screen_slide_viewer(source_text)


def render_slide_images(request: ExportRequest, html_output_path: pathlib.Path, slide_models: list[SlideModel], design: dict[str, str]) -> list[pathlib.Path]:
    if not needs_rendered_slides(request.formats):
        return []
    print_stage("render")
    clear_stale_render_evidence(request.review_path, request.deck_name)
    render_error = try_html_render(request.html_render_script, html_output_path, request.deck_name, request.build_path, request.formats)
    slide_image_paths = rendered_slide_image_paths(request.review_path, request.deck_name)
    if not render_error and slide_image_paths:
        write_render_source(request.review_path, "browser")
    if render_error and "review" in request.formats:
        write_native_fallback_review_images(slide_models, design, request)
    return slide_image_paths


def write_native_fallback_review_images(slide_models: list[SlideModel], design: dict[str, str], request: ExportRequest) -> None:
    if write_native_review_images(slide_models, design, request.review_path, request.deck_name):
        write_render_source(request.review_path, "nativeFallback")


def write_pptx(slide_models: list[SlideModel], design: dict[str, str], image_paths: list[pathlib.Path], pptx_path: pathlib.Path) -> str:
    if pptx_mode() == "image" and image_paths:
        write_image_backed_pptx(image_paths, pptx_path)
        return "image"
    if pptx_mode() == "image":
        print("[warning] image-backed PPTX requested, but rendered slide images are unavailable; writing native text-backed PPTX", file=sys.stderr, flush=True)
    write_native_text_pptx(slide_models, design, pptx_path)
    return "native"


def write_notes(slide_sources: list[str], notes_path: pathlib.Path) -> None:
    note_blocks = []
    for index, slide_source in enumerate(slide_sources, start=1):
        notes = extract_notes(slide_source)
        if notes:
            note_blocks.append(f"Slide {index}\n{notes}")
    notes_path.write_text("\n\n".join(note_blocks) + ("\n" if note_blocks else ""), encoding="utf-8")


def run_render_review(render_review_script: pathlib.Path, source_path: pathlib.Path, deck_name: str, review_path: pathlib.Path) -> None:
    if not render_review_script.exists():
        raise SystemExit("Error: render_review.py not found. Cannot review HTML-first deck.")
    result = subprocess.run([sys.executable, str(render_review_script), str(source_path), deck_name, str(review_path)])
    if result.returncode != 0:
        raise SystemExit(f"Error: slide render review failed; see {review_path / 'slide-review.json'}")


def print_stage(stage_name: str) -> None:
    print(f"[stage] {stage_name} {int(time.time())}", file=sys.stderr, flush=True)


def print_outputs(build_path: pathlib.Path, deck_name: str, formats: set[str], pptx_output_mode: str) -> None:
    print("")
    print("Done.")
    if "html" in formats:
        print(f"  {build_path.name}/{deck_name}.html            (HTML source rendered as deck)")
    if "pptx" in formats and pptx_output_mode == "image":
        print(f"  {build_path.name}/{deck_name}.pptx            (image-backed PowerPoint / Keynote)")
    elif "pptx" in formats:
        print(f"  {build_path.name}/{deck_name}.pptx            (native text-backed PowerPoint / Keynote fallback)")
    if "pdf" in formats and (build_path / f"{deck_name}.pdf").exists():
        print(f"  {build_path.name}/{deck_name}.pdf             (browser-rendered PDF)")
    elif "pdf" in formats:
        print(f"  {build_path.name}/{deck_name}.pdf             (not created; browser render unavailable)")
    if "notes" in formats:
        print(f"  {build_path.name}/{deck_name}-notes.txt       (speaker notes)")
    if "review" in formats:
        print(f"  {build_path.name}/review/slide-review.json (per-slide render review)")


def print_review_gate_summary(review_path: pathlib.Path) -> None:
    report_path = review_path / "slide-review.json"
    if not report_path.exists():
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    score = report.get("visualQualityScore", 0)
    minimum = report.get("visualQualityScoreMinimum", 0)
    if report.get("staticGatePassed"):
        print(f"Static design gate PASSED (visualQualityScore {score}/{minimum} minimum).")
        return
    print(f"Static design gate FAILED (visualQualityScore {score}, minimum {minimum}).")
    print("Revise slides.html to resolve these warnings, then rebuild before delivering:")
    for warning in report.get("designWarnings", []):
        print(f"  - {warning}")


if __name__ == "__main__":
    raise SystemExit(main())
