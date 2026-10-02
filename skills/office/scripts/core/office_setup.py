from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Callable

from core.office_result import SETUP_COMMAND, SETUP_FAILED, OfficeArgumentParser, Result
from fonts.registry import UNPACKED_FONT_DIRECTORY
from pdf.ocr.ocr_environment import OCR_DOWNLOAD_SIZE, ocr_environment, prepare_ocr_environment
from render.renderer import NODE_MODULES, RendererUnavailable, prepare_renderer
from skill_runtime import PreparationFailed, environment_path, prepare_environment


SCRIPTS_PATH = Path(__file__).resolve().parents[1]
FONT_PREPARATION = "from fonts.registry import prepare_bundled_fonts; print(prepare_bundled_fonts())"
SETUP_SUMMARY = "install the Python environment, the renderer's packages and the unpacked fonts into the skill, and with --with-ocr the OCR engine; every other command only reads them"


@dataclass(frozen=True)
class SetupStep:
    name: str
    prepare: Callable[[], str]
    location: Path


def setup_result(arguments: list[str]) -> Result:
    parsed = parse_arguments(arguments)
    finished = []
    for step in setup_steps(parsed.with_ocr):
        try:
            state = step.prepare()
        except (PreparationFailed, RendererUnavailable) as reason:
            issue = SETUP_FAILED.issue(f"{step.name} could not be prepared: {reason}", step.name)
            return Result(summary=issue.message, issues=(issue,), details=setup_details(finished))
        finished.append({"name": step.name, "state": state, "path": str(step.location)})
    return Result(summary=f"office is ready in {SCRIPTS_PATH.parent}", details=setup_details(finished))


def setup_details(finished: list[dict]) -> dict:
    return {"steps": finished}


def setup_steps(with_ocr: bool) -> list[SetupStep]:
    steps = [
        SetupStep("python environment", prepare_python_environment, environment_path(SCRIPTS_PATH)),
        SetupStep("renderer packages", prepare_renderer, NODE_MODULES),
        SetupStep("fonts", prepare_fonts, UNPACKED_FONT_DIRECTORY),
    ]
    if with_ocr:
        steps.append(SetupStep("ocr engine", prepare_ocr_environment, ocr_environment()))
    return steps


def prepare_python_environment() -> str:
    return "prepared" if prepare_environment(SCRIPTS_PATH) else "found"


def prepare_fonts() -> str:
    environment = {**os.environ, "PYTHONPATH": str(SCRIPTS_PATH)}
    python_path = environment_path(SCRIPTS_PATH) / "bin" / "python"
    completed = subprocess.run([str(python_path), "-c", FONT_PREPARATION], capture_output=True, text=True, env=environment, check=False)
    if completed.returncode != 0:
        raise PreparationFailed(completed.stderr.strip()[-400:] or "unpacking the bundled fonts stopped without a message")
    return completed.stdout.strip()


def parse_arguments(arguments: list[str]):
    parser = OfficeArgumentParser(prog=SETUP_COMMAND, description=SETUP_SUMMARY[0].upper() + SETUP_SUMMARY[1:] + ".")
    parser.add_argument("--with-ocr", action="store_true", help=f"also prepare the OCR engine that pdf read --ocr and convert --ocr use, {OCR_DOWNLOAD_SIZE}")
    return parser.parse_args(arguments)
