from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.office_commands import TOOLS
from core.office_result import SETUP_COMMAND, SETUP_FAILED, OfficeArgumentParser, Result
from pdf.ocr.ocr_environment import ocr_environment, prepare_ocr_environment
from render.renderer import NODE_MODULES, RendererUnavailable, prepare_renderer
from skill_runtime import PreparationFailed, environment_path, prepare_environment
from core.skill_paths import SCRIPTS_PATH


SETUP_SUMMARY = next(tool.summary for tool in TOOLS if tool.name == "setup")


@dataclass(frozen=True)
class SetupStep:
    name: str
    prepare: Callable[[], str]
    location: Path


def setup_result(arguments: list[str]) -> Result:
    finished = []
    parse_arguments(arguments)
    for step in setup_steps():
        try:
            state = step.prepare()
        except (PreparationFailed, RendererUnavailable) as reason:
            issue = SETUP_FAILED.issue(f"{step.name} could not be prepared: {reason}", step.name)
            return Result(summary=issue.message, issues=(issue,), details=setup_details(finished))
        finished.append({"name": step.name, "state": state, "path": str(step.location)})
    return Result(summary=f"office is ready in {SCRIPTS_PATH.parent}", details=setup_details(finished))


def setup_details(finished: list[dict]) -> dict:
    return {"steps": finished}


def setup_steps() -> list[SetupStep]:
    return [
        SetupStep("python environment", prepare_python_environment, environment_path(SCRIPTS_PATH)),
        SetupStep("renderer packages", prepare_renderer, NODE_MODULES),
        SetupStep("ocr engine", prepare_ocr_environment, ocr_environment()),
    ]


def prepare_python_environment() -> str:
    return "prepared" if prepare_environment(SCRIPTS_PATH) else "found"


def parse_arguments(arguments: list[str]):
    parser = OfficeArgumentParser(prog=SETUP_COMMAND, description=SETUP_SUMMARY[0].upper() + SETUP_SUMMARY[1:] + ".")
    return parser.parse_args(arguments)
