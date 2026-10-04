from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from design_gate_fixture import OFFICE_ENTRY, design_markdown
from design_gate_slides import deck


CHART_STYLE = """
figure { width: 1408px; height: 640px; margin: 0; }
"""


def chart_section(title: str, figure: str) -> str:
    return f"<h2>{title}</h2>{figure}"


def write_free_deck(directory: Path, sections: list, style: str = "", design: dict | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "DESIGN.md").write_text(design_markdown(design), encoding="utf-8")
    (directory / "slides.html").write_text(deck(sections, CHART_STYLE + style), encoding="utf-8")
    return directory


def run_office_json(arguments: list[str], working_directory: Path) -> dict:
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=working_directory)
    return json.loads(completed.stdout)


def build_pptx(deck_path: Path, name: str = "deck") -> dict:
    return run_office_json(["create", f"build/{name}.pptx", "slides.html"], deck_path)
