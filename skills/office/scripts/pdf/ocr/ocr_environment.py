from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from skill_runtime import PreparationFailed, environment_path, is_prepared, prepare_environment


OCR_PATH = Path(__file__).resolve().parent
HELPER_PATH = OCR_PATH / "ocr_lines.py"
ENGINE_READY_MARKER = "engine-models.ready"


def ocr_environment() -> Path:
    return environment_path(OCR_PATH)


def ocr_python() -> Path | None:
    if not is_prepared(OCR_PATH) or not (ocr_environment() / ENGINE_READY_MARKER).exists():
        return None
    return ocr_environment() / "bin" / "python"


def prepare_ocr_environment() -> str:
    if ocr_python() is not None:
        return "found"
    prepare_environment(OCR_PATH)
    fetch_engine_models(ocr_environment() / "bin" / "python")
    (ocr_environment() / ENGINE_READY_MARKER).write_text("ok\n", encoding="utf-8")
    return "prepared"


def fetch_engine_models(python_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="office-ocr-") as directory:
        completed = subprocess.run([str(python_path), str(HELPER_PATH), str(Path(directory) / "lines.json")], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise PreparationFailed(f"the OCR engine could not fetch its models: {completed.stderr.strip()[-400:]}")
