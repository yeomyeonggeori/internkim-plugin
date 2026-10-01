from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPTS_PATH = pathlib.Path(__file__).resolve().parents[1]
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from office_result import INPUT_NOT_FOUND, IssueKind, OfficeFailure, WARNING, ERROR  # noqa: E402
from skill_runtime import skill_cache_path  # noqa: E402


RENDER_DIRECTORY = pathlib.Path(__file__).resolve().parent
PACKAGE_MANIFEST = RENDER_DIRECTORY / "package.json"
ENTRY_SCRIPT_NAME = "render_html.mjs"
DOCUMENT_ENTRY_SCRIPT_NAME = "document_pdf.mjs"
BUNDLED_FONT_DIRECTORY = RENDER_DIRECTORY.parents[1] / "assets" / "fonts" / "paperlogy"
BUNDLED_FONT_PATTERN = re.compile(r"^(?P<family>[A-Za-z]+)-(?P<weight>\d)[A-Za-z]+\.ttf$")
COLLECTION_SUFFIXES = {".ttc", ".otc"}
NODE_MAJOR_VERSION_MINIMUM = 18
DEFAULT_VIEWPORT = (1600, 900)
PIXELS_FILE_NAME = "pixels.json"
CONTACT_SHEETS_FILE_NAME = "contact-sheets.json"

RENDERER_UNAVAILABLE = IssueKind("RENDERER_UNAVAILABLE", WARNING, "neither bun nor node 18 is installed, or the renderer's packages could not be installed, so no page was drawn", "install bun, or node 18 or newer, and run again")
RENDER_FAILED = IssueKind("RENDER_FAILED", ERROR, "the renderer stopped before drawing every page", "read the message for the page or element that stopped it")
LAYOUT_NOT_MAPPED = IssueKind("LAYOUT_NOT_MAPPED", WARNING, "part of a page's layout could not be matched to its HTML, so its boxes were not measured", "report the element the message names; the page images are still drawn")
STYLE_NOT_DRAWN = IssueKind("STYLE_NOT_DRAWN", WARNING, "an inline style declaration the renderer cannot read was left out, as a browser leaves out an invalid one", "write that property in a stylesheet rule, or with a value the message does not name")
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


@dataclass(frozen=True)
class DocumentPdfRequest:
    html: str
    css: str
    output_path: pathlib.Path
    title: str
    fonts: tuple[FontFile, ...]
    size: str = "a4"
    landscape: bool = False
    margin: dict = field(default_factory=dict)


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
    fonts = []
    for path in sorted(BUNDLED_FONT_DIRECTORY.glob("*.ttf")):
        match = BUNDLED_FONT_PATTERN.match(path.name)
        if match:
            fonts.append(FontFile(match["family"], path, int(match["weight"]) * 100))
    return tuple(fonts)


def font_from_json(entry: dict) -> FontFile:
    return FontFile(entry["family"], pathlib.Path(entry["path"]), int(entry.get("weight", 400)), int(entry.get("index", 0)), entry.get("style", "normal"))


def single_face_path(font: FontFile) -> pathlib.Path:
    if font.path.suffix.casefold() not in COLLECTION_SUFFIXES:
        return font.path
    from pdf_fonts import extract_face

    extracted_path = skill_cache_path(os.environ) / "fonts" / f"{font.path.stem}-face{font.index}.ttf"
    if not extracted_path.exists():
        extract_face(font.path, font.index, extracted_path)
    return extracted_path


def font_requests(fonts: tuple[FontFile, ...]) -> list[dict]:
    chosen = list(fonts) + [font for font in bundled_fonts() if (font.family, font.weight) not in {(other.family, other.weight) for other in fonts}]
    return [{"family": font.family, "weight": font.weight, "style": font.style, "path": str(single_face_path(font))} for font in chosen]


def javascript_runtime() -> list[str]:
    bun_path = shutil.which("bun")
    if bun_path:
        return [bun_path]
    node_path = shutil.which("node")
    if node_path and node_major_version(node_path) >= NODE_MAJOR_VERSION_MINIMUM:
        return [node_path]
    raise RendererUnavailable("neither bun nor node 18 or newer is installed")


def node_major_version(node_path: str) -> int:
    completed = subprocess.run([node_path, "--version"], capture_output=True, text=True)
    match = re.match(r"v(\d+)", completed.stdout.strip())
    return int(match.group(1)) if match else 0


def package_environment() -> pathlib.Path:
    manifest = PACKAGE_MANIFEST.read_bytes()
    environment = skill_cache_path(os.environ) / "render" / hashlib.sha256(manifest).hexdigest()[:16]
    if not (environment / "node_modules" / "@takumi-rs" / "core").exists():
        install_packages(environment, manifest)
    return script_directory(environment, {script.name: script.read_bytes() for script in sorted(RENDER_DIRECTORY.glob("*.mjs"))})


def script_directory(environment: pathlib.Path, scripts: dict[str, bytes]) -> pathlib.Path:
    digest = hashlib.sha256(b"".join(name.encode() + b"\0" + content for name, content in sorted(scripts.items()))).hexdigest()[:16]
    directory = environment / "scripts" / digest
    if directory.exists():
        return directory
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = pathlib.Path(tempfile.mkdtemp(dir=directory.parent))
    for name, content in scripts.items():
        (staging / name).write_bytes(content)
    try:
        staging.rename(directory)
    except OSError:
        shutil.rmtree(staging)
    return directory


def install_packages(environment: pathlib.Path, manifest: bytes) -> None:
    environment.mkdir(parents=True, exist_ok=True)
    (environment / "package.json").write_bytes(manifest)
    installer = [shutil.which("bun"), "install", "--production"] if shutil.which("bun") else [shutil.which("npm"), "install", "--omit=dev", "--no-audit", "--no-fund"]
    if not installer[0]:
        raise RendererUnavailable("neither bun nor npm is installed to fetch the renderer's packages")
    completed = subprocess.run(installer, cwd=environment, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RendererUnavailable(f"installing the renderer's packages failed: {completed.stderr.strip()[-400:]}")


def request_json(request: RenderRequest) -> dict:
    payload = {
        "html": str(request.html_path.resolve()),
        "pageSelector": request.page_selector,
        "viewport": {"width": request.viewport[0], "height": request.viewport[1]},
        "fonts": font_requests(request.fonts),
        "scriptSelector": request.script_selector,
        "excludeStyles": request.excluded_styles,
        "extraCss": list(request.extra_css),
    }
    if request.png_directory:
        payload["png"] = {"directory": str(request.png_directory), "prefix": request.png_prefix}
    optional_paths = {"pdf": request.pdf_path, "geometry": request.geometry_path, "layers": request.layers_directory, "pixels": request.pixels_path, "contactSheets": request.contact_sheet_directory}
    payload.update({name: str(path) for name, path in optional_paths.items() if path})
    return payload


def render_html(request: RenderRequest) -> RenderedPages:
    if not request.html_path.exists():
        raise OfficeFailure(INPUT_NOT_FOUND.issue(f"{request.html_path} does not exist", str(request.html_path)))
    return rendered_pages(run_entry(ENTRY_SCRIPT_NAME, request_json(request)))


def run_entry(entry_script_name: str, payload: dict) -> dict:
    runtime = javascript_runtime()
    environment = package_environment()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as request_file:
        json.dump(payload, request_file)
    try:
        completed = subprocess.run([*runtime, str(environment / entry_script_name), request_file.name], capture_output=True, text=True)
    finally:
        pathlib.Path(request_file.name).unlink(missing_ok=True)
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
    payload = {
        "html": request.html,
        "css": request.css,
        "output": str(request.output_path.resolve()),
        "title": request.title,
        "size": request.size,
        "landscape": request.landscape,
        "margin": request.margin,
        "fontFamilies": list(dict.fromkeys(font.family for font in request.fonts)),
        "fonts": [{"family": font.family, "weight": font.weight, "style": font.style, "path": str(single_face_path(font))} for font in request.fonts],
    }
    run_entry(DOCUMENT_ENTRY_SCRIPT_NAME, payload)
    return request.output_path


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
