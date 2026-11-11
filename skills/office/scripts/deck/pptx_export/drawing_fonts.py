from __future__ import annotations

import itertools

from fonts.font_files import mapped_code_points
from fonts.pptx_embedding import deck_family
from fonts.registry import SANS_BODY, BundledFamily, default_family


def slide_with_drawable_runs(slide: dict) -> dict:
    return {**slide, "blocks": [block_with_drawable_runs(block) for block in slide["blocks"]]}


def block_with_drawable_runs(block: dict) -> dict:
    paragraphs = [{**paragraph, "runs": [piece for run in paragraph["runs"] for piece in drawable_pieces(run)]} for paragraph in block["paragraphs"]]
    return {**block, "paragraphs": paragraphs}


def drawable_pieces(run: dict) -> list[dict]:
    family = None if run.get("isBreak") else deck_family(run["fontFamily"])
    if family is None or all(draws(family, run["fontWeight"], character) for character in run["text"]):
        return [run]
    fallback = default_family(SANS_BODY)
    pieces = itertools.groupby(run["text"], key=lambda character: drawing_family_name(run, family, fallback, character))
    return [{**run, "text": "".join(characters), "fontFamily": name} for name, characters in pieces]


def drawing_family_name(run: dict, family: BundledFamily, fallback: BundledFamily, character: str) -> str:
    if draws(family, run["fontWeight"], character) or not draws(fallback, run["fontWeight"], character):
        return run["fontFamily"]
    return fallback.name


def draws(family: BundledFamily, weight: int, character: str) -> bool:
    return character.isspace() or ord(character) in mapped_code_points(family.path(family.face(weight)))
