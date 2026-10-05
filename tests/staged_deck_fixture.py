from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

SCRIPTS_PATH = Path(os.environ.get("OFFICE_SCRIPTS_PATH") or Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts")
OFFICE_ENTRY = SCRIPTS_PATH / "office"
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from core.host_contract import RUNTIME_CONTEXT_VARIABLE  # noqa: E402,F401
from deck.layout_choice import assigned_layouts  # noqa: E402
from deck.outline import Outline, OutlinePage, valid_layouts  # noqa: E402
from deck.page_checks import has_parallel_blocks  # noqa: E402
from deck.deck_source import find_all, parse_source  # noqa: E402
from deck.outline import LAYOUTS  # noqa: E402


STYLE_SHEET = {
    "style": "a calm update: white pages, one green accent",
    "colors": {"text": "#14213D", "accent": "#0E7C66", "secondary": "#B7791F", "surface": "#EEF5F2", "line": "#D5E2DC"},
    "backgrounds": {"cover": "#FFFFFF", "content": "#FFFFFF", "data": "#FFFFFF", "closing": "#FFFFFF"},
    "sizes": {"display": "96px", "title": "56px", "body": "28px", "small": "22px"},
}

PAGE_STYLE = """
section { padding: 96px; box-sizing: border-box; font-size: var(--size-body); display: flex; flex-direction: column; gap: 32px; }
h1, h2 { font-size: var(--size-title); margin: 0; }
h3 { font-size: 30px; margin: 0; }
p { margin: 0; }
.card { padding: 28px; background: var(--surface); border-radius: var(--radius); display: flex; flex-direction: column; gap: 12px; }
.row { display: flex; gap: 32px; }
.row > .card { flex: 1; }
"""

NOTES = '<aside class="notes">notes</aside>'
HEADING_PATTERN = re.compile(r"<(h[1-3])\b[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")


def style_sheet_markdown(overrides: dict | None = None) -> str:
    sheet = json.loads(json.dumps(STYLE_SHEET))
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(sheet.get(key), dict):
            sheet[key] = {name: entry for name, entry in (sheet[key] | value).items() if entry is not None}
        elif value is None:
            sheet.pop(key, None)
        else:
            sheet[key] = value
    lines = ["---"]
    for key, value in sheet.items():
        if isinstance(value, dict):
            lines += [f"{key}:", *(f'  {name}: "{entry}"' for name, entry in value.items())]
        else:
            lines.append(f'{key}: "{value}"')
    return "\n".join(lines + ["---"]) + "\n"


def section_parts(content) -> tuple[str, str]:
    return ("", content) if isinstance(content, str) else content


def page_markup(content, style: str = "") -> str:
    attributes, markup = section_parts(content)
    notes = "" if 'class="notes"' in markup else NOTES
    return f"<section{attributes}>\n<style>{PAGE_STYLE}{style}</style>\n{markup}{notes}\n</section>\n"


def plain_text(markup: str) -> str:
    return re.sub(r"\s+", " ", TAG_PATTERN.sub(" ", markup)).strip()


def page_title(markup: str, number: int) -> str:
    heading = HEADING_PATTERN.search(re.sub(r"<aside\b.*?</aside>", "", markup, flags=re.S))
    return plain_text(heading.group(2)) if heading else f"Page {number}"


def page_type(number: int, count: int, markup: str) -> str:
    if number == 1:
        return "cover"
    if number == count and count > 2:
        return "closing"
    return "data" if "data-chart" in markup else "content"


def outline_page(number: int, count: int, content, photos: list[str]) -> OutlinePage:
    _, markup = section_parts(content)
    visible = plain_text(re.sub(r"<aside\b.*?</aside>|<style\b.*?</style>", "", markup, flags=re.S)) or "the page"
    return OutlinePage(page_title(markup, number), page_type(number, count, markup), (visible,), tuple(photos))


def fitting_layouts(page: OutlinePage, markup: str) -> dict:
    section = find_all(parse_source(f"<section>{markup}</section>"), "section")[0]
    probabilities = {}
    for name in valid_layouts(page):
        layout = LAYOUTS[name]
        fits = not layout.get("chart") or "data-chart" in markup
        blocks = layout.get("parallelBlocks")
        fits = fits and (not blocks or has_parallel_blocks(section, *blocks))
        probabilities[name] = 0.9 if fits and not layout.get("photo") else 0.5 if fits else 0.01
    return {"probabilities": probabilities}


def staged_outline(sections: list, photos: dict[int, list[str]] | None = None, layouts: list[str] | None = None) -> Outline:
    count = len(sections)
    pages = tuple(outline_page(number, count, content, (photos or {}).get(number, [])) for number, content in enumerate(sections, start=1))
    outline = Outline("A sample deck for the tests", pages)
    if layouts is not None:
        return outline.with_layouts(layouts)
    choices = {f"page_{index + 1:02d}": fitting_layouts(page, section_parts(content)[1]) for index, (page, content) in enumerate(zip(pages, sections))}
    return outline.with_layouts(assigned_layouts(outline, choices))


def write_staged_deck(directory: Path, sections: list, style: str = "", design: dict | None = None, photos: dict[int, list[str]] | None = None, layouts: list[str] | None = None) -> Path:
    pages_directory = directory / "pages"
    pages_directory.mkdir(parents=True, exist_ok=True)
    (directory / "DESIGN.md").write_text(style_sheet_markdown(design), encoding="utf-8")
    (directory / "outline.json").write_text(json.dumps(staged_outline(sections, photos, layouts).to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    for number, content in enumerate(sections, start=1):
        (pages_directory / f"{number:02d}.html").write_text(page_markup(content, style), encoding="utf-8")
    return directory


def run_office(arguments: list[str], working_directory: Path, environment: dict | None = None) -> dict:
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=working_directory, env=environment)
    return json.loads(completed.stdout)


def build_deck(directory: Path, name: str = "deck", extension: str = "pptx", extra: list[str] | None = None, environment: dict | None = None) -> dict:
    return run_office(["create", f"build/{name}.{extension}", ".", *(extra or [])], directory, environment)


def check_deck(directory: Path, target: str = ".", extra: list[str] | None = None, environment: dict | None = None) -> dict:
    return run_office(["check", target, *(extra or [])], directory, environment)


def issue_codes(envelope: dict) -> set[str]:
    return {issue["code"] for issue in envelope.get("issues", [])}


def issues_at(envelope: dict, location: str) -> set[str]:
    return {issue["code"] for issue in envelope.get("issues", []) if issue.get("location") == location}
