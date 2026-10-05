from __future__ import annotations

from pathlib import Path

from staged_deck_fixture import build_deck, run_office, write_staged_deck


CHART_STYLE = """
figure { width: 1408px; height: 640px; margin: 0; }
"""


def chart_section(title: str, figure: str) -> str:
    return f"<h2>{title}</h2>{figure}"


def write_free_deck(directory: Path, sections: list, style: str = "", design: dict | None = None) -> Path:
    return write_staged_deck(directory, sections, CHART_STYLE + style, design)


def run_office_json(arguments: list[str], working_directory: Path) -> dict:
    return run_office(arguments, working_directory)


def build_pptx(deck_path: Path, name: str = "deck") -> dict:
    return build_deck(deck_path, name)
