from __future__ import annotations

from dataclasses import dataclass, field
import json
import pathlib
import re
import shutil
import subprocess
import tempfile

from fonts.registry import renderer_fonts
from core.office_result import INPUT_NOT_FOUND, SETUP_COMMAND, SETUP_SUGGESTION, IssueKind, OfficeFailure, WARNING, ERROR


RENDER_DIRECTORY = pathlib.Path(__file__).resolve().parent
PACKAGE_LOCK = RENDER_DIRECTORY / "package-lock.json"
NODE_MODULES = RENDER_DIRECTORY / "node_modules"
INSTALLED_LOCK = NODE_MODULES / ".installed-package-lock.json"
ENTRY_SCRIPT_NAME = "render_html.mjs"
DOCUMENT_ENTRY_SCRIPT_NAME = "document_pdf.mjs"
COLLECTION_SUFFIXES = {".ttc", ".otc"}
NODE_MAJOR_VERSION_MINIMUM = 18
DEFAULT_VIEWPORT = (1600, 900)
PIXELS_FILE_NAME = "pixels.json"
CONTACT_SHEETS_FILE_NAME = "contact-sheets.json"
PAGE_NUMBER_FOOTER = '<div style="display:flex;width:100%;justify-content:center;font-size:8pt;color:#6e7781"><span class="pageNumber"></span>&nbsp;/&nbsp;<span class="totalPages"></span></div>'

RUNTIME_REQUIREMENT = f"bun, or node {NODE_MAJOR_VERSION_MINIMUM} or newer"
RUNTIME_MISSING = f"neither bun nor node {NODE_MAJOR_VERSION_MINIMUM} or newer is installed"
RENDERER_UNAVAILABLE = IssueKind("RENDERER_UNAVAILABLE", ERROR, f"{RUNTIME_MISSING}, or the renderer's packages are not prepared, so nothing was drawn or written", SETUP_SUGGESTION)
RENDER_FAILED = IssueKind("RENDER_FAILED", ERROR, "the renderer stopped before drawing every page", "read the message for the page or element that stopped it")
LAYOUT_NOT_MAPPED = IssueKind("LAYOUT_NOT_MAPPED", WARNING, "part of a page's layout could not be matched to its HTML, so its boxes were not measured", "report the element the message names; the page images are still drawn")
STYLE_NOT_DRAWN = IssueKind("STYLE_NOT_DRAWN", WARNING, "an inline style declaration the renderer cannot read was left out, as a browser leaves out an invalid one", "remove the style attribute: the kit styles every part, data-accent on <body> sets a brand color, and theme tokens go in a <style> on :root")
RENDER_ISSUE_KINDS = (RENDERER_UNAVAILABLE, RENDER_FAILED, LAYOUT_NOT_MAPPED, STYLE_NOT_DRAWN)


class RendererUnavailable(Exception):
    pass


class RenderFailed(Exception):
    pass


@dataclass(frozen=True)
class FontFile:
    family: str
    path: pathlib.Path
    weight: int = 400
    index: int = 0
    style: str = "normal"
    generic: str | None = None


@dataclass(frozen=True)
class RenderRequest:
    html_path: pathlib.Path
    page_selector: str = "section"
    viewport: tuple[int, int] = DEFAULT_VIEWPORT
    fonts: tuple[FontFile, ...] = ()
    png_directory: pathlib.Path | None = None
    png_prefix: str = "page"
    pdf_path: pathlib.Path | None = None
    geometry_path: pathlib.Path | None = None
    layers_directory: pathlib.Path | None = None
    pixels_path: pathlib.Path | None = None
    contact_sheet_directory: pathlib.Path | None = None
    script_selector: str | None = None
    excluded_styles: str | None = None
    extra_css: tuple[str, ...] = ()
    geometry_thresholds: dict | None = None


@dataclass(frozen=True)
class DocumentPdfRequest:
    html: str
    css: str
    output_path: pathlib.Path
    title: str
    fonts: tuple[FontFile, ...]
    size: str | dict = "a4"
    landscape: bool = False
    margin: dict = field(default_factory=dict)
    footer: str | None = PAGE_NUMBER_FOOTER


@dataclass(frozen=True)
class RenderedPages:
    page_sizes: list[tuple[float, float]]
    png_paths: list[pathlib.Path] = field(default_factory=list)
    pdf_path: pathlib.Path | None = None
    geometry_path: pathlib.Path | None = None
    layers_directory: pathlib.Path | None = None
    contact_sheet_paths: list[pathlib.Path] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)
    dropped_styles: list[str] = field(default_factory=list)
    timings: dict[str, int] = field(default_factory=dict)


def bundled_fonts() -> tuple[FontFile, ...]:
    return tuple(FontFile(entry["family"], pathlib.Path(entry["path"]), entry["weight"], generic=entry["generic"]) for entry in renderer_fonts())


def font_from_json(entry: dict) -> FontFile:
    return FontFile(entry["family"], pathlib.Path(entry["path"]), int(entry.get("weight", 400)), int(entry.get("index", 0)), entry.get("style", "normal"))


def single_face_path(font: FontFile, scratch: pathlib.Path) -> pathlib.Path:
    if font.path.suffix.casefold() not in COLLECTION_SUFFIXES:
        return font.path
    from fonts.font_files import extract_face

    extracted_path = scratch / f"{font.path.stem}-face{font.index}.ttf"
    if not extracted_path.exists():
        extract_face(font.path, font.index, extracted_path)
    return extracted_path


def font_requests(fonts: tuple[FontFile, ...], scratch: pathlib.Path) -> list[dict]:
    requested = {(font.family, font.weight) for font in fonts}
    chosen = list(fonts) + [font for font in bundled_fonts() if (font.family, font.weight) not in requested]
    return [font_request(font, scratch) for font in chosen]


def font_request(font: FontFile, scratch: pathlib.Path) -> dict:
    return {"family": font.family, "weight": font.weight, "style": font.style, "path": str(single_face_path(font, scratch)), "generic": font.generic}


def javascript_runtime() -> list[str]:
    bun_path = shutil.which("bun")
    if bun_path:
        return [bun_path]
    node_path = shutil.which("node")
    if node_path and node_major_version(node_path) >= NODE_MAJOR_VERSION_MINIMUM:
        return [node_path]
    raise RendererUnavailable(RUNTIME_MISSING)


def node_major_version(node_path: str) -> int:
    completed = subprocess.run([node_path, "--version"], capture_output=True, text=True)
    match = re.match(r"v(\d+)", completed.stdout.strip())
    return int(match.group(1)) if match else 0


def has_packages() -> bool:
    return INSTALLED_LOCK.exists() and INSTALLED_LOCK.read_bytes() == PACKAGE_LOCK.read_bytes()


def prepare_renderer() -> str:
    javascript_runtime()
    if has_packages():
        return "found"
    install_packages()
    return "prepared"


def install_packages() -> None:
    if NODE_MODULES.exists():
        shutil.rmtree(NODE_MODULES)
    completed = subprocess.run(package_installer(), cwd=RENDER_DIRECTORY, capture_output=True, text=True)
    (RENDER_DIRECTORY / "bun.lock").unlink(missing_ok=True)
    if completed.returncode != 0:
        raise RendererUnavailable(f"installing the renderer's packages from {PACKAGE_LOCK.name} failed: {completed.stderr.strip()[-400:]}")
    shutil.copyfile(PACKAGE_LOCK, INSTALLED_LOCK)


def package_installer() -> list[str]:
    if shutil.which("npm"):
        return [shutil.which("npm"), "ci", "--omit=dev", "--no-audit", "--no-fund"]
    if shutil.which("bun"):
        return [shutil.which("bun"), "install", "--frozen-lockfile", "--production"]
    raise RendererUnavailable("neither npm nor bun is installed to fetch the renderer's packages")


def request_json(request: RenderRequest, scratch: pathlib.Path) -> dict:
    payload = {
        "html": str(request.html_path.resolve()),
        "pageSelector": request.page_selector,
        "viewport": {"width": request.viewport[0], "height": request.viewport[1]},
        "fonts": font_requests(request.fonts, scratch),
        "scriptSelector": request.script_selector,
        "excludeStyles": request.excluded_styles,
        "extraCss": list(request.extra_css),
    }
    if request.png_directory:
        payload["png"] = {"directory": str(request.png_directory), "prefix": request.png_prefix}
    optional_paths = {"pdf": request.pdf_path, "geometry": request.geometry_path, "layers": request.layers_directory, "pixels": request.pixels_path, "contactSheets": request.contact_sheet_directory}
    payload.update({name: str(path) for name, path in optional_paths.items() if path})
    if request.geometry_thresholds:
        payload["geometryThresholds"] = request.geometry_thresholds
    return payload


def render_html(request: RenderRequest) -> RenderedPages:
    if not request.html_path.exists():
        raise OfficeFailure(INPUT_NOT_FOUND.issue(f"{request.html_path} does not exist", str(request.html_path)))
    return rendered_pages(run_entry(ENTRY_SCRIPT_NAME, lambda scratch: request_json(request, scratch)))


def run_entry(entry_script_name: str, payload_for) -> dict:
    runtime = javascript_runtime()
    if not has_packages():
        raise RendererUnavailable(f"the renderer's packages are not prepared; run {SETUP_COMMAND}")
    with tempfile.TemporaryDirectory(prefix="office-render-") as scratch:
        request_path = pathlib.Path(scratch) / "request.json"
        request_path.write_text(json.dumps(payload_for(pathlib.Path(scratch))), encoding="utf-8")
        completed = subprocess.run([*runtime, str(RENDER_DIRECTORY / entry_script_name), str(request_path)], capture_output=True, text=True)
    if completed.returncode != 0:
        raise RenderFailed(completed.stderr.strip()[-1200:] or "the renderer exited without a message")
    return json.loads(completed.stdout.strip().splitlines()[-1])


def draw_preview(preview_path: pathlib.Path, page_selector: str, preview_fonts: list[dict], pdf_path: pathlib.Path | None = None, draw_images: bool = True) -> RenderedPages:
    directory = preview_path.parent
    request = RenderRequest(
        html_path=preview_path,
        page_selector=page_selector,
        fonts=tuple(font_from_json(entry) for entry in preview_fonts),
        png_directory=directory if draw_images else None,
        contact_sheet_directory=directory if draw_images else None,
        pdf_path=pdf_path,
    )
    return render_html(request)


def render_document_pdf(request: DocumentPdfRequest) -> pathlib.Path:
    run_entry(DOCUMENT_ENTRY_SCRIPT_NAME, lambda scratch: document_payload(request, scratch))
    return request.output_path


def document_payload(request: DocumentPdfRequest, scratch: pathlib.Path) -> dict:
    return {
        "html": request.html,
        "css": request.css,
        "output": str(request.output_path.resolve()),
        "title": request.title,
        "size": request.size,
        "landscape": request.landscape,
        "margin": request.margin,
        "footer": request.footer,
        "fontFamilies": list(dict.fromkeys(font.family for font in request.fonts)),
        "fonts": [font_request(font, scratch) for font in request.fonts],
    }


def optional_path(output: dict, key: str) -> pathlib.Path | None:
    return pathlib.Path(output[key]) if output.get(key) else None


def rendered_pages(output: dict) -> RenderedPages:
    return RenderedPages(
        page_sizes=[(page["width"], page["height"]) for page in output["pages"]],
        png_paths=[pathlib.Path(path) for path in output.get("png", [])],
        pdf_path=optional_path(output, "pdf"),
        geometry_path=optional_path(output, "geometry"),
        layers_directory=pathlib.Path(output["layers"]["directory"]) if output.get("layers") else None,
        contact_sheet_paths=[pathlib.Path(path) for path in output.get("contactSheets", [])],
        unmapped=output.get("unmapped", []),
        dropped_styles=output.get("droppedStyles", []),
        timings=output.get("timings", {}),
    )


def render_issues(rendered: RenderedPages, location: str) -> tuple:
    unmapped = [LAYOUT_NOT_MAPPED.issue(message, location) for message in rendered.unmapped]
    dropped = [STYLE_NOT_DRAWN.issue(f"left out: {declaration}", location) for declaration in rendered.dropped_styles]
    return tuple(unmapped + dropped)
