#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import json
import pathlib
import subprocess
import sys
import time

from acceptance import judge_build
from browser_render import clear_stale_render_evidence, try_html_render, write_render_source
from check_deck import CheckRequest, add_check_arguments, check_deck, check_request
from deck_definitions import BROWSER_RENDER_UNAVAILABLE, FONT_NOT_EMBEDDED, PPTX_WITHOUT_DESIGN, REVIEW_FAILED, REVIEW_ISSUE_KINDS, TEXT_KEPT_AS_PICTURE, UNKNOWN_FORMAT
from deck_kit import inject_deck_kit
from design_tokens import read_design_tokens
from editable_pptx import EditablePptx, read_text_layers, text_layers_path, write_editable_pptx
from native_pptx import write_native_text_pptx
from native_preview import write_native_review_images
from office_result import INPUT_NOT_FOUND, INVALID_ARGUMENTS, Issue, OfficeArgumentParser, OfficeFailure, Result, issue_from_json, run_command
from resource_inlining import inject_vendored_paperlogy_fallback, inline_local_fonts, inline_local_images
from slide_images import rendered_slide_image_paths
from slide_model import SlideModel, create_slide_models, extract_notes
from slide_source import read_optional_text
from slide_viewer import inject_screen_slide_viewer
from source_preflight import read_checked_source


ALLOWED_FORMATS = {"html", "pdf", "pptx", "notes", "review"}
BUILD_REVIEW_FACTS = ("renderSource", "slideCount", "renderedSlideCount", "geometryMeasured", "visualEvidenceReliable")
USAGE = "usage: html_export.py <source.html> <deck-name> <build-dir> <formats> <render-review-script> <html-render-script> [--slide-count N] [--required-text TEXT ...]"
POSITIONAL_ARGUMENT_COUNT = 7


@dataclass(frozen=True)
class ExportRequest:
    source_path: pathlib.Path
    deck_name: str
    build_path: pathlib.Path
    formats: set[str]
    render_review_script: pathlib.Path
    html_render_script: pathlib.Path
    check: CheckRequest

    @property
    def review_path(self) -> pathlib.Path:
        return self.build_path / "review"

    def output_path(self, suffix: str) -> pathlib.Path:
        return self.build_path / f"{self.deck_name}{suffix}"


@dataclass(frozen=True)
class DerivedOutputs:
    issues: list[Issue]
    pptx: dict | None
    review: Result | None


def main() -> Result:
    if len(sys.argv) < POSITIONAL_ARGUMENT_COUNT:
        raise OfficeFailure(INVALID_ARGUMENTS.issue(USAGE))
    request = parse_export_request(sys.argv)
    source_text, slide_sources = read_checked_source(request.source_path)
    check = check_deck(request.check)
    if check.status == "error":
        return check
    request.build_path.mkdir(parents=True, exist_ok=True)
    html_output_path = request.output_path(".html")
    html_output_path.write_text(deck_html_text(request.source_path), encoding="utf-8")
    derived = write_derived_outputs(request, html_output_path, slide_sources)
    issues = list(check.issues) + derived.issues
    acceptance = judge_build(request.build_path, source_text, issues, deliverable_path(request), render_was_measured(derived))
    return Result(
        summary=f"{acceptance.verdict}. {build_summary(request, derived)}",
        output_path=deliverable_path(request),
        issues=tuple(issues),
        details=build_details(request, derived) | {"acceptance": acceptance.to_json()},
    )


def parse_export_request(arguments: list[str]) -> ExportRequest:
    source_path = pathlib.Path(arguments[1]).resolve()
    return ExportRequest(
        source_path=source_path,
        deck_name=arguments[2],
        build_path=pathlib.Path(arguments[3]).resolve(),
        formats=enabled_formats(arguments[4]),
        render_review_script=pathlib.Path(arguments[5]).resolve(),
        html_render_script=pathlib.Path(arguments[6]).resolve(),
        check=check_options(source_path, arguments[POSITIONAL_ARGUMENT_COUNT:]),
    )


def check_options(source_path: pathlib.Path, arguments: list[str]) -> CheckRequest:
    parser = OfficeArgumentParser(prog="html_export.py")
    add_check_arguments(parser)
    return check_request(source_path, parser.parse_args(arguments))


def deliverable_path(request: ExportRequest) -> str:
    for format_name, suffix in (("pptx", ".pptx"), ("pdf", ".pdf")):
        if format_name in request.formats and request.output_path(suffix).exists():
            return str(request.output_path(suffix))
    return str(request.output_path(".html"))


def render_was_measured(derived: DerivedOutputs) -> bool:
    return derived.review is not None and bool(derived.review.details.get("geometryMeasured"))


def write_derived_outputs(request: ExportRequest, html_output_path: pathlib.Path, slide_sources: list[str]) -> DerivedOutputs:
    design = read_design_tokens(read_optional_text(request.source_path.with_name("DESIGN.md")))
    slide_models = create_slide_models(slide_sources)
    issues = render_slide_images(request, html_output_path, slide_models, design)
    pptx_details = None
    if "pptx" in request.formats:
        print_stage("pptx")
        pptx_details, pptx_issues = write_pptx(request, slide_models, design)
        issues.extend(pptx_issues)
    if "notes" in request.formats:
        print_stage("notes")
        write_notes(slide_sources, request.output_path("-notes.txt"))
    review = None
    if "review" in request.formats:
        print_stage("review")
        review = run_render_review(request.render_review_script, request.source_path, request.deck_name, request.review_path)
        issues.extend(review.issues)
    return DerivedOutputs(issues, pptx_details, review)


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
        raise OfficeFailure(UNKNOWN_FORMAT.issue("unknown presentation format(s): " + ", ".join(unknown_formats)))
    return formats


def deck_html_text(source_path: pathlib.Path) -> str:
    source_text = inject_deck_kit(source_path.read_text(encoding="utf-8"))
    source_text = inject_vendored_paperlogy_fallback(source_text)
    source_text = inline_local_images(source_text, source_path.parent)
    source_text = inline_local_fonts(source_text, source_path.parent)
    return inject_screen_slide_viewer(source_text)


def render_slide_images(request: ExportRequest, html_output_path: pathlib.Path, slide_models: list[SlideModel], design: dict[str, str]) -> list[Issue]:
    print_stage("render")
    clear_stale_render_evidence(request.review_path, request.deck_name)
    render_error = try_html_render(request.html_render_script, html_output_path, request.deck_name, request.build_path, request.formats)
    slide_image_paths = rendered_slide_image_paths(request.review_path, request.deck_name)
    if not render_error and slide_image_paths:
        write_render_source(request.review_path, "browser")
    if not render_error:
        return []
    write_native_fallback_review_images(slide_models, design, request)
    return [BROWSER_RENDER_UNAVAILABLE.issue(f"{render_error}; continued with browserless outputs")]


def write_native_fallback_review_images(slide_models: list[SlideModel], design: dict[str, str], request: ExportRequest) -> None:
    if write_native_review_images(slide_models, design, request.review_path, request.deck_name):
        write_render_source(request.review_path, "nativeFallback")


def write_pptx(request: ExportRequest, slide_models: list[SlideModel], design: dict[str, str]) -> tuple[dict, list[Issue]]:
    pptx_path = request.output_path(".pptx")
    layers = read_text_layers(request.review_path, len(slide_models))
    if layers is None:
        write_native_text_pptx(slide_models, design, pptx_path)
        return {"source": "slideText"}, [PPTX_WITHOUT_DESIGN.issue("no browser rendered the deck; the PPTX holds the slide text in stock layouts", str(pptx_path))]
    written = write_editable_pptx(layers, [model.notes for model in slide_models], pptx_path)
    return editable_pptx_details(written, text_layers_path(request.review_path)), editable_pptx_issues(written, pptx_path)


def editable_pptx_details(written: EditablePptx, layers_path: pathlib.Path) -> dict:
    return {
        "source": "browser",
        "textBoxes": written.text_box_count,
        "shapes": written.shape_count,
        "boxesKeptAsPicture": written.boxes_kept_as_picture,
        "embeddedFonts": list(written.embedded_typefaces),
        "unembeddedFonts": list(written.unembedded_families),
        "textKeptAsPicture": list(written.picture_texts),
        "layers": str(layers_path),
    }


def editable_pptx_issues(written: EditablePptx, pptx_path: pathlib.Path) -> list[Issue]:
    issues = []
    if written.unembedded_families:
        issues.append(FONT_NOT_EMBEDDED.issue("not embedded: " + ", ".join(written.unembedded_families), str(pptx_path)))
    if written.picture_texts:
        issues.append(TEXT_KEPT_AS_PICTURE.issue("kept as picture: " + " / ".join(written.picture_texts), str(pptx_path)))
    return issues


def write_notes(slide_sources: list[str], notes_path: pathlib.Path) -> None:
    note_blocks = []
    for index, slide_source in enumerate(slide_sources, start=1):
        notes = extract_notes(slide_source)
        if notes:
            note_blocks.append(f"Slide {index}\n{notes}")
    notes_path.write_text("\n\n".join(note_blocks) + ("\n" if note_blocks else ""), encoding="utf-8")


def run_render_review(render_review_script: pathlib.Path, source_path: pathlib.Path, deck_name: str, review_path: pathlib.Path) -> Result:
    if not render_review_script.exists():
        raise OfficeFailure(INPUT_NOT_FOUND.issue(f"{render_review_script} not found; cannot review the deck", str(render_review_script)))
    completed = subprocess.run(
        [sys.executable, str(render_review_script), str(source_path), deck_name, str(review_path)],
        stdout=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise OfficeFailure(REVIEW_FAILED.issue(f"slide render review failed with exit code {completed.returncode}: {completed.stdout.strip()[-400:]}", str(review_path)))
    envelope = json.loads(completed.stdout)
    return Result(
        summary=envelope["summary"],
        output_path=envelope["outputPath"],
        issues=tuple(issue_from_json(document, REVIEW_ISSUE_KINDS) for document in envelope["issues"]),
        details=envelope["details"],
    )


def print_stage(stage_name: str) -> None:
    print(f"[stage] {stage_name} {int(time.time())}", file=sys.stderr, flush=True)


def build_summary(request: ExportRequest, derived: DerivedOutputs) -> str:
    written = [name for name, path in output_paths(request, derived).items() if path]
    summary = f"built {', '.join(written)} into {request.build_path}"
    if derived.review is None:
        return summary
    return f"{summary}; {derived.review.summary}"


def build_details(request: ExportRequest, derived: DerivedOutputs) -> dict:
    details = {"outputs": output_paths(request, derived), "pptx": derived.pptx}
    if derived.review is not None:
        details["review"] = {field: derived.review.details[field] for field in BUILD_REVIEW_FACTS}
    return details


def output_paths(request: ExportRequest, derived: DerivedOutputs) -> dict[str, str | None]:
    candidates = {
        "html": request.output_path(".html"),
        "pdf": request.output_path(".pdf"),
        "pptx": request.output_path(".pptx"),
        "notes": request.output_path("-notes.txt"),
        "review": request.review_path / "slide-review.json",
    }
    return {
        name: str(path) if path.exists() else None
        for name, path in candidates.items()
        if name in request.formats
    }


if __name__ == "__main__":
    raise SystemExit(run_command(main))
