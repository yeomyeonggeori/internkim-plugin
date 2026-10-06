from __future__ import annotations

import json
import os
from pathlib import Path


CONTEXT_VARIABLE = "SKILL_TASK_CONTEXT"
CONTEXT_FILE_NAME = "task-context.json"
COMPANY_PROFILE_FILE_NAME = "company-profile.json"


def company_record(language: str, profile_path: Path | str) -> dict:
    return {"tool": "company_info_get", "input": {"language": language}, "result": {}, "files": [{"name": COMPANY_PROFILE_FILE_NAME, "path": str(profile_path)}]}


def register_record(document_number: str | None) -> dict:
    return {"tool": "company_document_register", "input": {}, "result": {"documentID": "d", "documentNumber": document_number}}


def task_context(directory: Path | str, facts: dict) -> dict:
    requester = facts.get("requester") or {}
    records = [company_record(language, profile_file(directory, language, profile)) for language, profile in (facts.get("company") or {}).items()]
    records += [register_record(document.get("documentNumber")) for document in facts.get("registeredDocuments") or ()]
    return {
        "requester": {"name": requester.get("name", ""), "email": requester.get("email", "")},
        "today": facts.get("today", ""),
        "request": list(facts.get("request") or ()),
        "attachments": [attachment_entry(attachment) for attachment in facts.get("attachments") or ()],
        "records": records + list(facts.get("records") or ()),
    }


def attachment_entry(attachment: dict) -> dict:
    return {"name": attachment.get("name", ""), "path": attachment.get("path", ""), "text": attachment.get("text", ""), "current": attachment.get("current", True)}


def profile_file(directory: Path | str, language: str, profile: dict | str) -> str:
    if not isinstance(profile, dict):
        return str(profile)
    profile_directory = Path(directory) / f"company-{language}"
    profile_directory.mkdir(parents=True, exist_ok=True)
    path = profile_directory / COMPANY_PROFILE_FILE_NAME
    path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    return str(path)


def write_task_context(directory: Path | str, facts: dict) -> Path:
    path = Path(directory) / "task" / CONTEXT_FILE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(task_context(directory, facts), ensure_ascii=False), encoding="utf-8")
    return path


def environment_with_context(context_path: Path | str | None) -> dict:
    environment = {name: value for name, value in os.environ.items() if name != CONTEXT_VARIABLE}
    return environment | ({CONTEXT_VARIABLE: str(context_path)} if context_path else {})


def write_context_at(path: Path | str, facts: dict) -> Path:
    context_path = Path(path)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(json.dumps(task_context(context_path.parent, facts), ensure_ascii=False), encoding="utf-8")
    return context_path
