from __future__ import annotations

from pathlib import Path

from PIL import Image as PillowImage


def fitted_size(path: Path, box_width: float, box_height: float) -> tuple[float, float]:
    with PillowImage.open(path) as image:
        width, height = image.size
    scale = min(box_width / width, box_height / height)
    return width * scale, height * scale


def sized_style(path: Path, box_width: float, box_height: float, unit: str) -> str:
    width, height = fitted_size(path, box_width, box_height)
    return f"width:{width:.2f}{unit};height:{height:.2f}{unit}"
