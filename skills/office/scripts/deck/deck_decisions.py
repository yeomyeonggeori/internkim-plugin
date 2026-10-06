from __future__ import annotations

import json

from host import script_host
from host.task_context import load_task_context, state_directory


def definition_questions(definition: dict) -> dict:
    return {
        name: script_host.choice_question(f"{definition.get('instructions', '')} {question.get('instructions', '')}".strip(), question.get("options") or {})
        for name, question in (definition.get("questions") or {}).items()
    }


def request_wordings() -> list[str]:
    context = load_task_context()
    return list(context.request) if context else []


def decided(state: dict, definition: dict) -> dict:
    try:
        answer = script_host.decide(state, definition_questions(definition))
    except (script_host.HostFailure, script_host.HostUnavailable) as failure:
        return {"choices": {}, "failure": str(failure), "costUSD": 0.0}
    choices = {name: {"option": given.get("choice", ""), "probabilities": given.get("probabilities") or {}} for name, given in (answer.get("answers") or {}).items()}
    return {"choices": choices, "model": answer.get("modelName", ""), "costUSD": script_host.cost_of(answer)}


def read_state(name: str) -> dict | None:
    directory = state_directory()
    path = directory / name if directory else None
    if path is None or not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    return document if isinstance(document, dict) else None


def write_state(name: str, document: dict) -> None:
    directory = state_directory()
    if directory is not None:
        (directory / name).write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
