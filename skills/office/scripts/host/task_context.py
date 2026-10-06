from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
import os
from pathlib import Path


CONTEXT_VARIABLE = "SKILL_TASK_CONTEXT"
STATE_DIRECTORY_NAME = "office"


@dataclass(frozen=True)
class Attachment:
    name: str
    path: str = ""
    text: str = ""
    is_current: bool = False


@dataclass(frozen=True)
class Record:
    tool: str
    input: dict = field(default_factory=dict)
    result: object = None
    files: tuple = ()

    def file_named(self, name: str) -> str:
        return next((file["path"] for file in self.files if file.get("name") == name or Path(file.get("path", "")).name == name), "")


@dataclass(frozen=True)
class TaskContext:
    requester_name: str = ""
    requester_email: str = ""
    today: date | None = None
    request: tuple = ()
    attachments: tuple = ()
    records: tuple = ()

    def records_of(self, tool: str) -> list[Record]:
        return [record for record in self.records if record.tool == tool]


def context_path() -> Path | None:
    path = os.environ.get(CONTEXT_VARIABLE, "").strip()
    return Path(path) if path else None


def load_task_context() -> TaskContext | None:
    path = context_path()
    if path is None or not path.is_file():
        return None
    return parsed_context(json.loads(path.read_text(encoding="utf-8")))


def parsed_context(document: dict) -> TaskContext:
    requester = document.get("requester") or {}
    return TaskContext(
        requester_name=str(requester.get("name") or ""),
        requester_email=str(requester.get("email") or ""),
        today=date.fromisoformat(document["today"]) if document.get("today") else None,
        request=tuple(str(text) for text in document.get("request") or ()),
        attachments=tuple(parsed_attachment(item) for item in document.get("attachments") or () if isinstance(item, dict)),
        records=tuple(parsed_record(item) for item in document.get("records") or () if isinstance(item, dict)),
    )


def parsed_attachment(item: dict) -> Attachment:
    return Attachment(name=str(item.get("name") or ""), path=str(item.get("path") or ""), text=str(item.get("text") or ""), is_current=item.get("current") is True)


def parsed_record(item: dict) -> Record:
    files = tuple(file for file in item.get("files") or () if isinstance(file, dict) and file.get("path"))
    tool_input = item.get("input") if isinstance(item.get("input"), dict) else {}
    return Record(tool=str(item.get("tool") or ""), input=tool_input, result=item.get("result"), files=files)


def state_directory() -> Path | None:
    path = context_path()
    if path is None:
        return None
    directory = path.parent / STATE_DIRECTORY_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory
