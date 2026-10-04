#!/usr/bin/env python3
from __future__ import annotations

import pathlib

from deck.deck_definitions import NO_SLIDE_SECTIONS
from deck.deck_kit import strip_deck_kit
from deck.deck_photos import unfocus_photos
from core.office_arguments import route_arguments
from core.office_result import OfficeFailure, Result, run_command
from deck.resource_inlining import restore_authored_source
from deck.slide_viewer import strip_screen_slide_viewer


def main() -> Result:
    arguments = parse_arguments()
    delivered_path = pathlib.Path(arguments.input)
    source_path = pathlib.Path(arguments.output)
    source_text = unfocus_photos(restore_authored_source(strip_deck_kit(strip_screen_slide_viewer(delivered_path.read_text(encoding="utf-8")))))
    if "<section" not in source_text.casefold():
        raise OfficeFailure(NO_SLIDE_SECTIONS.issue("delivered HTML contains no slide sections", str(delivered_path)))
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(source_text.rstrip() + "\n", encoding="utf-8")
    return Result(summary=f"restored the authored source {source_path} ({len(source_text.encode())} bytes)", output_path=str(source_path))


def parse_arguments():
    return route_arguments("convert")


if __name__ == "__main__":
    raise SystemExit(run_command(main))
