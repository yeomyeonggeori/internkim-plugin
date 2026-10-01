#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
import sys

from check_deck import add_check_arguments, check_deck, check_request
from html_export import ALLOWED_FORMATS, enabled_formats
from office_result import OfficeArgumentParser, OfficeFailure, Result, command_result, failure_result


BUILD_SCRIPT_PATH = pathlib.Path(__file__).resolve().parent / "build.sh"
DEFAULT_FORMAT = "pdf"


def parse_arguments(arguments: list[str]):
    parser = OfficeArgumentParser(
        description="Check slides.html, then render it in a browser into build/<name>.pdf (or .pptx, .html) with review images, geometry and an acceptance verdict.",
    )
    parser.add_argument("--format", help=f"what to write: {', '.join(sorted(ALLOWED_FORMATS - {'review', 'notes'}))} or all, comma-separated; default {DEFAULT_FORMAT} (the FORMATS variable is read when this is absent)")
    parser.add_argument("--source", default="slides.html", help="the deck source (default slides.html)")
    parser.add_argument("--name", help="the output file name without extension (default this directory's name)")
    add_check_arguments(parser)
    return parser.parse_args(arguments)


def requested_formats(parsed) -> str:
    return parsed.format or os.environ.get("FORMATS") or DEFAULT_FORMAT


def preflight(parsed) -> Result:
    enabled_formats(requested_formats(parsed))
    return check_deck(check_request(pathlib.Path(parsed.source), parsed))


def forwarded_arguments(parsed) -> list[str]:
    arguments = [] if parsed.slide_count is None else ["--slide-count", str(parsed.slide_count)]
    for value in parsed.required_text:
        arguments += ["--required-text", value]
    return arguments


def build_environment(parsed) -> dict[str, str]:
    environment = os.environ.copy()
    environment["FORMATS"] = requested_formats(parsed)
    environment["SRC"] = parsed.source
    if parsed.name:
        environment["NAME"] = parsed.name
    return environment


def main(arguments: list[str]) -> int:
    parsed = parsed_or_none(arguments)
    if parsed is None:
        return 1
    check = command_result(lambda: preflight(parsed))
    if check.status == "error":
        return print_result(check)
    os.execvpe("bash", ["bash", str(BUILD_SCRIPT_PATH), *forwarded_arguments(parsed)], build_environment(parsed))


def parsed_or_none(arguments: list[str]):
    try:
        return parse_arguments(arguments)
    except OfficeFailure as failure:
        print_result(failure_result(failure.issues))
        return None


def print_result(result: Result) -> int:
    print(json.dumps(result.to_json(), ensure_ascii=False, indent=2))
    return 1 if result.status == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
