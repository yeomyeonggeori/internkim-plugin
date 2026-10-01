from __future__ import annotations

import pathlib
import re


SCRIPT_PATH = pathlib.Path(__file__).resolve().parent
SLIDE_VIEWER_MARKER = "data-internkim-slide-viewer"
SLIDE_VIEWER_BLOCK_PATTERNS = (
    rf"\s*<style\b(?=[^>]*\b{SLIDE_VIEWER_MARKER}\b)[^>]*>.*?</style>\s*",
    rf"\s*<script\b(?=[^>]*\b{SLIDE_VIEWER_MARKER}\b)[^>]*>.*?</script>\s*",
)


def strip_screen_slide_viewer(source_text: str) -> str:
    stripped_text = source_text
    for block_pattern in SLIDE_VIEWER_BLOCK_PATTERNS:
        stripped_text = re.sub(block_pattern, "", stripped_text, flags=re.IGNORECASE | re.DOTALL)
    return stripped_text


def inject_screen_slide_viewer(source_text: str) -> str:
    source_text = strip_screen_slide_viewer(source_text)
    viewer_markup = slide_viewer_markup()
    head_match = re.search(r"</head>", source_text, flags=re.IGNORECASE)
    if not head_match:
        return viewer_markup + "\n" + source_text.lstrip()
    prefix = source_text[:head_match.start()].rstrip()
    return prefix + "\n" + viewer_markup + "\n" + source_text[head_match.start():]


def slide_viewer_markup() -> str:
    style = (SCRIPT_PATH / "slide-viewer.css").read_text(encoding="utf-8")
    script = (SCRIPT_PATH / "slide-viewer.js").read_text(encoding="utf-8")
    return (
        f"<style {SLIDE_VIEWER_MARKER}>\n{style}</style>\n"
        f"<script {SLIDE_VIEWER_MARKER}>\n{script}</script>"
    )
