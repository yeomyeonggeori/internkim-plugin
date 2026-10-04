#!/usr/bin/env python3
from __future__ import annotations

import pathlib
from dataclasses import replace

from deck.check_deck import check_request, deck_source_path
from deck.html_export import ExportRequest, export_deck, output_formats
from core.office_arguments import route_arguments
from core.host_contract import DELIVERABLE_EXTENSIONS
from core.office_result import Result, run_command
from core.source_snapshot import write_source
from deck.deck_claims import blank_labels, blanked_deck, deck_claims
from schemas.blank_paths import replacement_map
from deck.deck_holds import deck_slides


def export_request(parsed) -> ExportRequest:
    source_path = deck_source_path(parsed.source).resolve()
    output_path = pathlib.Path(parsed.output).expanduser().resolve()
    return ExportRequest(
        source_path=source_path,
        deck_name=output_path.stem,
        build_path=output_path.parent,
        formats=output_formats(output_path.suffix.lower().lstrip(".")),
        check=check_request(source_path, parsed),
    )


def keep_built_provenance(request: ExportRequest, blanks: list[dict], details: dict) -> None:
    source_text = request.source_path.read_text(encoding="utf-8")
    visual_review = {"visualReview": details["visualReview"]} if "visualReview" in details else {}
    for suffix in DELIVERABLE_EXTENSIONS:
        built_path = request.output_path(suffix)
        if built_path.is_file():
            write_source(built_path, {"command": "office create", "arguments": [str(built_path), str(request.source_path)],
                                      "deck": str(request.source_path), "claims": deck_claims(source_text), "slides": deck_slides(source_text),
                                      "blanks": blanks, **visual_review})


def blank_source(request: ExportRequest, paths: list[str], replacements: dict[str, str]) -> list[dict]:
    if not paths and not replacements:
        return []
    source_text = request.source_path.read_text(encoding="utf-8")
    request.source_path.write_text(blanked_deck(source_text, paths, replacements), encoding="utf-8")
    return blank_labels(source_text, paths)


def main() -> Result:
    parsed = route_arguments("create", "slides")
    request = export_request(parsed)
    blanks = blank_source(request, parsed.blank or [], replacement_map(parsed.replace or []))
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
