from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Callable

from core.office_result import SETUP_COMMAND, SETUP_FAILED, OfficeArgumentParser, Result
from pdf.ocr.ocr_environment import OCR_DOWNLOAD_SIZE, ocr_environment, prepare_ocr_environment
from render.renderer import RendererUnavailable, package_directory, prepare_renderer
from skill_runtime import PreparationFailed, dependency_environment_path, prepare_requirements, skill_cache_path


SKILL_NAME = "office"
SCRIPTS_PATH = Path(__file__).resolve().parents[1]
FONT_PREPARATION = "from fonts.registry import prepare_bundled_fonts; print(prepare_bundled_fonts())"
SETUP_SUMMARY = "prepare the Python environment, the renderer's packages and the unpacked fonts, and with --with-ocr the OCR engine; every other command only reads them"


@dataclass(frozen=True)
class SetupStep:
    name: str
    prepare: Callable[[], str]
    location: Callable[[], Path]


def setup_result(arguments: list[str]) -> Result:
    parsed = parse_arguments(arguments)
    finished = []
    for step in setup_steps(parsed.with_ocr):
        try:
            state = step.prepare()
        except (PreparationFailed, RendererUnavailable) as reason:
            issue = SETUP_FAILED.issue(f"{step.name} could not be prepared: {reason}", step.name)
            return Result(summary=issue.message, issues=(issue,), details=setup_details(finished))
        finished.append({"name": step.name, "state": state, "path": str(step.location())})
    return Result(summary=f"office is ready in {skill_cache_path(os.environ)}", details=setup_details(finished))


def setup_details(finished: list[dict]) -> dict:
    return {"cacheHome": str(skill_cache_path(os.environ)), "steps": finished}


def setup_steps(with_ocr: bool) -> list[SetupStep]:
    steps = [
        SetupStep("python environment", prepare_python_environment, lambda: dependency_environment_path(SKILL_NAME)),
        SetupStep("renderer packages", prepare_renderer, package_directory),
        SetupStep("fonts", prepare_fonts, lambda: skill_cache_path(os.environ) / "fonts" / "bundled"),
    ]
    if with_ocr:
        steps.append(SetupStep("ocr engine", prepare_ocr_environment, ocr_environment))
    return steps


def prepare_python_environment() -> str:
    return "prepared" if prepare_requirements(SKILL_NAME) else "found"


def prepare_fonts() -> str:
    environment = {**os.environ, "PYTHONPATH": str(SCRIPTS_PATH)}
    python_path = dependency_environment_path(SKILL_NAME) / "bin" / "python"
    completed = subprocess.run([str(python_path), "-c", FONT_PREPARATION], capture_output=True, text=True, env=environment, check=False)
    if completed.returncode != 0:
        raise PreparationFailed(completed.stderr.strip()[-400:] or "unpacking the bundled fonts stopped without a message")
    return completed.stdout.strip()


def parse_arguments(arguments: list[str]):
    parser = OfficeArgumentParser(prog=SETUP_COMMAND, description=SETUP_SUMMARY[0].upper() + SETUP_SUMMARY[1:] + ".")
    parser.add_argument("--with-ocr", action="store_true", help=f"also prepare the OCR engine that pdf read --ocr and convert --ocr use, {OCR_DOWNLOAD_SIZE}")
    return parser.parse_args(arguments)
