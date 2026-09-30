#!/usr/bin/env python3
import base64
from dataclasses import dataclass
import html
import json
import mimetypes
import os
import pathlib
import re
import subprocess
import sys
import time
import zipfile


SLIDE_WIDTH = 1600
SLIDE_HEIGHT = 900
PRESENTATION_WIDTH_EMU = 12192000
PRESENTATION_HEIGHT_EMU = 6858000
SLIDE_MASTER_RELATIONSHIP_ID = 2147483648
DEFAULT_NATIVE_COLORS = {
    "background": "F8FAFC",
    "surface": "FFFFFF",
    "ink": "111827",
    "muted": "64748B",
    "accent": "0F766E",
    "line": "CBD5E1",
}
SLIDE_VIEWER_BLOCK_PATTERNS = (
    r"\s*<style\b(?=[^>]*\bdata-internkim-slide-viewer\b)[^>]*>.*?</style>\s*",
    r"\s*<script\b(?=[^>]*\bdata-internkim-slide-viewer\b)[^>]*>.*?</script>\s*",
)


@dataclass(frozen=True)
class SlideModel:
    index: int
    source: str
    title: str
    lines: list[str]
    tables: list[list[list[str]]]
    list_items: list[str]
    kind: str


def main() -> int:
    if len(sys.argv) != 7:
        print("Usage: html_export.py <source.html> <deck-name> <build-dir> <formats> <render-review-script> <html-render-script>", file=sys.stderr)
        return 2
    source_path = pathlib.Path(sys.argv[1]).resolve()
    deck_name = sys.argv[2]
    build_path = pathlib.Path(sys.argv[3]).resolve()
    formats = enabled_formats(sys.argv[4])
    render_review_script = pathlib.Path(sys.argv[5]).resolve()
    html_render_script = pathlib.Path(sys.argv[6]).resolve()
    validate_source(source_path)
    build_path.mkdir(parents=True, exist_ok=True)
    html_output_path = build_path / f"{deck_name}.html"
    html_output_path.write_text(inline_local_resources(source_path), encoding="utf-8")
    slide_sources = extract_slide_sources(source_path)
    if not slide_sources:
        print("Error: slides.html must contain at least one <section> slide", file=sys.stderr)
        return 1
    design = read_design_tokens(source_path.with_name("DESIGN.md"))
    slide_models = create_slide_models(slide_sources)
    slide_image_paths = []
    render_error = ""
    if needs_rendered_slides(formats):
        print(f"[stage] render {int(time.time())}", file=sys.stderr, flush=True)
        clear_stale_render_evidence(build_path / "review", deck_name)
        render_error = try_html_render(html_render_script, html_output_path, deck_name, build_path, formats)
        slide_image_paths = sorted((build_path / "review").glob(f"{deck_name}.[0-9][0-9][0-9].png"))
        if not render_error and slide_image_paths:
            write_render_source(build_path / "review", "browser")
    if render_error and "review" in formats:
        if write_native_review_images(slide_models, design, build_path / "review", deck_name):
            write_render_source(build_path / "review", "nativeFallback")
    if "pptx" in formats:
        print(f"[stage] pptx {int(time.time())}", file=sys.stderr, flush=True)
        pptx_output_mode = write_pptx(slide_models, design, slide_image_paths, build_path / f"{deck_name}.pptx")
    else:
        pptx_output_mode = ""
    if "notes" in formats:
        print(f"[stage] notes {int(time.time())}", file=sys.stderr, flush=True)
        write_notes(slide_sources, build_path / f"{deck_name}-notes.txt")
    if "review" in formats:
        print(f"[stage] review {int(time.time())}", file=sys.stderr, flush=True)
        run_render_review(render_review_script, source_path, deck_name, build_path / "review")
    print_outputs(build_path, deck_name, formats, pptx_output_mode)
    if "review" in formats:
        print_review_gate_summary(build_path / "review")
    return 0


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


def enabled_formats(raw_formats: str) -> set[str]:
    formats = {value.strip().casefold() for value in raw_formats.split(",") if value.strip()}
    if not formats:
        formats = {"html"}
    if "all" in formats:
        formats.remove("all")
        formats.update({"html", "pdf", "pptx", "notes", "review"})
    if "pptx" in formats:
        formats.update({"html", "pdf"})
    formats.update({"review", "html"})
    allowed_formats = {"html", "pdf", "pptx", "notes", "review"}
    unknown_formats = sorted(formats - allowed_formats)
    if unknown_formats:
        raise SystemExit("Error: unknown presentation format(s): " + ", ".join(unknown_formats))
    return formats


def needs_rendered_slides(formats: set[str]) -> bool:
    if "pdf" in formats or "review" in formats:
        return True
    return "pptx" in formats and pptx_mode() == "image"


def validate_source(source_path: pathlib.Path) -> None:
    if not source_path.exists():
        raise SystemExit(f"Error: {source_path.name} not found. Create slides.html or set SRC=yourfile.html")
    design_path = source_path.with_name("DESIGN.md")
    if not design_path.exists():
        print("[warning] DESIGN.md not found; continuing with HTML source and native defaults", file=sys.stderr, flush=True)
    source_text = source_path.read_text(encoding="utf-8")
    if "design-source: DESIGN.md" not in source_text:
        print(f"[warning] {source_path.name} does not include design-source: DESIGN.md", file=sys.stderr, flush=True)


def extract_slide_sources(source_path: pathlib.Path) -> list[str]:
    source_text = source_path.read_text(encoding="utf-8")
    sections = re.findall(r"<section\b[^>]*>.*?</section>", source_text, flags=re.IGNORECASE | re.DOTALL)
    return [section.strip() for section in sections if section.strip()]


def inline_local_resources(source_path: pathlib.Path) -> str:
    source_text = source_path.read_text(encoding="utf-8")
    source_text = inject_vendored_paperlogy_fallback(source_text)
    source_text = inline_local_images(source_text, source_path.parent)
    source_text = inline_local_fonts(source_text, source_path.parent)
    return inject_screen_slide_viewer(source_text)


def inject_vendored_paperlogy_fallback(source_text: str) -> str:
    source_text = add_paperlogy_local_to_font_family_lists(source_text)
    font_style = vendored_paperlogy_fallback_style()
    if "data-internkim-vendored-fonts" in source_text:
        return re.sub(
            r"<style\b[^>]*data-internkim-vendored-fonts[^>]*>.*?</style>",
            font_style,
            source_text,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
    style_match = re.search(r"<style\b[^>]*>", source_text, flags=re.IGNORECASE)
    if style_match:
        insert_index = style_match.start()
        return source_text[:insert_index] + "\n" + font_style + "\n" + source_text[insert_index:]
    head_match = re.search(r"</head>", source_text, flags=re.IGNORECASE)
    if head_match:
        insert_index = head_match.start()
        return source_text[:insert_index] + "<style>\n" + font_style + "\n</style>\n" + source_text[insert_index:]
    return "<style>\n" + font_style + "\n</style>\n" + source_text


def add_paperlogy_local_to_font_family_lists(source_text: str) -> str:
    if "PaperlogyLocal" in source_text:
        return source_text
    source_text = re.sub(
        r'(["\']Paperlogy["\']\s*,)(?!\s*["\']PaperlogyLocal["\'])',
        r'\1 "PaperlogyLocal",',
        source_text,
    )
    return re.sub(
        r'(?<![-\w])Paperlogy\s*,(?!\s*["\']?PaperlogyLocal)',
        'Paperlogy, "PaperlogyLocal",',
        source_text,
    )


def vendored_paperlogy_fallback_style() -> str:
    fonts = [
        (400, "Paperlogy-4Regular.woff2"),
        (600, "Paperlogy-6SemiBold.woff2"),
        (700, "Paperlogy-7Bold.woff2"),
        (800, "Paperlogy-8ExtraBold.woff2"),
    ]
    rules = []
    for weight, file_name in fonts:
        font_path = pathlib.Path(__file__).resolve().parent.parent / "assets" / "fonts" / "paperlogy" / file_name
        rules.append(
            '@font-face { font-family: "PaperlogyLocal"; '
            f"font-weight: {weight}; font-style: normal; font-display: swap; "
            f'src: url("{base64_data_url("font/woff2", font_path)}") format("woff2"); }}'
        )
    return '<style data-internkim-vendored-fonts>' + "\n".join(rules) + "</style>"


def strip_screen_slide_viewer(source_text: str) -> str:
    stripped_text = source_text
    for block_pattern in SLIDE_VIEWER_BLOCK_PATTERNS:
        stripped_text = re.sub(block_pattern, "", stripped_text, flags=re.IGNORECASE | re.DOTALL)
    return stripped_text


def inject_screen_slide_viewer(source_text: str) -> str:
    source_text = strip_screen_slide_viewer(source_text)
    viewer_style = """
<style data-internkim-slide-viewer>
section aside.notes, section aside[role="note"], section [data-speaker-notes] { display: none !important; }
@media screen {
  html { background: #000; }
  body { min-height: 100vh; margin: 0; background: #000; }
  body:not(.internkim-deck-ready) { padding: 32px; display: grid; gap: 32px; justify-items: center; align-content: start; }
  body:not(.internkim-deck-ready) section { width: 1600px; height: 900px; max-width: calc(100vw - 64px); max-height: calc((100vw - 64px) * 0.5625); aspect-ratio: 16 / 9; box-shadow: 0 24px 80px rgba(15, 23, 42, 0.28); }
  body.internkim-deck-ready { width: 100vw; height: 100vh; overflow: hidden; display: block; padding: 0; }
  .bespoke-marp-parent { position: absolute; inset: 0; overflow: hidden; }
  .marpit { position: absolute; left: 50%; top: 50%; width: 1600px; height: 900px; transform: translate(-50%, -50%) scale(var(--internkim-deck-scale, 1)); transform-origin: center center; }
  .marpit > section { position: absolute; inset: 0; width: 1600px !important; height: 900px !important; min-width: 1600px !important; max-width: none !important; min-height: 900px !important; max-height: none !important; margin: 0 !important; box-sizing: border-box; box-shadow: 0 24px 80px rgba(15, 23, 42, 0.28); visibility: hidden !important; pointer-events: none; }
  .marpit > section.bespoke-active { visibility: visible !important; pointer-events: auto; z-index: 1; }
  .bespoke-marp-osc { position: fixed; right: 20px; bottom: 18px; display: flex; align-items: center; gap: 8px; padding: 8px; border: 1px solid rgba(255,255,255,0.16); border-radius: 999px; background: rgba(15,23,42,0.86); color: white; font: 600 13px system-ui, -apple-system, BlinkMacSystemFont, sans-serif; box-shadow: 0 16px 40px rgba(0,0,0,0.26); backdrop-filter: blur(12px); z-index: 9999; transition: transform 320ms ease, opacity 320ms ease; }
  .bespoke-marp-osc[data-idle="true"] { transform: translateY(calc(100% + 26px)); opacity: 0; pointer-events: none; }
  body[data-bespoke-view="presenter"] .bespoke-marp-osc { right: auto; left: 33%; transform: translateX(-50%); }
  body[data-bespoke-view="presenter"] .bespoke-marp-osc[data-idle="true"] { transform: translateX(-50%) translateY(calc(100% + 26px)); }
  .bespoke-marp-osc button { width: 32px; height: 32px; border: 0; border-radius: 999px; background: rgba(255,255,255,0.12); color: white; cursor: pointer; display: grid; place-items: center; font: inherit; }
  .bespoke-marp-osc button:disabled { opacity: 0.35; cursor: default; }
  .bespoke-marp-osc svg { width: 18px; height: 18px; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; fill: none; }
  .bespoke-marp-osc-status { min-width: 44px; text-align: center; }
  .bespoke-marp-tooltip { position: fixed; left: 0; top: 0; opacity: 0; pointer-events: none; transform: translate(-50%, calc(-100% - 12px)); padding: 6px 8px; border-radius: 6px; background: rgba(15,23,42,0.94); color: white; font: 600 12px system-ui, -apple-system, BlinkMacSystemFont, sans-serif; white-space: nowrap; z-index: 10002; transition: opacity 120ms ease; }
  .bespoke-marp-tooltip[data-open="true"] { opacity: 1; }
  body[data-bespoke-view="presenter"] .bespoke-marp-osc button[data-action="presenter"] { display: none; }
  .bespoke-progress-parent { position: fixed; left: 0; right: 0; bottom: 0; height: 4px; background: rgba(255,255,255,0.14); z-index: 9998; }
  .bespoke-progress-bar { display: block; height: 100%; width: 0; background: #60a5fa; transition: width 180ms ease; }
  .bespoke-marp-overview { position: fixed; inset: 0; display: none; overflow: auto; padding: 72px 48px; background: rgba(2, 6, 23, 0.92); z-index: 10000; }
  .bespoke-marp-overview[data-open="true"] { display: block; }
  .bespoke-marp-overview-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 24px; max-width: 1440px; margin: 0 auto; }
  .bespoke-marp-overview-card { display: grid; gap: 10px; border: 0; background: transparent; color: white; text-align: left; cursor: pointer; font: 600 13px system-ui, -apple-system, BlinkMacSystemFont, sans-serif; }
  .bespoke-marp-overview-card.is-current .bespoke-marp-overview-thumb { outline: 3px solid #60a5fa; }
  .bespoke-marp-overview-thumb { position: relative; width: 100%; aspect-ratio: 16 / 9; overflow: hidden; border-radius: 8px; background: #0f172a; box-shadow: 0 18px 46px rgba(0,0,0,0.35); }
  .bespoke-marp-overview-thumb > section { position: absolute !important; left: 0 !important; top: 0 !important; width: 1600px !important; height: 900px !important; min-width: 1600px !important; max-width: none !important; min-height: 900px !important; max-height: none !important; opacity: 1 !important; pointer-events: none !important; transform: scale(var(--internkim-thumb-scale, 0.16)) !important; transform-origin: 0 0 !important; box-shadow: none !important;  visibility: visible !important;}
  .bespoke-marp-overview-close { position: fixed; right: 24px; top: 20px; width: 36px; height: 36px; border: 0; border-radius: 999px; background: rgba(255,255,255,0.14); color: white; cursor: pointer; font: 700 16px system-ui, -apple-system, BlinkMacSystemFont, sans-serif; z-index: 10001; }
  .bespoke-marp-overview-close svg { width: 18px; height: 18px; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; fill: none; }
  body[data-bespoke-view="presenter"] { background: #000; }
  body[data-bespoke-view="presenter"] .bespoke-marp-parent { right: 34%; bottom: 0; }
  .bespoke-marp-presenter-panel { position: fixed; top: 0; right: 0; bottom: 0; width: 34%; display: grid; grid-template-rows: minmax(160px, 38%) 1fr 64px; gap: 0; background: #0a0a0a; border-left: 1px solid rgba(255,255,255,0.1); color: white; font: 500 15px system-ui, -apple-system, BlinkMacSystemFont, sans-serif; z-index: 3; }
  .bespoke-marp-presenter-next { position: relative; overflow: hidden; margin: 20px; border-radius: 10px; background: #000; box-shadow: 0 12px 34px rgba(0,0,0,0.35); }
  .bespoke-marp-presenter-next > section { position: absolute !important; left: 0 !important; top: 0 !important; width: 1600px !important; height: 900px !important; min-width: 1600px !important; max-width: none !important; min-height: 900px !important; max-height: none !important; opacity: 1 !important; pointer-events: none !important; transform: scale(var(--internkim-presenter-next-scale, 0.2)) !important; transform-origin: 0 0 !important; box-shadow: none !important;  visibility: visible !important;}
  .bespoke-marp-presenter-note { overflow: auto; padding: 0 24px 24px; color: #d1d5db; line-height: 1.55; white-space: pre-wrap; }
  .bespoke-marp-presenter-info { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 24px; border-top: 1px solid rgba(255,255,255,0.08); color: #f9fafb; }
}
@page { size: 1600px 900px; margin: 0; }
@media print {
  body.internkim-deck-ready { display: block; width: auto; height: auto; overflow: visible; }
  .bespoke-marp-parent { position: static; inset: auto; overflow: visible; }
  .marpit { position: static; width: auto; height: auto; transform: none; }
  .marpit > section { position: relative; inset: auto; opacity: 1; pointer-events: auto; transform: none; box-shadow: none; page-break-after: always; }
  .bespoke-marp-osc,
  .bespoke-progress-parent,
  .bespoke-marp-overview,
  .bespoke-marp-presenter-panel { display: none !important; }
}
</style>
<script data-internkim-slide-viewer>
(() => {
  let activeIndex = 0;
  let slides = [];
  let deck = null;
  let parent = null;
  let osc = null;
  let progress = null;
  let overview = null;
  let presenterPanel = null;
  let presenterWindow = null;
  let tooltip = null;
  let isSyncingSlide = false;

  document.addEventListener("DOMContentLoaded", () => {
    slides = Array.from(document.querySelectorAll("section"));
    if (slides.length === 0) return;
    activeIndex = initialIndex();
    parent = ensureBespokeParent(slides);
    deck = parent.querySelector(".marpit");
    osc = document.createElement("nav");
    osc.className = "bespoke-marp-osc";
    osc.setAttribute("aria-label", "Slide controls");
    osc.innerHTML = `
      <button type="button" data-action="previous" aria-label="Previous slide" data-tooltip="Previous slide (← / PageUp)">${lucideIcon("chevron-left")}</button>
      <span class="bespoke-marp-osc-status" data-role="status"></span>
      <button type="button" data-action="next" aria-label="Next slide" data-tooltip="Next slide (→ / Space / PageDown)">${lucideIcon("chevron-right")}</button>
      <button type="button" data-action="fullscreen" aria-label="Fullscreen" data-tooltip="Fullscreen (F)">${lucideIcon("maximize")}</button>
      <button type="button" data-action="overview" aria-label="Overview" data-tooltip="Overview (O)">${lucideIcon("layout-grid")}</button>
      <button type="button" data-action="presenter" aria-label="Presenter view" data-tooltip="Presenter view (P)">${lucideIcon("presentation")}</button>
    `;
    progress = document.createElement("div");
    progress.className = "bespoke-progress-parent";
    progress.setAttribute("aria-hidden", "true");
    progress.innerHTML = `<span class="bespoke-progress-bar"></span>`;
    osc.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button) return;
      runControlAction(button.dataset.action);
    });
    osc.addEventListener("mouseover", (event) => {
      const button = event.target.closest("button[data-tooltip]");
      if (button) showTooltip(button);
    });
    osc.addEventListener("mouseout", (event) => {
      if (event.target.closest("button[data-tooltip]")) hideTooltip();
    });
    document.body.dataset.bespokeView = currentView();
    document.body.classList.add("internkim-deck-ready");
    parent.appendChild(osc);
    document.body.insertBefore(progress, parent);
    tooltip = document.createElement("div");
    tooltip.className = "bespoke-marp-tooltip";
    document.body.appendChild(tooltip);
    if (currentView() === "presenter") createPresenterPanel();
    updateScale();
    update();
    wakeControls();
  });

  window.addEventListener("resize", () => {
    if (deck) updateScale();
  });

  document.addEventListener("fullscreenchange", updateFullscreenButton);

  let controlsIdleTimer = null;

  function wakeControls() {
    if (!osc) return;
    osc.dataset.idle = "false";
    clearTimeout(controlsIdleTimer);
    controlsIdleTimer = setTimeout(() => {
      if (!osc || osc.matches(":hover")) {
        wakeControls();
        return;
      }
      osc.dataset.idle = "true";
      hideTooltip();
    }, 2600);
  }

  document.addEventListener("mousemove", wakeControls);
  document.addEventListener("pointerdown", wakeControls);

  document.addEventListener("keydown", (event) => {
    if (slides.length === 0) return;
    if (event.defaultPrevented || editableTarget(event.target)) return;
    if (["ArrowRight", "PageDown", " "].includes(event.key)) {
      event.preventDefault();
      go(1);
    }
    if (["ArrowLeft", "PageUp", "Backspace"].includes(event.key)) {
      event.preventDefault();
      go(-1);
    }
    if (event.key === "Home") {
      event.preventDefault();
      show(0);
    }
    if (event.key === "End") {
      event.preventDefault();
      show(slides.length - 1);
    }
    if (event.key === "Escape" && overview?.dataset.open === "true") {
      event.preventDefault();
      closeOverview();
    }
    if ((event.key === "o" || event.key === "O") && !event.altKey && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      toggleOverview();
    }
    if ((event.key === "f" || event.key === "F") && !event.altKey && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      toggleFullscreen();
    }
    if ((event.key === "p" || event.key === "P") && !event.altKey && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      openPresenterView();
    }
  });

  window.addEventListener("hashchange", () => {
    if (slides.length > 0) show(initialIndex(), false);
  });

  window.addEventListener("message", (event) => {
    if (event.data?.type !== "internkim-slide") return;
    isSyncingSlide = true;
    show(Number(event.data.index), false);
    isSyncingSlide = false;
  });

  function initialIndex() {
    const match = location.hash.match(/(?:slide-)?(\\d+)/);
    const parsed = match ? Number(match[1]) - 1 : 0;
    return clamp(parsed);
  }

  function editableTarget(target) {
    return target && target.closest && target.closest("input, textarea, select, button, [contenteditable='true']");
  }

  function go(delta) {
    show(activeIndex + delta);
  }

  function show(index, updateHash = true) {
    activeIndex = clamp(index);
    update();
    if (updateHash) history.replaceState(null, "", `#slide-${activeIndex + 1}`);
    broadcastSlideChange();
  }

  function update() {
    if (!osc || !progress) return;
    slides.forEach((slide, index) => {
      slide.classList.toggle("bespoke-active", index === activeIndex);
      slide.classList.toggle("bespoke-before", index < activeIndex);
      slide.classList.toggle("bespoke-after", index > activeIndex);
      slide.setAttribute("aria-hidden", index === activeIndex ? "false" : "true");
    });
    osc.querySelector("[data-action='previous']").disabled = activeIndex === 0;
    osc.querySelector("[data-action='next']").disabled = activeIndex === slides.length - 1;
    osc.querySelector("[data-role='status']").textContent = `${activeIndex + 1} / ${slides.length}`;
    progress.querySelector(".bespoke-progress-bar").style.width = `${((activeIndex + 1) / slides.length) * 100}%`;
    updateFullscreenButton();
    updateOverviewState();
    updatePresenterPanel();
  }

  function runControlAction(action) {
    if (action === "next") go(1);
    if (action === "previous") go(-1);
    if (action === "fullscreen") toggleFullscreen();
    if (action === "overview") toggleOverview();
    if (action === "presenter") openPresenterView();
  }

  function ensureBespokeParent(currentSlides) {
    const existingDeck = currentSlides[0].closest(".marpit");
    if (existingDeck) {
      const existingParent = existingDeck.closest(".bespoke-marp-parent");
      if (existingParent) return existingParent;
      const createdParent = document.createElement("div");
      createdParent.className = "bespoke-marp-parent";
      existingDeck.parentNode.insertBefore(createdParent, existingDeck);
      createdParent.appendChild(existingDeck);
      return createdParent;
    }
    const createdParent = document.createElement("div");
    createdParent.className = "bespoke-marp-parent";
    const createdDeck = document.createElement("div");
    createdDeck.className = "marpit";
    currentSlides[0].parentNode.insertBefore(createdParent, currentSlides[0]);
    createdParent.appendChild(createdDeck);
    currentSlides.forEach((slide) => createdDeck.appendChild(slide));
    return createdParent;
  }

  function updateScale() {
    const horizontalPadding = 0;
    const verticalPadding = 0;
    const bounds = parent.getBoundingClientRect();
    const availableWidth = Math.max(320, bounds.width - horizontalPadding);
    const availableHeight = Math.max(180, bounds.height - verticalPadding);
    const scale = Math.min(availableWidth / 1600, availableHeight / 900);
    deck.style.setProperty("--internkim-deck-scale", String(Math.max(0.1, scale)));
    updateOverviewScale();
    updatePresenterNextScale();
  }

  function clamp(index) {
    return Math.max(0, Math.min(slides.length - 1, Number.isFinite(index) ? index : 0));
  }

  function currentView() {
    return new URLSearchParams(location.search).get("view") === "presenter" ? "presenter" : "slide";
  }

  async function toggleFullscreen() {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      return;
    }
    await document.documentElement.requestFullscreen?.();
  }

  function updateFullscreenButton() {
    const button = osc?.querySelector("[data-action='fullscreen']");
    if (!button) return;
    const isFullscreen = !!document.fullscreenElement;
    button.innerHTML = lucideIcon(isFullscreen ? "minimize" : "maximize");
    button.setAttribute("aria-label", isFullscreen ? "Exit fullscreen" : "Fullscreen");
    button.dataset.tooltip = isFullscreen ? "Exit fullscreen (F)" : "Fullscreen (F)";
  }

  function toggleOverview() {
    if (overview?.dataset.open === "true") {
      closeOverview();
      return;
    }
    openOverview();
  }

  function openOverview() {
    if (!overview) overview = createOverview();
    overview.dataset.open = "true";
    updateOverviewScale();
    updateOverviewState();
  }

  function closeOverview() {
    if (overview) overview.dataset.open = "false";
  }

  function createOverview() {
    const createdOverview = document.createElement("div");
    createdOverview.className = "bespoke-marp-overview";
    createdOverview.innerHTML = `<button type="button" class="bespoke-marp-overview-close" aria-label="Close overview" title="Close overview (Esc)">${lucideIcon("x")}</button><div class="bespoke-marp-overview-grid"></div>`;
    const grid = createdOverview.querySelector(".bespoke-marp-overview-grid");
    slides.forEach((slide, index) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "bespoke-marp-overview-card";
      card.dataset.index = String(index);
      const thumb = document.createElement("div");
      thumb.className = "bespoke-marp-overview-thumb";
      thumb.appendChild(slide.cloneNode(true));
      card.appendChild(thumb);
      card.insertAdjacentHTML("beforeend", `<span>${index + 1}</span>`);
      card.addEventListener("click", () => {
        show(index);
        closeOverview();
      });
      grid.appendChild(card);
    });
    createdOverview.querySelector(".bespoke-marp-overview-close").addEventListener("click", closeOverview);
    document.body.appendChild(createdOverview);
    return createdOverview;
  }

  function updateOverviewState() {
    overview?.querySelectorAll(".bespoke-marp-overview-card").forEach((card) => {
      card.classList.toggle("is-current", Number(card.dataset.index) === activeIndex);
    });
  }

  function updateOverviewScale() {
    overview?.querySelectorAll(".bespoke-marp-overview-thumb").forEach((thumb) => {
      thumb.style.setProperty("--internkim-thumb-scale", String(thumb.clientWidth / 1600));
    });
  }

  function openPresenterView() {
    const url = new URL(location.href);
    url.searchParams.set("view", "presenter");
    url.hash = `slide-${activeIndex + 1}`;
    presenterWindow = window.open(url.toString(), "internkim-presenter", "width=1280,height=720,menubar=no,toolbar=no");
  }

  function broadcastSlideChange() {
    if (isSyncingSlide) return;
    const message = { type: "internkim-slide", index: activeIndex };
    presenterWindow?.postMessage(message, "*");
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage(message, "*");
    }
  }

  function createPresenterPanel() {
    presenterPanel = document.createElement("aside");
    presenterPanel.className = "bespoke-marp-presenter-panel";
    presenterPanel.innerHTML = `<div class="bespoke-marp-presenter-next"></div><div class="bespoke-marp-presenter-note"></div><div class="bespoke-marp-presenter-info"><span data-role="presenter-status"></span><time data-role="presenter-clock"></time></div>`;
    document.body.appendChild(presenterPanel);
    setInterval(updatePresenterClock, 1000);
    updatePresenterClock();
  }

  function updatePresenterPanel() {
    if (!presenterPanel) return;
    const nextSlide = slides[Math.min(activeIndex + 1, slides.length - 1)];
    const nextContainer = presenterPanel.querySelector(".bespoke-marp-presenter-next");
    nextContainer.replaceChildren(nextSlide.cloneNode(true));
    presenterPanel.querySelector(".bespoke-marp-presenter-note").textContent = notesForSlide(slides[activeIndex]);
    presenterPanel.querySelector("[data-role='presenter-status']").textContent = `${activeIndex + 1} / ${slides.length}`;
    updatePresenterNextScale();
  }

  function updatePresenterNextScale() {
    const nextContainer = presenterPanel?.querySelector(".bespoke-marp-presenter-next");
    if (!nextContainer) return;
    const scale = Math.min(nextContainer.clientWidth / 1600, nextContainer.clientHeight / 900);
    nextContainer.style.setProperty("--internkim-presenter-next-scale", String(Math.max(0.1, scale)));
  }

  function updatePresenterClock() {
    const clock = presenterPanel?.querySelector("[data-role='presenter-clock']");
    if (clock) clock.textContent = new Date().toLocaleTimeString();
  }

  function notesForSlide(slide) {
    const note = slide.querySelector("aside.notes, aside[role='note'], [data-speaker-notes]");
    if (note?.textContent?.trim()) return note.textContent.trim();
    const heading = slide.querySelector("h1, h2, h3")?.textContent?.trim() || `Slide ${activeIndex + 1}`;
    return `현재 슬라이드: ${heading}`;
  }

  function showTooltip(button) {
    if (!tooltip) return;
    tooltip.textContent = button.dataset.tooltip || "";
    const bounds = button.getBoundingClientRect();
    tooltip.style.left = `${bounds.left + bounds.width / 2}px`;
    tooltip.style.top = `${bounds.top}px`;
    tooltip.dataset.open = "true";
  }

  function hideTooltip() {
    if (tooltip) tooltip.dataset.open = "false";
  }

  function lucideIcon(name) {
    const icons = {
      "chevron-left": `<svg data-lucide="chevron-left" viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>`,
      "chevron-right": `<svg data-lucide="chevron-right" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"></path></svg>`,
      "layout-grid": `<svg data-lucide="layout-grid" viewBox="0 0 24 24" aria-hidden="true"><rect width="7" height="7" x="3" y="3" rx="1"></rect><rect width="7" height="7" x="14" y="3" rx="1"></rect><rect width="7" height="7" x="14" y="14" rx="1"></rect><rect width="7" height="7" x="3" y="14" rx="1"></rect></svg>`,
      "maximize": `<svg data-lucide="maximize" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3"></path><path d="M21 8V5a2 2 0 0 0-2-2h-3"></path><path d="M3 16v3a2 2 0 0 0 2 2h3"></path><path d="M16 21h3a2 2 0 0 0 2-2v-3"></path></svg>`,
      "minimize": `<svg data-lucide="minimize" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3v3a2 2 0 0 1-2 2H3"></path><path d="M21 8h-3a2 2 0 0 1-2-2V3"></path><path d="M3 16h3a2 2 0 0 1 2 2v3"></path><path d="M16 21v-3a2 2 0 0 1 2-2h3"></path></svg>`,
      "presentation": `<svg data-lucide="presentation" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 3h20"></path><path d="M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3"></path><path d="m7 21 5-5 5 5"></path></svg>`,
      "x": `<svg data-lucide="x" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>`,
    };
    return icons[name] || "";
  }
})();
</script>
""".strip()
    head_match = re.search(r"</head>", source_text, flags=re.IGNORECASE)
    if head_match:
        prefix = source_text[:head_match.start()].rstrip()
        return prefix + "\n" + viewer_style + "\n" + source_text[head_match.start():]
    return viewer_style + "\n" + source_text.lstrip()


def inline_local_images(source_text: str, base_path: pathlib.Path) -> str:
    image_pattern = r'src="([^"]+\.(?:png|jpg|jpeg|gif|webp|svg))"'

    def replace_image(match: re.Match[str]) -> str:
        image_url = html.unescape(match.group(1))
        if image_url.startswith(("data:", "http:", "https:")):
            return match.group(0)
        image_path = resolve_resource_path(image_url, base_path)
        if image_path is None or not image_path.exists():
            return match.group(0)
        extension = image_path.suffix.lower().removeprefix(".")
        mime_type = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "svg": "image/svg+xml",
        }.get(extension, mimetypes.guess_type(image_path)[0] or "application/octet-stream")
        data_url = base64_data_url(mime_type, image_path)
        return f'src="{data_url}"'

    return re.sub(image_pattern, replace_image, source_text, flags=re.IGNORECASE)


def inline_local_fonts(source_text: str, base_path: pathlib.Path) -> str:
    font_pattern = r"url\((['\"]?)([^)'\"]+\.(?:woff2|woff|otf|ttf)(?:[?#][^)'\"]*)?)\1\)"

    def replace_font(match: re.Match[str]) -> str:
        quote = match.group(1) or ""
        font_url = html.unescape(match.group(2))
        if font_url.startswith(("data:", "http:", "https:")):
            return match.group(0)
        font_path = resolve_resource_path(font_url, base_path)
        if font_path is None or not font_path.exists():
            return match.group(0)
        return f"url({quote}{base64_data_url(font_mime_type(font_path), font_path)}{quote})"

    return re.sub(font_pattern, replace_font, source_text, flags=re.IGNORECASE)


def resolve_resource_path(resource_url: str, base_path: pathlib.Path) -> pathlib.Path | None:
    clean_url = resource_url.split("#", 1)[0].split("?", 1)[0]
    if clean_url.startswith("file://"):
        return pathlib.Path(clean_url.removeprefix("file://"))
    resource_path = pathlib.Path(clean_url)
    if resource_path.is_absolute():
        resolved_skill_asset_path = resolve_skill_asset_path(resource_path)
        if resolved_skill_asset_path is not None:
            return resolved_skill_asset_path
        return resource_path
    resolved_path = (base_path / resource_path).resolve()
    if resolved_path.exists():
        return resolved_path
    return resolve_skill_asset_path(resource_path)


def resolve_skill_asset_path(resource_path: pathlib.Path) -> pathlib.Path | None:
    path_text = str(resource_path)
    marker = "presentation/assets/"
    if marker not in path_text:
        return None
    asset_relative_text = path_text.split(marker, 1)[1].lstrip("/")
    asset_path = pathlib.Path(__file__).resolve().parent.parent / "assets" / asset_relative_text
    if asset_path.exists():
        return asset_path
    return resolve_paperlogy_alias(asset_relative_text)


def resolve_paperlogy_alias(asset_relative_text: str) -> pathlib.Path | None:
    aliases = {
        "fonts/Paperlogy-Regular.woff2": "fonts/paperlogy/Paperlogy-4Regular.woff2",
        "fonts/Paperlogy-Medium.woff2": "fonts/paperlogy/Paperlogy-6SemiBold.woff2",
        "fonts/Paperlogy-SemiBold.woff2": "fonts/paperlogy/Paperlogy-6SemiBold.woff2",
        "fonts/Paperlogy-Bold.woff2": "fonts/paperlogy/Paperlogy-7Bold.woff2",
        "fonts/Paperlogy-ExtraBold.woff2": "fonts/paperlogy/Paperlogy-8ExtraBold.woff2",
    }
    aliased_path = aliases.get(asset_relative_text)
    if aliased_path is None:
        return None
    resolved_path = pathlib.Path(__file__).resolve().parent.parent / "assets" / aliased_path
    if resolved_path.exists():
        return resolved_path
    return None


def base64_data_url(mime_type: str, path: pathlib.Path) -> str:
    import base64

    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime_type};base64,{encoded}"


def font_mime_type(path: pathlib.Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".woff2":
        return "font/woff2"
    if suffix == ".woff":
        return "font/woff"
    if suffix == ".otf":
        return "font/otf"
    if suffix == ".ttf":
        return "font/ttf"
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def read_design_tokens(path: pathlib.Path) -> dict[str, str]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    tokens = {}
    section = ""
    for raw_line in parts[1].splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1].strip()
            continue
        if not section or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            tokens[section + "." + key] = value
    return tokens


def create_slide_models(slide_sources: list[str]) -> list[SlideModel]:
    models = []
    for index, slide_source in enumerate(slide_sources, start=1):
        lines = slide_visible_lines(slide_source)
        title = first_heading_text(slide_source) or first_non_empty_line(lines, f"Slide {index}")
        tables = extract_tables(slide_source)
        list_items = extract_list_items(slide_source)
        models.append(SlideModel(
            index=index,
            source=slide_source,
            title=title,
            lines=lines,
            tables=tables,
            list_items=list_items,
            kind=infer_slide_kind(index, slide_source, title, lines),
        ))
    return models


def slide_visible_lines(slide_source: str) -> list[str]:
    text = visible_text(remove_invisible_slide_markup(slide_source))
    return [line for line in text.splitlines() if line.strip()]


def remove_invisible_slide_markup(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(
        r"<(?:aside|div)\b[^>]*class=[\"'][^\"']*(?:speaker-notes|notes)[^\"']*[\"'][^>]*>.*?</(?:aside|div)>",
        " ",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )


def first_heading_text(slide_source: str) -> str:
    match = re.search(r"<h[1-3]\b[^>]*>(.*?)</h[1-3]>", slide_source, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return visible_text(match.group(1)).replace("\n", " ").strip()


def first_non_empty_line(lines: list[str], default_value: str) -> str:
    for line in lines:
        if line.strip():
            return line.strip()
    return default_value


def extract_tables(slide_source: str) -> list[list[list[str]]]:
    tables = []
    for table_match in re.finditer(r"<table\b[^>]*>(.*?)</table>", slide_source, flags=re.IGNORECASE | re.DOTALL):
        rows = extract_table_rows(table_match.group(1))
        if rows:
            tables.append(rows)
    return tables


def extract_table_rows(table_source: str) -> list[list[str]]:
    rows = []
    for row_match in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", table_source, flags=re.IGNORECASE | re.DOTALL):
        cells = []
        for cell_match in re.finditer(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_match.group(1), flags=re.IGNORECASE | re.DOTALL):
            cell_text = visible_text(remove_invisible_slide_markup(cell_match.group(1))).replace("\n", " ").strip()
            if cell_text:
                cells.append(cell_text)
        if cells:
            rows.append(cells)
    return rows


def extract_list_items(slide_source: str) -> list[str]:
    items = []
    for match in re.finditer(r"<li\b[^>]*>(.*?)</li>", slide_source, flags=re.IGNORECASE | re.DOTALL):
        text = visible_text(remove_invisible_slide_markup(match.group(1))).replace("\n", " ").strip()
        if text:
            items.append(text)
    return items


def infer_slide_kind(index: int, slide_source: str, title: str, lines: list[str]) -> str:
    text = " ".join([title, " ".join(lines), slide_source]).casefold()
    if index == 1:
        return "cover"
    if contains_any(text, ["summary", "요약", "executive"]):
        return "summary"
    if contains_any(text, ["approval", "승인", "next step", "다음 단계", "요청"]):
        return "approval"
    if contains_any(text, ["risk", "리스크", "defect", "sla", "response", "대응"]):
        return "risk"
    if contains_any(text, ["roadmap", "로드맵", "timeline", "milestone", "2026-08", "2026-09"]):
        return "timeline"
    if contains_any(text, ["metric", "지표", "revenue", "uptime", "target", "actual", "목표", "실제"]):
        return "metrics"
    return "content"


def contains_any(text: str, values: list[str]) -> bool:
    return any(value.casefold() in text for value in values)


def pptx_mode() -> str:
    mode = os.environ.get("PRESENTATION_PPTX_MODE", "image").strip().casefold()
    if mode in {"image", "native"}:
        return mode
    return "image"


def try_html_render(html_render_script: pathlib.Path, source_path: pathlib.Path, deck_name: str, build_path: pathlib.Path, formats: set[str]) -> str:
    marker_path = browser_unavailable_marker_path(build_path)
    if marker_path.exists():
        message = "browser previously unavailable in this workspace; skipping render attempt"
        print(f"[warning] {message}", file=sys.stderr, flush=True)
        return message
    try:
        run_html_render(html_render_script, source_path, deck_name, build_path, formats)
        return ""
    except subprocess.CalledProcessError as error_value:
        message = f"browser render failed with exit code {error_value.returncode}"
        print(f"[warning] {message}; continuing with available browserless outputs", file=sys.stderr, flush=True)
        write_browser_unavailable_marker(marker_path)
        return message
    except OSError as error_value:
        message = f"browser render unavailable: {error_value}"
        print(f"[warning] {message}; continuing with available browserless outputs", file=sys.stderr, flush=True)
        write_browser_unavailable_marker(marker_path)
        return message


def clear_stale_render_evidence(review_path: pathlib.Path, deck_name: str) -> None:
    if not review_path.exists():
        return
    stale_paths = [
        *review_path.glob(f"{deck_name}.[0-9][0-9][0-9].png"),
        *review_path.glob("contact-sheet-*.png"),
        review_path / "render-source.txt",
    ]
    for stale_path in stale_paths:
        if stale_path.exists():
            stale_path.unlink()


def browser_unavailable_marker_path(build_path: pathlib.Path) -> pathlib.Path:
    return build_path.parent / ".skill-env" / "presentation" / "browser-unavailable"


def write_browser_unavailable_marker(marker_path: pathlib.Path) -> None:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text("browser launch failed; delete this file to retry browser rendering\n", encoding="utf-8")


def run_html_render(html_render_script: pathlib.Path, source_path: pathlib.Path, deck_name: str, build_path: pathlib.Path, formats: set[str]) -> None:
    if not html_render_script.exists():
        raise SystemExit("Error: html_render.mjs not found. Cannot export HTML-first deck.")
    command = [
        "bun",
        str(html_render_script),
        str(source_path),
        deck_name,
        str(build_path),
        ",".join(sorted(formats)),
    ]
    subprocess.run(command, check=True)


def write_notes(slide_sources: list[str], notes_path: pathlib.Path) -> None:
    note_blocks = []
    for index, slide_source in enumerate(slide_sources, start=1):
        notes = extract_notes(slide_source)
        if notes:
            note_blocks.append(f"Slide {index}\n{notes}")
    notes_path.write_text("\n\n".join(note_blocks) + ("\n" if note_blocks else ""), encoding="utf-8")


def extract_notes(slide_source: str) -> str:
    matches = re.findall(
        r"<(?:aside|div)\b[^>]*class=[\"'][^\"']*(?:speaker-notes|notes)[^\"']*[\"'][^>]*>(.*?)</(?:aside|div)>",
        slide_source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return "\n".join(visible_text(match) for match in matches if visible_text(match)).strip()


def visible_text(source: str) -> str:
    source = re.sub(r"<script[^>]*>.*?</script>", " ", source, flags=re.IGNORECASE | re.DOTALL)
    source = re.sub(r"<style[^>]*>.*?</style>", " ", source, flags=re.IGNORECASE | re.DOTALL)
    source = re.sub(r"<[^>]+>", "\n", source)
    lines = [re.sub(r"\s+", " ", html.unescape(line)).strip() for line in source.splitlines()]
    return "\n".join(line for line in lines if line)


def run_render_review(render_review_script: pathlib.Path, source_path: pathlib.Path, deck_name: str, review_path: pathlib.Path) -> None:
    if not render_review_script.exists():
        raise SystemExit("Error: render_review.py not found. Cannot review HTML-first deck.")
    result = subprocess.run([sys.executable, str(render_review_script), str(source_path), deck_name, str(review_path)])
    if result.returncode != 0:
        raise SystemExit(f"Error: slide render review failed; see {review_path / 'slide-review.json'}")


def write_pptx(slide_models: list[SlideModel], design: dict[str, str], image_paths: list[pathlib.Path], pptx_path: pathlib.Path) -> str:
    if pptx_mode() == "image" and image_paths:
        write_image_backed_pptx(image_paths, pptx_path)
        return "image"
    if pptx_mode() == "image":
        print("[warning] image-backed PPTX requested, but rendered slide images are unavailable; writing native text-backed PPTX", file=sys.stderr, flush=True)
    write_native_text_pptx(slide_models, design, pptx_path)
    return "native"


def write_native_text_pptx(slide_models: list[SlideModel], design: dict[str, str], pptx_path: pathlib.Path) -> None:
    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as archive:
        write_pptx_static_files(archive, len(slide_models))
        for model in slide_models:
            archive.writestr(f"ppt/slides/slide{model.index}.xml", native_slide_xml(model, design))
            archive.writestr(f"ppt/slides/_rels/slide{model.index}.xml.rels", native_slide_relationship_xml())


def native_slide_xml(model: SlideModel, design: dict[str, str]) -> str:
    colors = native_colors(design)
    shapes = native_slide_shapes(model, colors)
    return xml_document(
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<p:cSld><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
        + "".join(shapes)
        + "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def native_colors(design: dict[str, str]) -> dict[str, str]:
    return {
        key: normalize_hex_color(design.get("colors." + key, DEFAULT_NATIVE_COLORS[key]), DEFAULT_NATIVE_COLORS[key])
        for key in DEFAULT_NATIVE_COLORS
    }


def normalize_hex_color(value: str, default_value: str) -> str:
    cleaned_value = value.strip().removeprefix("#").upper()
    if re.fullmatch(r"[0-9A-F]{3}", cleaned_value):
        return "".join(character * 2 for character in cleaned_value)
    if re.fullmatch(r"[0-9A-F]{6}", cleaned_value):
        return cleaned_value
    return default_value


def native_slide_shapes(model: SlideModel, colors: dict[str, str]) -> list[str]:
    shape_parts = []
    shape_id = 2
    title = native_slide_title(model)

    def add_rectangle(x: int, y: int, width: int, height: int, fill: str, line: str = "", radius: bool = False) -> None:
        nonlocal shape_id
        shape_parts.append(rectangle_shape_xml(shape_id, x, y, width, height, fill, line, radius))
        shape_id += 1

    def add_text(x: int, y: int, width: int, height: int, lines: list[str], font_size: int, color: str, bold: bool = False, align: str = "l") -> None:
        nonlocal shape_id
        visible_lines = [line for line in lines if line.strip()]
        if not visible_lines:
            return
        shape_parts.append(text_box_xml(shape_id, x, y, width, height, visible_lines, font_size, color, bold, align))
        shape_id += 1

    if model.kind == "cover":
        add_rectangle(0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, "111827")
        add_rectangle(112, 108, 330, 8, colors["accent"])
        add_text(112, 146, 900, 220, [title], 36, "FFFFFF", True)
        add_text(116, 390, 870, 190, non_title_lines(model)[:4], 20, "E5E7EB")
        add_rectangle(1088, 150, 360, 210, "0F172A", "334155")
        add_text(1128, 190, 280, 44, ["BOARD REVIEW"], 16, "94A3B8", True)
        add_text(1128, 250, 280, 70, ["승인 필요"], 24, "FFFFFF", True)
        add_rectangle(112, 676, 1180, 1, "334155")
        add_text(112, 724, 1120, 70, compact_source_line(model), 16, "CBD5E1")
        return shape_parts

    add_rectangle(0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, colors["background"])
    add_rectangle(72, 42, 160, 6, colors["accent"])
    add_text(72, 70, 1280, 78, [title], 28, colors["ink"], True)

    if model.kind == "summary":
        draw_summary_dashboard(add_rectangle, add_text, non_title_lines(model), colors)
        return shape_parts

    if model.kind == "metrics":
        if model.tables:
            draw_metric_scoreboard(add_rectangle, add_text, model.tables[0], colors)
        else:
            draw_line_cards(add_rectangle, add_text, non_title_lines(model), 72, 170, 1456, 610, colors, 3)
        return shape_parts

    if model.kind == "timeline":
        draw_timeline(add_rectangle, add_text, timeline_lines(model), colors)
        return shape_parts

    if model.kind == "risk":
        if model.tables:
            draw_risk_ledger_from_table(add_rectangle, add_text, model.tables[0], colors)
        else:
            draw_risk_panels(add_rectangle, add_text, non_title_lines(model), colors)
        return shape_parts

    if model.kind == "approval":
        draw_approval(add_rectangle, add_text, non_title_lines(model), colors)
        return shape_parts

    draw_line_cards(add_rectangle, add_text, non_title_lines(model), 72, 170, 1456, 610, colors, 2)
    return shape_parts


def native_slide_title(model: SlideModel) -> str:
    normalized_title = normalize_text_for_comparison(model.title)
    if model.kind == "summary" and normalized_title in {"executive summary", "summary"}:
        return "2분기 요약"
    if model.kind == "approval" and normalized_title in {"next steps", "next step"}:
        return "다음 단계"
    if model.kind == "risk" and normalized_title in {"risks", "risks and responses"}:
        return "리스크와 대응"
    return model.title


def non_title_lines(model: SlideModel) -> list[str]:
    title_text = normalize_text_for_comparison(model.title)
    lines = []
    for line in model.lines:
        if normalize_text_for_comparison(line) == title_text:
            continue
        if line not in lines:
            lines.append(line)
    return merge_label_value_lines(lines)


def merge_label_value_lines(lines: list[str]) -> list[str]:
    labels = []
    index = 0
    while index < len(lines) and is_label_line(lines[index]):
        labels.append(lines[index].rstrip(":：").strip())
        index += 1
    values = lines[index:]
    if len(labels) >= 2 and len(values) >= len(labels):
        merged_lines = [f"{label}: {values[label_index]}" for label_index, label in enumerate(labels)]
        return merged_lines + values[len(labels):]
    return lines


def is_label_line(value: str) -> bool:
    cleaned_value = value.strip()
    return cleaned_value.endswith((":","：")) and len(cleaned_value) <= 16


def normalize_text_for_comparison(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def compact_source_line(model: SlideModel) -> list[str]:
    values = []
    for line in model.lines:
        if any(character.isdigit() for character in line) or "제공된 자료 없음" in line:
            values.append(line)
        if len(values) >= 3:
            break
    return values


def timeline_lines(model: SlideModel) -> list[str]:
    if model.tables:
        rows = model.tables[0][1:] if len(model.tables[0]) > 1 else model.tables[0]
        return [" / ".join(row) for row in rows if row]
    lines = [line for line in non_title_lines(model) if re.search(r"\d{4}-\d{2}-\d{2}", line)]
    if lines:
        return lines
    if model.list_items:
        return model.list_items
    return non_title_lines(model)


def draw_summary_dashboard(add_rectangle, add_text, lines: list[str], colors: dict[str, str]) -> None:
    values = lines or ["제공된 자료 없음"]
    summary_items = summary_dashboard_items(values)
    add_rectangle(72, 172, 610, 510, "111827")
    add_text(112, 218, 520, 56, ["핵심 판단"], 23, "FFFFFF", True)
    add_text(112, 318, 520, 260, [summary_items["success"], summary_items["caution"]], 19, "E5E7EB")
    add_rectangle(720, 172, 810, 154, colors["surface"], colors["line"])
    add_text(754, 206, 720, 44, ["성과"], 16, colors["accent"], True)
    add_text(754, 252, 720, 44, [summary_items["success"]], 18, colors["ink"], True)
    add_rectangle(720, 354, 810, 154, colors["surface"], colors["line"])
    add_text(754, 388, 720, 44, ["주의"], 16, "B45309", True)
    add_text(754, 434, 720, 44, [summary_items["caution"]], 18, colors["ink"], True)
    add_rectangle(720, 536, 810, 146, "ECFDF5", colors["accent"])
    add_text(754, 568, 720, 40, ["요청"], 16, colors["accent"], True)
    add_text(754, 612, 720, 44, [summary_items["request"]], 18, colors["ink"], True)


def summary_dashboard_items(lines: list[str]) -> dict[str, str]:
    values = [strip_leading_label(line) for line in lines if line.strip()]
    success = first_matching_line(values, ["성과", "실적", "달성", "growth", "met"]) or first_available_line(values, 0)
    caution = first_matching_line(values, ["과제", "주의", "결함", "미달", "risk", "miss"]) or first_available_line(values, 1)
    request = first_matching_line(values, ["승인", "요청", "approve", "sign-off"]) or first_available_line(values, 2)
    return {
        "success": success or "제공된 자료 없음",
        "caution": caution or "제공된 자료 없음",
        "request": request or "제공된 자료 없음",
    }


def strip_leading_label(value: str) -> str:
    cleaned_value = value.strip()
    if ":" in cleaned_value:
        label, content = cleaned_value.split(":", 1)
        if len(label.strip()) <= 12 and content.strip():
            return content.strip()
    if "：" in cleaned_value:
        label, content = cleaned_value.split("：", 1)
        if len(label.strip()) <= 12 and content.strip():
            return content.strip()
    return cleaned_value


def first_matching_line(lines: list[str], needles: list[str]) -> str:
    for line in lines:
        normalized_line = normalize_text_for_comparison(line)
        if any(normalize_text_for_comparison(needle) in normalized_line for needle in needles):
            return line
    return ""


def first_available_line(lines: list[str], index: int) -> str:
    if index < len(lines):
        return lines[index]
    if lines:
        return lines[-1]
    return ""


def draw_metric_scoreboard(add_rectangle, add_text, rows: list[list[str]], colors: dict[str, str]) -> None:
    if len(rows) < 2:
        draw_table(add_rectangle, add_text, rows, 72, 170, 1456, 620, colors)
        return
    header = rows[0]
    metric_index = table_column_index(header, ["metric", "지표"])
    q1_index = table_column_index(header, ["q1", "q1 2026"])
    q2_index = table_column_index(header, ["q2", "q2 2026"])
    target_index = table_column_index(header, ["target", "목표"])
    note_index = table_column_index(header, ["note", "비고"])
    add_rectangle(72, 164, 1456, 86, "111827")
    add_text(104, 190, 720, 40, ["목표 대비 Q2 판정"], 22, "FFFFFF", True)
    add_text(980, 194, 500, 34, ["actual / target / signal"], 14, "CBD5E1", False, "ctr")
    card_width = 462
    card_height = 188
    gap = 36
    for index, row in enumerate(rows[1:6]):
        column = index % 3
        row_number = index // 3
        x = 72 + column * (card_width + gap)
        y = 292 + row_number * (card_height + 34)
        status_fill = metric_status_color(table_value(row, note_index), table_value(row, target_index))
        add_rectangle(x, y, card_width, card_height, colors["surface"], colors["line"])
        add_rectangle(x, y, card_width, 8, status_fill)
        add_text(x + 28, y + 26, card_width - 56, 34, [table_value(row, metric_index)], 15, colors["muted"], True)
        add_text(x + 28, y + 66, card_width - 56, 54, [table_value(row, q2_index)], 26, colors["ink"], True)
        add_text(x + 28, y + 128, card_width - 56, 30, [f"Q1 {table_value(row, q1_index)}  ·  목표 {table_value(row, target_index)}"], 12, colors["muted"])
        add_text(x + 28, y + 158, card_width - 56, 24, [table_value(row, note_index)], 12, status_fill, True)


def draw_risk_ledger_from_table(add_rectangle, add_text, rows: list[list[str]], colors: dict[str, str]) -> None:
    if len(rows) < 2:
        draw_table(add_rectangle, add_text, rows, 72, 170, 1456, 620, colors)
        return
    header = rows[0]
    risk_index = table_column_index(header, ["risk", "리스크"])
    evidence_index = table_column_index(header, ["evidence", "근거"])
    response_index = table_column_index(header, ["response", "대응"])
    add_rectangle(72, 170, 1456, 64, "111827")
    add_text(104, 190, 420, 28, ["리스크"], 16, "FFFFFF", True)
    add_text(610, 190, 340, 28, ["근거"], 16, "FFFFFF", True)
    add_text(1034, 190, 420, 28, ["대응"], 16, "FFFFFF", True)
    row_height = 182
    for row_index, row in enumerate(rows[1:5]):
        y = 258 + row_index * (row_height + 24)
        fill = colors["surface"] if row_index % 2 == 0 else "F1F5F9"
        add_rectangle(72, y, 1456, row_height, fill, colors["line"])
        add_rectangle(94, y + 26, 118, 34, "FEF3C7", "", True)
        add_text(112, y + 34, 82, 18, ["ACTIVE"], 10, "92400E", True, "ctr")
        add_text(104, y + 76, 430, 72, [table_value(row, risk_index)], 16, colors["ink"], True)
        add_text(610, y + 44, 340, 92, [table_value(row, evidence_index)], 15, colors["ink"])
        add_text(1034, y + 44, 420, 92, [table_value(row, response_index)], 15, colors["ink"], True)


def table_column_index(header: list[str], candidates: list[str]) -> int:
    normalized_header = [normalize_text_for_comparison(value) for value in header]
    for candidate in candidates:
        normalized_candidate = normalize_text_for_comparison(candidate)
        for index, value in enumerate(normalized_header):
            if normalized_candidate in value:
                return index
    return 0


def table_value(row: list[str], index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return row[index]


def metric_status_color(note: str, target: str) -> str:
    normalized_note = normalize_text_for_comparison(note)
    normalized_target = normalize_text_for_comparison(target)
    if "miss" in normalized_note or "미달" in normalized_note or "초과" in normalized_note:
        return "B45309"
    if "met" in normalized_note or "달성" in normalized_note:
        return "0F766E"
    if "not provided" in normalized_target or "제공된 자료 없음" in normalized_target:
        return "64748B"
    return "0F766E"


def draw_line_cards(add_rectangle, add_text, lines: list[str], x: int, y: int, width: int, height: int, colors: dict[str, str], columns: int) -> None:
    values = lines or ["제공된 자료 없음"]
    card_count = max(1, min(6, len(values)))
    row_count = (card_count + columns - 1) // columns
    gap = 26
    card_width = (width - gap * (columns - 1)) // columns
    card_height = (height - gap * (row_count - 1)) // row_count
    for index, line in enumerate(values[:card_count]):
        column = index % columns
        row = index // columns
        card_x = x + column * (card_width + gap)
        card_y = y + row * (card_height + gap)
        add_rectangle(card_x, card_y, card_width, card_height, colors["surface"], colors["line"])
        add_rectangle(card_x, card_y, card_width, 8, colors["accent"])
        font_size = 17 if len(line) < 80 else 14
        add_text(card_x + 30, card_y + 28, card_width - 56, card_height - 52, [line], font_size, colors["ink"], index < 2)
    remaining_lines = values[card_count:]
    if remaining_lines:
        add_text(x, y + height + 16, width, 56, remaining_lines[:3], 13, colors["muted"])


def draw_table(add_rectangle, add_text, rows: list[list[str]], x: int, y: int, width: int, height: int, colors: dict[str, str]) -> None:
    visible_rows = rows[:8]
    column_count = max(len(row) for row in visible_rows)
    row_height = max(52, min(86, height // max(1, len(visible_rows))))
    column_width = width // max(1, column_count)
    for row_index, row in enumerate(visible_rows):
        row_y = y + row_index * row_height
        fill = colors["ink"] if row_index == 0 else (colors["surface"] if row_index % 2 else "EEF2F7")
        text_color = "FFFFFF" if row_index == 0 else colors["ink"]
        for column_index in range(column_count):
            cell_x = x + column_index * column_width
            cell_text = row[column_index] if column_index < len(row) else ""
            add_rectangle(cell_x, row_y, column_width - 2, row_height - 2, fill, colors["line"])
            add_text(cell_x + 16, row_y + 12, column_width - 32, row_height - 20, [cell_text], 14 if row_index else 15, text_color, row_index == 0)
    remaining_rows = rows[len(visible_rows):]
    if remaining_rows:
        add_text(x, y + height + 10, width, 52, ["추가 표 행: " + " / ".join(" | ".join(row) for row in remaining_rows[:2])], 12, colors["muted"])


def draw_timeline(add_rectangle, add_text, lines: list[str], colors: dict[str, str]) -> None:
    values = lines or ["제공된 자료 없음"]
    add_rectangle(128, 430, 1344, 8, colors["line"])
    card_width = 410
    gap = 46
    for index, line in enumerate(values[:3]):
        x = 110 + index * (card_width + gap)
        add_rectangle(x, 230, card_width, 350, colors["surface"], colors["line"])
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", line)
        date_text = date_match.group(0) if date_match else f"Step {index + 1}"
        add_rectangle(x + 28, 258, 170, 42, colors["accent"], "", True)
        add_text(x + 42, 266, 146, 26, [date_text], 13, "FFFFFF", True, "ctr")
        add_text(x + 28, 324, card_width - 56, 172, timeline_card_lines(line), 15, colors["ink"], True)
    if len(values) > 3:
        add_text(112, 640, 1320, 70, values[3:6], 16, colors["muted"])


def timeline_card_lines(line: str) -> list[str]:
    cells = [cell.strip() for cell in line.split("/") if cell.strip()]
    if len(cells) >= 4:
        return [cells[0], f"{cells[2]} · {cells[3]}"]
    return [line]


def draw_risk_panels(add_rectangle, add_text, lines: list[str], colors: dict[str, str]) -> None:
    groups = group_risk_lines(lines)
    panel_width = 700
    panel_height = 220
    positions = [(72, 180), (828, 180), (72, 450), (828, 450)]
    for index, group in enumerate(groups[:4]):
        x, y = positions[index]
        add_rectangle(x, y, panel_width, panel_height, colors["surface"], colors["line"])
        add_rectangle(x, y, panel_width, 8, colors["accent"])
        add_text(x + 34, y + 30, panel_width - 68, 48, [group[0]], 20, colors["ink"], True)
        add_text(x + 34, y + 92, panel_width - 68, 96, group[1:], 15, colors["muted"])
    remaining_lines = [line for group in groups[4:] for line in group]
    if remaining_lines:
        add_text(88, 720, 1380, 60, remaining_lines[:4], 13, colors["muted"])


def group_risk_lines(lines: list[str]) -> list[list[str]]:
    values = [line for line in lines if line.strip()]
    if not values:
        return [["제공된 자료 없음"]]
    if any(normalize_text_for_comparison(line) in {"증거:", "대응:", "evidence:", "response:"} for line in values):
        return [values[index:index + 5] for index in range(0, len(values), 5)]
    groups = []
    current_group = []
    for line in values:
        normalized_line = normalize_text_for_comparison(line)
        if current_group and not normalized_line.endswith(":") and len(current_group) >= 3:
            groups.append(current_group)
            current_group = []
        if normalized_line in {"증거:", "대응:", "evidence:", "response:"} and current_group:
            current_group.append(line)
            continue
        current_group.append(line)
    if current_group:
        groups.append(current_group)
    return groups


def draw_approval(add_rectangle, add_text, lines: list[str], colors: dict[str, str]) -> None:
    values = lines or ["제공된 자료 없음"]
    left_lines = values[::2] or values[:1]
    right_lines = values[1::2] or values[1:2] or values[:1]
    add_rectangle(72, 178, 700, 520, "111827")
    add_text(116, 226, 610, 70, ["승인 요청"], 24, "FFFFFF", True)
    add_text(116, 326, 610, 260, left_lines[:5], 18, "E5E7EB")
    add_rectangle(828, 178, 700, 520, colors["surface"], colors["line"])
    add_text(872, 226, 610, 70, ["다음 단계"], 24, colors["ink"], True)
    add_text(872, 326, 610, 260, right_lines[:5], 18, colors["ink"])
    add_text(88, 748, 1380, 56, values[10:14], 14, colors["muted"])


def rectangle_shape_xml(shape_id: int, x: int, y: int, width: int, height: int, fill: str, line: str = "", radius: bool = False) -> str:
    line_xml = f'<a:ln w="9525"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>' if line else '<a:ln><a:noFill/></a:ln>'
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Shape {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x_emu(x)}" y="{y_emu(y)}"/><a:ext cx="{x_emu(width)}" cy="{y_emu(height)}"/></a:xfrm>'
        f'<a:prstGeom prst="{"roundRect" if radius else "rect"}"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>{line_xml}</p:spPr></p:sp>'
    )


def text_box_xml(shape_id: int, x: int, y: int, width: int, height: int, lines: list[str], font_size: int, color: str, bold: bool, align: str) -> str:
    paragraphs = "".join(text_paragraph_xml(line, font_size, color, bold, align) for line in lines)
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Text {shape_id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x_emu(x)}" y="{y_emu(y)}"/><a:ext cx="{x_emu(width)}" cy="{y_emu(height)}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square" anchor="t"><a:spAutoFit/></a:bodyPr><a:lstStyle/>{paragraphs}</p:txBody></p:sp>'
    )


def text_paragraph_xml(value: str, font_size: int, color: str, bold: bool, align: str) -> str:
    bold_xml = ' b="1"' if bold else ""
    alignment = "ctr" if align == "ctr" else "l"
    return (
        f'<a:p><a:pPr algn="{alignment}"/>'
        f'<a:r><a:rPr lang="ko-KR" sz="{font_size * 100}"{bold_xml}>'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        '<a:latin typeface="Arial"/><a:ea typeface="Apple SD Gothic Neo"/></a:rPr>'
        f'<a:t>{xml_escape(value)}</a:t></a:r>'
        f'<a:endParaRPr lang="ko-KR" sz="{font_size * 100}"/></a:p>'
    )


def x_emu(value: int | float) -> int:
    return round(value * PRESENTATION_WIDTH_EMU / SLIDE_WIDTH)


def y_emu(value: int | float) -> int:
    return round(value * PRESENTATION_HEIGHT_EMU / SLIDE_HEIGHT)


def xml_escape(value: str) -> str:
    return html.escape(str(value), quote=True)


def native_slide_relationship_xml() -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        "</Relationships>"
    )


def write_native_review_images(slide_models: list[SlideModel], design: dict[str, str], review_path: pathlib.Path, deck_name: str) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[warning] Pillow is unavailable; native fallback review images were not created", file=sys.stderr, flush=True)
        return False
    review_path.mkdir(parents=True, exist_ok=True)
    colors = native_colors(design)
    fonts = {
        "title": preview_font(ImageFont, 46, True),
        "subtitle": preview_font(ImageFont, 28, True),
        "body": preview_font(ImageFont, 23, False),
        "small": preview_font(ImageFont, 17, False),
    }
    for model in slide_models:
        image = Image.new("RGB", (SLIDE_WIDTH, SLIDE_HEIGHT), hex_to_rgb("111827" if model.kind == "cover" else colors["background"]))
        draw = ImageDraw.Draw(image)
        draw_native_preview_slide(draw, model, colors, fonts)
        image.save(review_path / f"{deck_name}.{model.index:03}.png")
    return True


def write_render_source(review_path: pathlib.Path, render_source: str) -> None:
    review_path.mkdir(parents=True, exist_ok=True)
    (review_path / "render-source.txt").write_text(render_source + "\n", encoding="utf-8")


def preview_font(image_font_module, size: int, is_bold: bool):
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if is_bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            if pathlib.Path(candidate).exists():
                return image_font_module.truetype(candidate, size)
        except OSError:
            continue
    return image_font_module.load_default()


def draw_native_preview_slide(draw, model: SlideModel, colors: dict[str, str], fonts: dict[str, object]) -> None:
    if model.kind == "cover":
        draw.rectangle((0, 0, 92, SLIDE_HEIGHT), fill=hex_to_rgb(colors["accent"]))
        draw.rectangle((1260, 96, 1480, 316), fill=hex_to_rgb("1F2937"))
        draw_wrapped_text(draw, model.title, (150, 130), 1080, fonts["title"], hex_to_rgb("FFFFFF"), 1.15)
        draw_wrapped_lines(draw, non_title_lines(model)[:7], (154, 360), 980, fonts["body"], hex_to_rgb("E5E7EB"), 1.35)
        draw.rectangle((150, 684, 450, 692), fill=hex_to_rgb(colors["accent"]))
        draw_wrapped_lines(draw, compact_source_line(model), (150, 735), 1120, fonts["small"], hex_to_rgb("9CA3AF"), 1.25)
        return
    draw.rectangle((0, 0, SLIDE_WIDTH, 20), fill=hex_to_rgb(colors["accent"]))
    draw_wrapped_text(draw, model.title, (72, 58), 1280, fonts["subtitle"], hex_to_rgb(colors["ink"]), 1.2)
    if model.tables:
        draw_preview_table(draw, model.tables[0], (72, 170), (1456, 620), colors, fonts)
        return
    values = timeline_lines(model) if model.kind == "timeline" else non_title_lines(model)
    draw_preview_cards(draw, values, (72, 170), (1456, 610), colors, fonts, 3 if model.kind == "metrics" else 2)


def draw_preview_table(draw, rows: list[list[str]], origin: tuple[int, int], size: tuple[int, int], colors: dict[str, str], fonts: dict[str, object]) -> None:
    x, y = origin
    width, height = size
    visible_rows = rows[:8]
    column_count = max(len(row) for row in visible_rows)
    row_height = max(52, min(86, height // max(1, len(visible_rows))))
    column_width = width // max(1, column_count)
    for row_index, row in enumerate(visible_rows):
        fill = colors["ink"] if row_index == 0 else (colors["surface"] if row_index % 2 else "EEF2F7")
        text_color = "FFFFFF" if row_index == 0 else colors["ink"]
        for column_index in range(column_count):
            cell_x = x + column_index * column_width
            cell_y = y + row_index * row_height
            draw.rectangle((cell_x, cell_y, cell_x + column_width - 2, cell_y + row_height - 2), fill=hex_to_rgb(fill), outline=hex_to_rgb(colors["line"]))
            cell_text = row[column_index] if column_index < len(row) else ""
            draw_wrapped_text(draw, cell_text, (cell_x + 14, cell_y + 12), column_width - 28, fonts["small"], hex_to_rgb(text_color), 1.15)


def draw_preview_cards(draw, lines: list[str], origin: tuple[int, int], size: tuple[int, int], colors: dict[str, str], fonts: dict[str, object], columns: int) -> None:
    values = lines or ["제공된 자료 없음"]
    x, y = origin
    width, height = size
    card_count = max(1, min(6, len(values)))
    row_count = (card_count + columns - 1) // columns
    gap = 26
    card_width = (width - gap * (columns - 1)) // columns
    card_height = (height - gap * (row_count - 1)) // row_count
    for index, line in enumerate(values[:card_count]):
        column = index % columns
        row = index // columns
        card_x = x + column * (card_width + gap)
        card_y = y + row * (card_height + gap)
        draw.rectangle((card_x, card_y, card_x + card_width, card_y + card_height), fill=hex_to_rgb(colors["surface"]), outline=hex_to_rgb(colors["line"]), width=2)
        draw.rectangle((card_x, card_y, card_x + 10, card_y + card_height), fill=hex_to_rgb(colors["accent"]))
        draw_wrapped_text(draw, line, (card_x + 30, card_y + 28), card_width - 56, fonts["body"], hex_to_rgb(colors["ink"]), 1.25)


def draw_wrapped_lines(draw, lines: list[str], origin: tuple[int, int], width: int, font, fill: tuple[int, int, int], line_height_scale: float) -> None:
    y = origin[1]
    for line in lines:
        y = draw_wrapped_text(draw, line, (origin[0], y), width, font, fill, line_height_scale) + 8


def draw_wrapped_text(draw, text: str, origin: tuple[int, int], width: int, font, fill: tuple[int, int, int], line_height_scale: float) -> int:
    x, y = origin
    line_height = max(18, round(font_size_pixels(font) * line_height_scale))
    for line in wrap_preview_text(draw, text, font, width):
        draw.text((x, y), line, fill=fill, font=font)
        y += line_height
    return y


def wrap_preview_text(draw, text: str, font, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines = []
    current_line = ""
    for word in words:
        candidate = word if not current_line else current_line + " " + word
        if draw.textlength(candidate, font=font) <= width:
            current_line = candidate
            continue
        if current_line:
            lines.append(current_line)
        current_line = word
    if current_line:
        lines.append(current_line)
    return lines[:8]


def font_size_pixels(font) -> int:
    size = getattr(font, "size", None)
    return int(size) if isinstance(size, int) else 20


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    color = normalize_hex_color(value, "000000")
    return tuple(int(color[index:index + 2], 16) for index in range(0, 6, 2))


def write_image_backed_pptx(image_paths: list[pathlib.Path], pptx_path: pathlib.Path) -> None:
    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as archive:
        write_pptx_static_files(archive, len(image_paths))
        for index, image_path in enumerate(image_paths, start=1):
            archive.write(image_path, f"ppt/media/image{index}.png")
            archive.writestr(f"ppt/slides/slide{index}.xml", slide_xml(index))
            archive.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", slide_relationship_xml(index))




def write_pptx_static_files(archive: zipfile.ZipFile, slide_count: int) -> None:
    archive.writestr("[Content_Types].xml", content_types_xml(slide_count))
    archive.writestr("_rels/.rels", package_relationships_xml())
    archive.writestr("docProps/core.xml", core_properties_xml())
    archive.writestr("docProps/app.xml", app_properties_xml(slide_count))
    archive.writestr("ppt/presentation.xml", presentation_xml(slide_count))
    archive.writestr("ppt/_rels/presentation.xml.rels", presentation_relationships_xml(slide_count))
    archive.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
    archive.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_relationships_xml())
    archive.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
    archive.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_relationships_xml())
    archive.writestr("ppt/theme/theme1.xml", theme_xml())


def content_types_xml(slide_count: int) -> str:
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    overrides.extend(
        f'<Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(1, slide_count + 1)
    )
    return xml_document(
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        + "".join(overrides)
        + "</Types>"
    )


def package_relationships_xml() -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def presentation_relationships_xml(slide_count: int) -> str:
    relationships = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
    ]
    relationships.extend(
        f'<Relationship Id="rId{index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, slide_count + 1)
    )
    return xml_document(f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(relationships)}</Relationships>')


def presentation_xml(slide_count: int) -> str:
    slide_ids = "".join(f'<p:sldId id="{255 + index}" r:id="rId{index + 1}"/>' for index in range(1, slide_count + 1))
    return xml_document(
        '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<p:sldMasterIdLst><p:sldMasterId id="{SLIDE_MASTER_RELATIONSHIP_ID}" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{slide_ids}</p:sldIdLst>"
        f'<p:sldSz cx="{PRESENTATION_WIDTH_EMU}" cy="{PRESENTATION_HEIGHT_EMU}" type="wide"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        "</p:presentation>"
    )


def slide_xml(index: int) -> str:
    return xml_document(
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<p:cSld><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
        '<p:pic><p:nvPicPr><p:cNvPr id="2" name="Rendered slide"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>'
        '<p:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{PRESENTATION_WIDTH_EMU}" cy="{PRESENTATION_HEIGHT_EMU}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
        "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def slide_relationship_xml(index: int) -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{index}.png"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        "</Relationships>"
    )


def slide_master_relationships_xml() -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
        "</Relationships>"
    )


def slide_layout_relationships_xml() -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
        "</Relationships>"
    )


def slide_master_xml() -> str:
    return xml_document(
        '<p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></p:bgPr></p:bg>'
        '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>'
        '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
        '<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>'
        "</p:sldMaster>"
    )


def slide_layout_xml() -> str:
    return xml_document(
        '<p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" type="blank" preserve="1">'
        '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>'
        '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>'
        "</p:sldLayout>"
    )


def theme_xml() -> str:
    return xml_document(
        '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="internkim">'
        '<a:themeElements><a:clrScheme name="internkim">'
        '<a:dk1><a:srgbClr val="111827"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="374151"/></a:dk2><a:lt2><a:srgbClr val="F8FAFC"/></a:lt2>'
        '<a:accent1><a:srgbClr val="2563EB"/></a:accent1><a:accent2><a:srgbClr val="64748B"/></a:accent2>'
        '<a:accent3><a:srgbClr val="CBD5E1"/></a:accent3><a:accent4><a:srgbClr val="0F172A"/></a:accent4>'
        '<a:accent5><a:srgbClr val="475569"/></a:accent5><a:accent6><a:srgbClr val="E2E8F0"/></a:accent6>'
        '<a:hlink><a:srgbClr val="2563EB"/></a:hlink><a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink>'
        '</a:clrScheme><a:fontScheme name="internkim"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface="Apple SD Gothic Neo"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface="Apple SD Gothic Neo"/></a:minorFont></a:fontScheme>'
        '<a:fmtScheme name="internkim"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
        '<a:lnStyleLst><a:ln w="63500"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
        '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>'
        "</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>"
    )


def core_properties_xml() -> str:
    return xml_document(
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>HTML-first slide deck</dc:title>"
        "<dc:creator>internkim</dc:creator>"
        "</cp:coreProperties>"
    )


def app_properties_xml(slide_count: int) -> str:
    return xml_document(
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>internkim HTML Slides</Application>"
        f"<Slides>{slide_count}</Slides>"
        "</Properties>"
    )


def xml_document(body: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + body


def print_outputs(build_path: pathlib.Path, deck_name: str, formats: set[str], pptx_output_mode: str) -> None:
    print("")
    print("Done.")
    if "html" in formats:
        print(f"  {build_path.name}/{deck_name}.html            (HTML source rendered as deck)")
    if "pptx" in formats:
        if pptx_output_mode == "image":
            print(f"  {build_path.name}/{deck_name}.pptx            (image-backed PowerPoint / Keynote)")
        else:
            print(f"  {build_path.name}/{deck_name}.pptx            (native text-backed PowerPoint / Keynote fallback)")
    if "pdf" in formats and (build_path / f"{deck_name}.pdf").exists():
        print(f"  {build_path.name}/{deck_name}.pdf             (browser-rendered PDF)")
    elif "pdf" in formats:
        print(f"  {build_path.name}/{deck_name}.pdf             (not created; browser render unavailable)")
    if "notes" in formats:
        print(f"  {build_path.name}/{deck_name}-notes.txt       (speaker notes)")
    if "review" in formats:
        print(f"  {build_path.name}/review/slide-review.json (per-slide render review)")


if __name__ == "__main__":
    raise SystemExit(main())
