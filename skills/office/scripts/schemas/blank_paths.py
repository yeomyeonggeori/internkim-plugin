from __future__ import annotations

import copy
import re

from schemas.claims import sentences

PATH_PART = re.compile(r"([^.\[\]#]+)|\[(\d+)\]")


def blanked(values: dict, paths: list[str]) -> dict:
    result = copy.deepcopy(values)
    for path in sorted(paths, key=sentence_last):
        blank_path(result, path)
    return result


def sentence_last(path: str) -> tuple[str, int]:
    location, _, sentence = path.partition("#")
    return location, -int(sentence) if sentence.isdigit() else 0


def blank_path(values: dict, path: str) -> None:
    location, _, sentence = path.partition("#")
    parts = [name if name else int(index) for name, index in PATH_PART.findall(location)]
    if not parts:
        return
    parent = values
    for part in parts[:-1]:
        parent = step(parent, part)
        if parent is None:
            return
    last = parts[-1]
    if step(parent, last) is None:
        return
    if sentence.isdigit():
        parent[last] = without_sentence(parent[last], int(sentence))
        return
    parent[last] = None


def step(container: object, part: str | int) -> object:
    if isinstance(part, int):
        return container[part] if isinstance(container, list) and part < len(container) else None
    return container.get(part) if isinstance(container, dict) else None


def without_sentence(text: object, index: int) -> str | None:
    pieces = sentences(text) if isinstance(text, str) else []
    kept = [piece for position, piece in enumerate(pieces) if position != index]
    return " ".join(kept) or None
