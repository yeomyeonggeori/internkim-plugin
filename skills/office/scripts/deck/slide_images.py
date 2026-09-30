import pathlib


def slide_image_filename(deck_name: str, slide_number: int) -> str:
    return f"{deck_name}.{slide_number:03}.png"


def rendered_slide_image_paths(review_path: pathlib.Path, deck_name: str) -> list[pathlib.Path]:
    return sorted(review_path.glob(f"{deck_name}.[0-9][0-9][0-9].png"))
