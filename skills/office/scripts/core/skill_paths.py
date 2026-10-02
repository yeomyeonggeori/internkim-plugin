from __future__ import annotations

from pathlib import Path


SCRIPTS_PATH = Path(__file__).resolve().parents[1]
SKILL_PATH = SCRIPTS_PATH.parent
ASSETS_PATH = SKILL_PATH / "assets"
REFERENCES_PATH = SKILL_PATH / "references"
