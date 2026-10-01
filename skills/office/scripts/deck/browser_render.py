from __future__ import annotations

import pathlib
import re
import shutil
import subprocess

from office_result import INPUT_NOT_FOUND, OfficeFailure
from editable_pptx import text_layers_path
from geometry_checks import GEOMETRY_FILE_NAME
from slide_images import rendered_slide_image_paths


NODE_MAJOR_VERSION_MINIMUM = 18


def try_html_render(html_render_script: pathlib.Path, source_path: pathlib.Path, deck_name: str, build_path: pathlib.Path, formats: set[str]) -> str:
    marker_path = browser_unavailable_marker_path(build_path)
    if marker_path.exists():
        return "browser previously unavailable in this workspace; skipped the render attempt"
    try:
        run_html_render(html_render_script, source_path, deck_name, build_path, formats)
        return ""
    except subprocess.CalledProcessError as error_value:
        return record_browser_unavailable(marker_path, f"browser render failed with exit code {error_value.returncode}")
    except OSError as error_value:
        return record_browser_unavailable(marker_path, f"browser render unavailable: {error_value}")


def record_browser_unavailable(marker_path: pathlib.Path, message: str) -> str:
    write_browser_unavailable_marker(marker_path)
    return message


def run_html_render(html_render_script: pathlib.Path, source_path: pathlib.Path, deck_name: str, build_path: pathlib.Path, formats: set[str]) -> None:
    if not html_render_script.exists():
        raise OfficeFailure(INPUT_NOT_FOUND.issue(f"{html_render_script} not found; cannot render the deck", str(html_render_script)))
    command = [
        javascript_runtime(),
        str(html_render_script),
        str(source_path),
        deck_name,
        str(build_path),
        ",".join(sorted(formats)),
    ]
    subprocess.run(command, check=True)


def javascript_runtime() -> str:
    node_path = shutil.which("node")
    if node_path is None:
        return "bun"
    completed = subprocess.run([node_path, "--version"], capture_output=True, text=True)
    major_version = re.match(r"v(\d+)", completed.stdout.strip())
    return "node" if major_version and int(major_version.group(1)) >= NODE_MAJOR_VERSION_MINIMUM else "bun"


def browser_unavailable_marker_path(build_path: pathlib.Path) -> pathlib.Path:
    return build_path.parent / ".skill-env" / "presentation" / "browser-unavailable"


def write_browser_unavailable_marker(marker_path: pathlib.Path) -> None:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text("browser launch failed; delete this file to retry browser rendering\n", encoding="utf-8")


def clear_stale_render_evidence(review_path: pathlib.Path, deck_name: str) -> None:
    if not review_path.exists():
        return
    stale_paths = [
        *rendered_slide_image_paths(review_path, deck_name),
        *review_path.glob("contact-sheet-*.png"),
        review_path / "render-source.txt",
        review_path / GEOMETRY_FILE_NAME,
    ]
    for stale_path in stale_paths:
        if stale_path.exists():
            stale_path.unlink()
    shutil.rmtree(text_layers_path(review_path), ignore_errors=True)


def write_render_source(review_path: pathlib.Path, render_source: str) -> None:
    review_path.mkdir(parents=True, exist_ok=True)
    (review_path / "render-source.txt").write_text(render_source + "\n", encoding="utf-8")
