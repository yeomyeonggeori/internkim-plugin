#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import sys

from check_deck import add_check_arguments, check_request
from html_export import ALLOWED_FORMATS, ExportRequest, enabled_formats, export_deck
from office_result import OfficeArgumentParser, Result, run_command


DEFAULT_FORMAT = "pdf"


def parse_arguments(arguments: list[str]):
    parser = OfficeArgumentParser(
        description="Check slides.html, then draw it without a browser into build/<name>.pdf (or .pptx, .html) with review images, geometry and an acceptance verdict.",
    )
    parser.add_argument("--format", help=f"what to write: {', '.join(sorted(ALLOWED_FORMATS - {'review', 'notes'}))} or all, comma-separated; default {DEFAULT_FORMAT} (the FORMATS variable is read when this is absent)")
    parser.add_argument("--source", default="slides.html", help="the deck source (default slides.html)")
    parser.add_argument("--name", help="the output file name without extension (default this directory's name)")
    add_check_arguments(parser)
    return parser.parse_args(arguments)


def export_request(parsed) -> ExportRequest:
    working_directory = pathlib.Path.cwd()
    source_path = (working_directory / parsed.source).resolve()
    return ExportRequest(
        source_path=source_path,
        deck_name=parsed.name or working_directory.name,
        build_path=working_directory / "build",
        formats=enabled_formats(parsed.format or os.environ.get("FORMATS") or DEFAULT_FORMAT),
        check=check_request(source_path, parsed),
    )


def main() -> Result:
    return export_deck(export_request(parse_arguments(sys.argv[1:])))


if __name__ == "__main__":
    raise SystemExit(run_command(main))
