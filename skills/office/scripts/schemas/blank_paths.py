from __future__ import annotations

import copy
import re

from schemas.claims import sentences

PATH_PART = re.compile(r"([^.\[\]#]+)|\[(\d+)\]")


def replacement_map(pairs: list[str]) -> dict[str, str]:
    replacements = {}
    for pair in pairs:
        path, separator, text = pair.partition("=")
        if not separator or not path:
            raise ValueError(f"a replacement is PATH=TEXT, not {pair!r}")
        replacements[path] = text
    return replacements


def blanked(values: dict, paths: list[str], replacements: dict[str, str] | None = None) -> dict:
    result = copy.deepcopy(values)
    for path, text in (replacements or {}).items():
        replace_path(result, path, text)
    for path in sorted(paths, key=sentence_last):
        blank_path(result, path)
    return result


def sentence_last(path: str) -> tuple[str, int]:
    location, _, sentence = path.partition("#")
    return location, -int(sentence) if sentence.isdigit() else 0


def located(values: dict, path: str) -> tuple[object, str | int, str] | None:
    location, _, sentence = path.partition("#")
    parts = [name if name else int(index) for name, index in PATH_PART.findall(location)]
    if not parts:
        return None
    parent = values
    for part in parts[:-1]:
        parent = step(parent, part)
        if parent is None:
            return None
    if step(parent, parts[-1]) is None:
        return None
    return parent, parts[-1], sentence


def replace_path(values: dict, path: str, text: str) -> None:
    found = located(values, path)
    if found is None:
        return
    parent, last, sentence = found
    if sentence.isdigit():
        pieces = sentences(parent[last]) if isinstance(parent[last], str) else []
        if int(sentence) < len(pieces):
            pieces[int(sentence)] = text
            parent[last] = " ".join(pieces)
        return
    parent[last] = text


def blank_path(values: dict, path: str) -> None:
    found = located(values, path)
    if found is None:
        return
    parent, last, sentence = found
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
