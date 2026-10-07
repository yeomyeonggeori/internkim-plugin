from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys


SOURCE_SUFFIX = ".source.json"
DELIVERABLE_EXTENSIONS = (".docx", ".xlsx", ".pptx", ".pdf")
WRITING_VERBS = ("create", "merge", "convert", "apply")
CARRYING_VERBS = ("apply",)


def source_path_of(output_path: Path | str) -> Path:
    path = Path(output_path).expanduser()
    return path.with_name(path.name + SOURCE_SUFFIX)


def read_source(output_path: Path | str) -> dict:
    path = source_path_of(output_path)
    if not path.is_file():
        return {}
    source = json.loads(path.read_text(encoding="utf-8"))
    return source if isinstance(source, dict) else {}


def write_source(output_path: Path | str, source: dict) -> Path:
    path = source_path_of(output_path)
    path.write_text(json.dumps(source, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def keep_provenance(output_path: str | None, arguments: list[str] | None = None) -> None:
    verb = os.environ.get("OFFICE_COMMAND", "").removeprefix("office ").strip()
    if verb not in WRITING_VERBS or not output_path or Path(output_path).suffix.lower() not in DELIVERABLE_EXTENSIONS:
        return
    if source_path_of(output_path).is_file():
        return
    words = list(sys.argv[1:] if arguments is None else arguments)
    input_path = words[0] if words else ""
    if verb in CARRYING_VERBS and input_path and source_path_of(input_path).is_file():
        shutil.copyfile(source_path_of(input_path), source_path_of(output_path))
        return
    write_source(output_path, {"command": f"office {verb}", "arguments": words})
