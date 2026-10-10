#!/usr/bin/env python3
from __future__ import annotations

import pathlib
from dataclasses import replace

from core.office_arguments import route_arguments
from core.office_result import Result, run_command
from core.source_snapshot import DELIVERABLE_EXTENSIONS, read_source, write_source
from deck.check_deck import DeckRequest, deck_directory
from deck.deck_claims import deck_claims
from deck.deck_holds import deck_slides
from deck.deck_preparation import prepare_deck
from deck.html_export import ExportRequest, export_deck, output_formats
from deck.page_blanks import blank_pages
from schemas.blank_paths import replacement_map


def held_blanks(output_path: pathlib.Path) -> list[dict]:
    blanks = read_source(output_path).get("blanks")
    return blanks if isinstance(blanks, list) else []


def with_held_blanks(blanks: list[dict], held: list[dict]) -> list[dict]:
    return blanks + [blank for blank in held if blank.get("field") not in {made.get("field") for made in blanks}]


def export_request(parsed, recomposed: tuple[int, ...], is_blank_remake: bool) -> ExportRequest:
    directory = deck_directory(parsed.source)
    output_path = pathlib.Path(parsed.output).expanduser().resolve()
    return ExportRequest(
        deck=DeckRequest(directory, parsed.slide_count, tuple(parsed.required_text), tuple(parsed.forbidden_text), is_blank_remake),
        deck_name=output_path.stem,
        build_path=output_path.parent,
        formats=output_formats(output_path.suffix.lower().lstrip(".")),
        recomposed=recomposed,
    )


def keep_built_provenance(request: ExportRequest, blanks: list[dict], details: dict) -> None:
    source_text = request.source_path.read_text(encoding="utf-8")
    visual_review = {"visualReview": details["visualReview"]} if "visualReview" in details else {}
    for suffix in DELIVERABLE_EXTENSIONS:
        built_path = request.output_path(suffix)
        if built_path.is_file():
            write_source(built_path, {"command": "office create", "arguments": [str(built_path), str(request.deck.directory)],
                                      "deck": str(request.deck.directory), "claims": deck_claims(source_text), "slides": deck_slides(source_text),
                                      "blanks": blanks, "design": prepare_deck().to_json(), **visual_review})


def main() -> Result:
    parsed = route_arguments("create", "slides")
    output_path = pathlib.Path(parsed.output).expanduser().resolve()
    held = held_blanks(output_path)
    made = blank_pages(deck_directory(parsed.source), parsed.blank or [], replacement_map(parsed.replace or []))
    blanks = with_held_blanks(made.blanks, made.held_on_the_remade_deck(held))
    request = export_request(parsed, made.recomposed, bool(held or parsed.blank or parsed.replace))
    result = export_deck(request)
    if result.status == "error":
        return result
    keep_built_provenance(request, blanks, result.details or {})
    return result if not blanks else blanked_result(result, blanks)


def blanked_result(result: Result, blanks: list[dict]) -> Result:
    labels = ", ".join(blank["label"] for blank in blanks)
    return replace(result, summary=f"{result.summary} {len(blanks)} values left blank for the person to complete: {labels}", details=(result.details or {}) | {"blanks": blanks})


if __name__ == "__main__":
    raise SystemExit(run_command(main))
