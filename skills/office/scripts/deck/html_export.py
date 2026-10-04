from __future__ import annotations

from dataclasses import dataclass
import pathlib

from deck.review.acceptance import OBJECTIVE_DEFECT_CODES, judge_build
from deck.review.visual_review import write_visual_review
from deck.check_deck import CheckRequest, check_deck
from deck.deck_definitions import FONT_NOT_EMBEDDED, TEXT_KEPT_AS_PICTURE
from deck.deck_kit import KIT_MARKER, slide_size
from deck.deck_html import EXCLUDED_STYLES, SPEAKER_NOTES_HIDDEN_STYLE, deck_html_text
from deck.design_system import read_design_system
from pptx import Presentation

from powerpoint.chart_audit import presentation_chart_issues
from deck.pptx_export.editable import EditablePptx, read_text_layers, text_layers_path, write_editable_pptx
from deck.review.geometry_checks import GEOMETRY_FILE_NAME
from deck.layout_thresholds import renderer_thresholds
from core.office_result import Issue, OfficeFailure, Result
from render.renderer import PIXELS_FILE_NAME, RENDER_FAILED, RENDERER_UNAVAILABLE, RenderFailed, RendererUnavailable, RenderRequest, render_html, render_issues
from deck.review.evidence import clear_stale_render_evidence
from deck.review.deck_review import review_deck
from deck.slide_structure import extract_notes
from deck.source_preflight import read_checked_source
from schemas.known_values import load_runtime_context


BUILD_REVIEW_FACTS = ("slideCount", "renderedSlideCount")


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
    review: Result


def export_deck(request: ExportRequest) -> Result:
    source_text, slide_sources = read_checked_source(request.source_path)
    check = check_deck(request.check)
    if check.status == "error":
        return check
    remove_previous_outputs(request)
    html_output_path = request.output_path(".html")
    html_output_path.write_text(deck_html_text(request.source_path, read_design_system(request.source_path.parent / "DESIGN.md")[0]), encoding="utf-8")
    derived = write_derived_outputs(request, html_output_path, slide_sources)
    issues = list(check.issues) + derived.issues
    acceptance = judge_build(request.build_path, source_text, issues, deliverable_path(request))
    return Result(
        summary=f"{acceptance.verdict}. {build_summary(request, derived)}",
        output_path=deliverable_path(request),
        issues=tuple(issues),
        details=build_details(request, derived) | {"acceptance": acceptance.to_json()} | visual_review_details(request, issues),
    )


def visual_review_details(request: ExportRequest, issues: list[Issue]) -> dict[str, str]:
    context = load_runtime_context()
    if not context or not context.reviews_deck_renders:
        return {}
    return {"visualReview": str(write_visual_review(request.source_path, request.review_path, request.deck_name, issues, OBJECTIVE_DEFECT_CODES))}


def remove_previous_outputs(request: ExportRequest) -> None:
    request.build_path.mkdir(parents=True, exist_ok=True)
    for suffix in (".html", ".pptx", ".pdf"):
        request.output_path(suffix).unlink(missing_ok=True)


def deliverable_path(request: ExportRequest) -> str:
    for format_name, suffix in (("pptx", ".pptx"), ("pdf", ".pdf")):
        if format_name in request.formats and request.output_path(suffix).exists():
            return str(request.output_path(suffix))
    return str(request.output_path(".html"))


def write_derived_outputs(request: ExportRequest, html_output_path: pathlib.Path, slide_sources: list[str]) -> DerivedOutputs:
    issues = render_deck(request, html_output_path)
    pptx_details = None
    if "pptx" in request.formats:
        pptx_details, pptx_issues = write_pptx(request, [extract_notes(slide_source) for slide_source in slide_sources])
        issues.extend(pptx_issues)
    review = review_deck(request.source_path, request.deck_name, request.review_path, request.check.required_text)
    issues.extend(review.issues)
    return DerivedOutputs(issues, pptx_details, review)


def output_formats(requested: str) -> set[str]:
    return {requested, "html", "review", *(("pdf",) if requested == "pptx" else ())}


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
        excluded_styles=EXCLUDED_STYLES,
        extra_css=(SPEAKER_NOTES_HIDDEN_STYLE,),
    )


def render_deck(request: ExportRequest, html_output_path: pathlib.Path) -> list[Issue]:
    clear_stale_render_evidence(request.review_path, request.deck_name)
    try:
        rendered = render_html(deck_render_request(request, html_output_path))
    except RendererUnavailable as reason:
        html_output_path.unlink()
        raise OfficeFailure(RENDERER_UNAVAILABLE.issue(f"{request.deck_name} was not built: {reason}", str(request.source_path)))
    except RenderFailed as reason:
        clear_stale_render_evidence(request.review_path, request.deck_name)
        raise OfficeFailure(RENDER_FAILED.issue(f"{request.deck_name} was not built: {reason}", str(html_output_path)))
    return list(render_issues(rendered, str(html_output_path)))


def write_pptx(request: ExportRequest, notes: list[str]) -> tuple[dict, list[Issue]]:
    pptx_path = request.output_path(".pptx")
    layers_path = text_layers_path(request.review_path)
    layers = read_text_layers(request.review_path, len(notes))
    if layers is None:
        raise OfficeFailure(RENDER_FAILED.issue(f"{pptx_path.name} was not written: the renderer left no editable layer for each of the {len(notes)} slides", str(layers_path)))
    written = write_editable_pptx(layers, notes, pptx_path)
    return editable_pptx_details(written, layers_path), editable_pptx_issues(written, pptx_path) + presentation_chart_issues(Presentation(str(pptx_path)))


def editable_pptx_details(written: EditablePptx, layers_path: pathlib.Path) -> dict:
    return {
        "textBoxes": written.text_box_count,
        "shapes": written.shape_count,
        "connectors": written.connector_count,
        "charts": written.chart_count,
        "tables": written.table_count,
        "icons": written.icon_count,
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


def build_summary(request: ExportRequest, derived: DerivedOutputs) -> str:
    written = [name for name, path in output_paths(request, derived).items() if path]
    return f"built {', '.join(written)} into {request.build_path}; {derived.review.summary}"


def build_details(request: ExportRequest, derived: DerivedOutputs) -> dict:
    review = {field: derived.review.details[field] for field in BUILD_REVIEW_FACTS}
    return {"outputs": output_paths(request, derived), "pptx": derived.pptx, "review": review}


def output_paths(request: ExportRequest, derived: DerivedOutputs) -> dict[str, str | None]:
    candidates = {
        "html": request.output_path(".html"),
        "pdf": request.output_path(".pdf"),
        "pptx": request.output_path(".pptx"),
        "review": request.review_path / "slide-review.json",
    }
    return {
        name: str(path) if path.exists() else None
        for name, path in candidates.items()
        if name in request.formats
    }
