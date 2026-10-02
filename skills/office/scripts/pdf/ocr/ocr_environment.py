from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from skill_runtime import PreparationFailed, create_dependency_environment, dependency_environment_path, install_requirements_if_needed, is_prepared


OCR_PATH = Path(__file__).resolve().parent
ENVIRONMENT_NAME = "office-ocr"
REQUIREMENTS_PATH = OCR_PATH / "ocr-requirements.txt"
OVERRIDE_OPTIONS = ("--override", str(OCR_PATH / "ocr-overrides.txt"))
HELPER_PATH = OCR_PATH / "ocr_lines.py"
ENGINE_READY_MARKER = ".engine-ready"
OCR_DOWNLOAD_SIZE = "about 150 MB"


def ocr_environment() -> Path:
    return dependency_environment_path(ENVIRONMENT_NAME)


def ocr_python() -> Path | None:
    environment = ocr_environment()
    if not is_prepared(environment, REQUIREMENTS_PATH, *OVERRIDE_OPTIONS) or not (environment / ENGINE_READY_MARKER).exists():
        return None
    return environment / "bin" / "python"


def prepare_ocr_environment() -> str:
    if ocr_python() is not None:
        return "found"
    environment = ocr_environment()
    python_path = environment / "bin" / "python"
    create_dependency_environment(python_path, environment)
    install_requirements_if_needed(python_path, REQUIREMENTS_PATH, environment, *OVERRIDE_OPTIONS)
    fetch_engine_models(python_path)
    (environment / ENGINE_READY_MARKER).write_text("ok\n", encoding="utf-8")
    return "prepared"


def fetch_engine_models(python_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="office-ocr-") as directory:
        completed = subprocess.run([str(python_path), str(HELPER_PATH), str(Path(directory) / "lines.json")], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise PreparationFailed(f"the OCR engine could not fetch its models: {completed.stderr.strip()[-400:]}")
