from __future__ import annotations

import json
import pathlib
import re
import tempfile

from core.design_rules import deck_rule_issues, render_rule_issues
from core.office_result import WARNING, Issue, IssueKind, OfficeFailure
from deck.deck_kit import KIT_MARKER, inject_deck_kit, slide_size
from deck.deck_photos import focus_photos
from deck.deck_preparation import kit_additions, prepare_deck
from deck.design_system import DesignSystem
from deck.layout_thresholds import gate_thresholds
from deck.resource_inlining import VENDORED_FONTS_MARKER, inject_vendored_paperlogy_fallback, inline_local_fonts, inline_local_images
from deck.slide_source import SPEAKER_NOTES_CLASS
from deck.slide_viewer import SLIDE_VIEWER_MARKER, inject_screen_slide_viewer
from render.renderer import RENDER_FAILED, RENDERER_UNAVAILABLE, RenderFailed, RendererUnavailable, RenderRequest, render_html


RENDER_GATE_SKIPPED = IssueKind("RENDER_GATE_SKIPPED", WARNING, "the renderer is not available, so the slides were not measured against the render rules", "run office setup, then check again; a build needs the renderer anyway")
SPEAKER_NOTES_HIDDEN_STYLE = f"section .{SPEAKER_NOTES_CLASS} {{ display: none !important; }}"
EXCLUDED_STYLES = f"style[{SLIDE_VIEWER_MARKER}], style[{VENDORED_FONTS_MARKER}]"
GATE_GEOMETRY_FILE = "geometry.json"
GATE_HTML_FILE = "gate.html"


FONT_DECLARATION = re.compile(r"(?<![-\w])font(?:-family)?\s*:\s*(?:[^;}\"'<>]|(?<=[:,\s])(?:\"[^\"<>]*\"|'[^'<>]*'))*;?", re.I)


FONT_FACE_BLOCK = re.compile(r"@font-face\s*\{[^}]*\}", re.I)


def without_font_choices(source_text: str) -> str:
    kept, position = [], 0
    for block in FONT_FACE_BLOCK.finditer(source_text):
        kept.append(FONT_DECLARATION.sub("", source_text[position:block.start()]))
        kept.append(block.group(0))
        position = block.end()
    kept.append(FONT_DECLARATION.sub("", source_text[position:]))
    return "".join(kept)


def kit_html_text(source_path: pathlib.Path, system: DesignSystem | None) -> str:
    source_text = without_font_choices(source_path.read_text(encoding="utf-8"))
    source_text = inject_deck_kit(source_text, kit_additions(prepare_deck(), system))
    source_text = inject_vendored_paperlogy_fallback(source_text)
    source_text = inline_local_images(focus_photos(source_text, source_path.parent), source_path.parent)
    return inline_local_fonts(source_text, source_path.parent)


def deck_html_text(source_path: pathlib.Path, system: DesignSystem | None) -> str:
    return inject_screen_slide_viewer(kit_html_text(source_path, system))


def render_gate_issues(source_path: pathlib.Path, system: DesignSystem | None) -> list[Issue]:
    try:
        slides = measure_for_gate(source_path, system)
    except OfficeFailure as failure:
        if any(issue.kind is RENDERER_UNAVAILABLE for issue in failure.issues):
            return [RENDER_GATE_SKIPPED.issue(str(failure), str(source_path))]
        raise
    per_slide = [issue for number, slide in enumerate(slides, start=1) for issue in render_rule_issues(slide.get("designFindings", []), f"slide {number}")]
    return per_slide + deck_rule_issues([slide.get("designFindings", []) for slide in slides])


def measure_for_gate(source_path: pathlib.Path, system: DesignSystem | None) -> list[dict]:
    with tempfile.TemporaryDirectory() as scratch:
        html_path = pathlib.Path(scratch) / GATE_HTML_FILE
        geometry_path = pathlib.Path(scratch) / GATE_GEOMETRY_FILE
        html_path.write_text(kit_html_text(source_path, system), encoding="utf-8")
        draw_for_gate(source_path, html_path, geometry_path)
        return json.loads(geometry_path.read_text(encoding="utf-8"))["slides"]


def draw_for_gate(source_path: pathlib.Path, html_path: pathlib.Path, geometry_path: pathlib.Path) -> None:
    request = RenderRequest(
        html_path=html_path,
        page_selector="section",
        viewport=slide_size(),
        geometry_path=geometry_path,
        geometry_thresholds=gate_thresholds(),
        script_selector=f"script[{KIT_MARKER}]",
        excluded_styles=EXCLUDED_STYLES,
        extra_css=(SPEAKER_NOTES_HIDDEN_STYLE,),
    )
    try:
        render_html(request)
    except RendererUnavailable as reason:
        raise OfficeFailure(RENDERER_UNAVAILABLE.issue(f"{source_path.name} was not checked: {reason}", str(source_path)))
    except RenderFailed as reason:
        raise OfficeFailure(RENDER_FAILED.issue(f"{source_path.name} was not checked: {reason}", str(source_path)))
