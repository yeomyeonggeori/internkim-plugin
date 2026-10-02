#!/usr/bin/env python3
from __future__ import annotations

import pathlib

from deck.check_deck import check_request, deck_source_path
from deck.html_export import ExportRequest, export_deck, output_formats
from core.office_arguments import route_arguments
from core.office_result import Result, run_command


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


def main() -> Result:
    return export_deck(export_request(route_arguments("create", "slides")))


if __name__ == "__main__":
    raise SystemExit(run_command(main))
