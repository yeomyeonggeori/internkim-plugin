#!/usr/bin/env python3
import pathlib

from deck_definitions import NO_SLIDE_SECTIONS
from office_result import OfficeArgumentParser, OfficeFailure, Result, run_command
from slide_viewer import strip_screen_slide_viewer


def main() -> Result:
    arguments = parse_arguments()
    delivered_path = pathlib.Path(arguments.delivered_path)
    source_path = pathlib.Path(arguments.source_path)
    source_text = strip_screen_slide_viewer(delivered_path.read_text(encoding="utf-8"))
    if "<section" not in source_text.casefold():
        raise OfficeFailure(NO_SLIDE_SECTIONS.issue("delivered HTML contains no slide sections", str(delivered_path)))
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(source_text.rstrip() + "\n", encoding="utf-8")
    return Result(summary=f"restored controller-free source {source_path}", output_path=str(source_path))


def parse_arguments():
    parser = OfficeArgumentParser(description="Recover controller-free slides.html from a delivered deck HTML.")
    parser.add_argument("delivered_path", help="the delivered deck .html")
    parser.add_argument("source_path", help="where to write slides.html")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
