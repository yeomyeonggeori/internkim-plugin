from __future__ import annotations

from dataclasses import dataclass
import pathlib

from deck.acceptance import judge_build
from deck.check_deck import CheckRequest, check_deck
from deck.deck_definitions import FONT_NOT_EMBEDDED, LAYOUT_RENDER_SOURCE, NATIVE_RENDER_SOURCE, PPTX_WITHOUT_DESIGN, TEXT_KEPT_AS_PICTURE, UNKNOWN_FORMAT
from deck.deck_kit import KIT_MARKER, inject_deck_kit, slide_size
from deck.design_tokens import read_design_tokens
from deck.editable_pptx import EditablePptx, read_text_layers, text_layers_path, write_editable_pptx
from deck.geometry_checks import GEOMETRY_FILE_NAME
from deck.layout_thresholds import renderer_thresholds
from deck.native_pptx import write_native_text_pptx
from deck.native_preview import write_native_review_images
from core.office_result import Issue, OfficeFailure, Result
from render.renderer import PIXELS_FILE_NAME, RENDER_FAILED, RENDERER_UNAVAILABLE, RenderFailed, RendererUnavailable, RenderRequest, render_html, render_issues
from deck.render_evidence import clear_stale_render_evidence, write_render_source
from deck.render_review import review_deck
from deck.resource_inlining import VENDORED_FONTS_MARKER, inject_vendored_paperlogy_fallback, inline_local_fonts, inline_local_images
from deck.slide_model import SlideModel, create_slide_models, extract_notes
from deck.slide_source import SPEAKER_NOTES_CLASS, read_optional_text
from deck.slide_viewer import SLIDE_VIEWER_MARKER, inject_screen_slide_viewer
from deck.source_preflight import read_checked_source


ALLOWED_FORMATS = {"html", "pdf", "pptx", "notes", "review"}
BUILD_REVIEW_FACTS = ("renderSource", "slideCount", "renderedSlideCount", "geometryMeasured", "visualEvidenceReliable")
SPEAKER_NOTES_HIDDEN_STYLE = f"section .{SPEAKER_NOTES_CLASS} {{ display: none !important; }}"


@dataclass(frozen=True)
class ExportRequest:
    source_path: pathlib.Path
    deck_name: str
    build_path: pathlib.Path
    formats: set[str]
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


def export_deck(request: ExportRequest) -> Result:
    source_text, slide_sources = read_checked_source(request.source_path)
    check = check_deck(request.check)
    if check.status == "error":
        return check
    remove_previous_outputs(request)
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


def remove_previous_outputs(request: ExportRequest) -> None:
    request.build_path.mkdir(parents=True, exist_ok=True)
    for suffix in (".html", ".pptx", ".pdf", "-notes.txt"):
        request.output_path(suffix).unlink(missing_ok=True)


def deliverable_path(request: ExportRequest) -> str:
    for format_name, suffix in (("pptx", ".pptx"), ("pdf", ".pdf")):
        if format_name in request.formats and request.output_path(suffix).exists():
            return str(request.output_path(suffix))
    return str(request.output_path(".html"))


def render_was_measured(derived: DerivedOutputs) -> bool:
    if derived.review is None:
        return False
    return derived.review.details.get("renderSource") == LAYOUT_RENDER_SOURCE and bool(derived.review.details.get("geometryMeasured"))


def write_derived_outputs(request: ExportRequest, html_output_path: pathlib.Path, slide_sources: list[str]) -> DerivedOutputs:
    design = read_design_tokens(read_optional_text(request.source_path.with_name("DESIGN.md")))
    slide_models = create_slide_models(slide_sources)
    issues = render_deck(request, html_output_path, slide_models, design)
    pptx_details = None
    if "pptx" in request.formats:
        pptx_details, pptx_issues = write_pptx(request, slide_models, design)
        issues.extend(pptx_issues)
    if "notes" in request.formats:
        write_notes(slide_sources, request.output_path("-notes.txt"))
    review = review_deck(request.source_path, request.deck_name, request.review_path, request.check.required_text)
    issues.extend(review.issues)
    return DerivedOutputs(issues, pptx_details, review)


def enabled_formats(raw_formats: str) -> set[str]:
    formats = {value.strip().casefold() for value in raw_formats.split(",") if value.strip()}
    if "all" in formats:
        formats.remove("all")
        formats.update(ALLOWED_FORMATS)
    if "pptx" in formats:
        formats.add("pdf")
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


def deck_render_request(request: ExportRequest, html_output_path: pathlib.Path) -> RenderRequest:
    return RenderRequest(
        html_path=html_output_path,
        page_selector="section",
        png_directory=request.review_path,
        png_prefix=request.deck_name,
        pdf_path=request.output_path(".pdf") if "pdf" in request.formats else None,
        viewport=slide_size(),
        geometry_path=request.review_path / GEOMETRY_FILE_NAME,
        geometry_thresholds=renderer_thresholds(),
        layers_directory=text_layers_path(request.review_path) if "pptx" in request.formats else None,
        pixels_path=request.review_path / PIXELS_FILE_NAME,
        contact_sheet_directory=request.review_path,
        script_selector=f"script[{KIT_MARKER}]",
        excluded_styles=f"style[{SLIDE_VIEWER_MARKER}], style[{VENDORED_FONTS_MARKER}]",
        extra_css=(SPEAKER_NOTES_HIDDEN_STYLE,),
    )


def render_deck(request: ExportRequest, html_output_path: pathlib.Path, slide_models: list[SlideModel], design: dict[str, str]) -> list[Issue]:
    clear_stale_render_evidence(request.review_path, request.deck_name)
    try:
        rendered = render_html(deck_render_request(request, html_output_path))
    except RendererUnavailable as reason:
        write_native_fallback_review_images(slide_models, design, request)
        return [RENDERER_UNAVAILABLE.issue(f"{reason}; the slide text was laid out without the deck's design")]
    except RenderFailed as reason:
        clear_stale_render_evidence(request.review_path, request.deck_name)
        write_native_fallback_review_images(slide_models, design, request)
        return [RENDER_FAILED.issue(str(reason), str(html_output_path))]
    write_render_source(request.review_path, LAYOUT_RENDER_SOURCE)
    return list(render_issues(rendered, str(html_output_path)))


def write_native_fallback_review_images(slide_models: list[SlideModel], design: dict[str, str], request: ExportRequest) -> None:
    if write_native_review_images(slide_models, design, request.review_path, request.deck_name):
        write_render_source(request.review_path, NATIVE_RENDER_SOURCE)


def write_pptx(request: ExportRequest, slide_models: list[SlideModel], design: dict[str, str]) -> tuple[dict, list[Issue]]:
    pptx_path = request.output_path(".pptx")
    layers = read_text_layers(request.review_path, len(slide_models))
    if layers is None:
        write_native_text_pptx(slide_models, design, pptx_path)
        return {"source": "slideText"}, [PPTX_WITHOUT_DESIGN.issue("no renderer drew the deck; the PPTX holds the slide text in stock layouts", str(pptx_path))]
    written = write_editable_pptx(layers, [model.notes for model in slide_models], pptx_path)
    return editable_pptx_details(written, text_layers_path(request.review_path)), editable_pptx_issues(written, pptx_path)


def editable_pptx_details(written: EditablePptx, layers_path: pathlib.Path) -> dict:
    return {
        "source": LAYOUT_RENDER_SOURCE,
        "textBoxes": written.text_box_count,
        "shapes": written.shape_count,
        "connectors": written.connector_count,
        "charts": written.chart_count,
        "tables": written.table_count,
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
