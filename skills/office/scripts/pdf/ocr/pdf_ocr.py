from __future__ import annotations

from dataclasses import dataclass
import io
import json
from pathlib import Path
import subprocess
import tempfile

import pdfplumber
import pypdfium2

from pdf.pdf_definitions import OCR_DOWNLOAD_SIZE
from skill_runtime import create_dependency_environment, dependency_environment_path, install_requirements_if_needed


OCR_PATH = Path(__file__).resolve().parent
ENVIRONMENT_NAME = "office-ocr"
REQUIREMENTS_PATH = OCR_PATH / "ocr-requirements.txt"
OVERRIDES_PATH = OCR_PATH / "ocr-overrides.txt"
HELPER_PATH = OCR_PATH / "ocr_lines.py"
RENDER_SCALE = 3
FONT_SHARE_OF_LINE_BOX = 0.7


class OcrUnavailable(Exception):
    pass


@dataclass(frozen=True)
class OcrLine:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float

    def as_word(self) -> dict:
        return {"text": self.text, "x0": self.x0, "x1": self.x1, "top": self.top, "bottom": self.bottom, "size": (self.bottom - self.top) * FONT_SHARE_OF_LINE_BOX, "bold": False, "link": None}


def pages_without_words(data: bytes) -> list[int]:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return [number for number, page in enumerate(pdf.pages, start=1) if not page.extract_words()]


def read_pages_by_ocr(data: bytes, page_numbers: list[int]) -> dict[int, list[OcrLine]]:
    if not page_numbers:
        return {}
    python_path = ocr_python()
    with tempfile.TemporaryDirectory(prefix="office-ocr-") as directory:
        image_paths = render_pages(data, page_numbers, Path(directory))
        output_path = Path(directory) / "lines.json"
        completed = subprocess.run([str(python_path), str(HELPER_PATH), str(output_path), *map(str, image_paths)], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise OcrUnavailable(f"the OCR engine stopped: {last_line(completed.stderr)}")
        pages = json.loads(output_path.read_text(encoding="utf-8"))
    return {number: [line_in_points(line) for line in lines] for number, lines in zip(page_numbers, pages)}


def ocr_python() -> Path:
    environment_path = dependency_environment_path(ENVIRONMENT_NAME)
    python_path = environment_path / "bin" / "python"
    try:
        create_dependency_environment(python_path, environment_path)
        install_requirements_if_needed(python_path, REQUIREMENTS_PATH, environment_path, "--override", str(OVERRIDES_PATH))
    except (RuntimeError, OSError) as error:
        raise OcrUnavailable(f"installing the OCR engine ({OCR_DOWNLOAD_SIZE}) failed: {last_line(str(error))}") from error
    return python_path


def render_pages(data: bytes, page_numbers: list[int], directory: Path) -> list[Path]:
    document = pypdfium2.PdfDocument(data)
    try:
        paths = [directory / f"page-{number}.png" for number in page_numbers]
        for number, path in zip(page_numbers, paths):
            document[number - 1].render(scale=RENDER_SCALE, grayscale=True).to_pil().save(path)
    finally:
        document.close()
    return paths


def line_in_points(line: dict) -> OcrLine:
    return OcrLine(line["text"], line["x0"] / RENDER_SCALE, line["x1"] / RENDER_SCALE, line["top"] / RENDER_SCALE, line["bottom"] / RENDER_SCALE)


def last_line(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else "no message"
