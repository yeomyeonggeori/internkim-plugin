#!/usr/bin/env python3
import pathlib
import sys

from slide_viewer import strip_screen_slide_viewer


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: restore_source.py <delivered.html> <slides.html>", file=sys.stderr)
        return 2
    delivered_path = pathlib.Path(sys.argv[1])
    source_path = pathlib.Path(sys.argv[2])
    source_text = strip_screen_slide_viewer(delivered_path.read_text(encoding="utf-8"))
    if "<section" not in source_text.casefold():
        print("Error: delivered HTML contains no slide sections", file=sys.stderr)
        return 1
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(source_text.rstrip() + "\n", encoding="utf-8")
    print(f"Restored controller-free source: {source_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
