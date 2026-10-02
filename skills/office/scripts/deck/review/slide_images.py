from __future__ import annotations

import pathlib


def rendered_slide_image_paths(review_path: pathlib.Path, deck_name: str) -> list[pathlib.Path]:
    return sorted(review_path.glob(f"{deck_name}.[0-9][0-9][0-9].png"))
