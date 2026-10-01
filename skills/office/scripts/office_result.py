from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from typing import Callable


ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class IssueKind:
    code: str
    severity: str
    meaning: str
    suggestion: str

    def issue(self, message: str, location: str | None = None, suggestion: object = None) -> "Issue":
        return Issue(self, message, location, self.default_suggestion() if suggestion is None else suggestion)

    def default_suggestion(self) -> str:
        return self.suggestion.replace("{guide}", guide_reference())


@dataclass(frozen=True)
class Issue:
    kind: IssueKind
    message: str
    location: str | None
    suggestion: object

    def to_json(self) -> dict:
        return {
            "code": self.kind.code,
            "severity": self.kind.severity,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion,
        }


@dataclass(frozen=True)
class Result:
    summary: str
    output_path: str | None = None
    issues: tuple[Issue, ...] = ()
    details: dict | None = None

    @property
    def status(self) -> str:
        severities = {issue.kind.severity for issue in self.issues}
        if ERROR in severities:
            return "error"
        if WARNING in severities:
            return "warning"
        return "ok"

    def to_json(self) -> dict:
        envelope = {
            "status": self.status,
            "summary": self.summary,
            "outputPath": self.output_path,
            "issues": [issue.to_json() for issue in self.issues],
        }
        if self.details is not None:
            envelope["details"] = self.details
        return envelope


def issue_from_json(document: dict, kinds: tuple[IssueKind, ...]) -> Issue:
    kind = next(kind for kind in kinds if kind.code == document["code"])
    return Issue(kind, document["message"], document["location"], document["suggestion"])


class OfficeFailure(Exception):
    def __init__(self, *issues: Issue):
        super().__init__("; ".join(issue.message for issue in issues))
        self.issues = issues


INVALID_ARGUMENTS = IssueKind("INVALID_ARGUMENTS", ERROR, "the command line does not match the command's arguments", "run the command with --help and pass the arguments it lists")
UNKNOWN_COMMAND = IssueKind("UNKNOWN_COMMAND", ERROR, "no office command has this format and verb", "run office --help for the command list")
INPUT_NOT_FOUND = IssueKind("INPUT_NOT_FOUND", ERROR, "an input file or directory does not exist", "check the path, or write the file first")
WRONG_INPUT_FORMAT = IssueKind("WRONG_INPUT_FORMAT", ERROR, "the input file is not the kind this command reads", "run the command the suggestion names for this kind of file")
PDF_PASSWORD_REQUIRED = IssueKind("PDF_PASSWORD_REQUIRED", ERROR, "the PDF needs a password to open", "ask the user for the password and rerun with --password <password>; never guess one")
NO_FILE_FOUND = IssueKind("NO_FILE_FOUND", ERROR, "no path was given and ~/documents holds no file of this kind", "pass the file path explicitly")
INVALID_JSON = IssueKind("INVALID_JSON", ERROR, "an input file is not valid JSON", "fix the JSON syntax at the reported line and column")
PERMISSION_DENIED = IssueKind("PERMISSION_DENIED", ERROR, "the command may not read or write this path", "write the output under ~/documents instead")
DEPENDENCIES_UNAVAILABLE = IssueKind("DEPENDENCIES_UNAVAILABLE", ERROR, "the office Python packages could not be installed", "check network access and that uv is on PATH, then rerun")
KOREAN_FONT_UNAVAILABLE = IssueKind("KOREAN_FONT_UNAVAILABLE", ERROR, "the text needs a Korean-capable font and none is installed", "install Nanum Gothic or Noto Sans CJK, or pass a font path")
BOLD_FONT_UNAVAILABLE = IssueKind("BOLD_FONT_UNAVAILABLE", WARNING, "no bold face was found beside the Korean font, so headings render without bold", "install fonts-nanum or fonts-noto-cjk, which carry a bold face, or pass a font path that has a Bold file beside it")
MISSING_FIELD = IssueKind("MISSING_FIELD", ERROR, "a required field is absent or empty", "add the field; {guide} lists every field")
UNKNOWN_FIELD = IssueKind("UNKNOWN_FIELD", ERROR, "a field is not part of this structure", "remove the field or correct its spelling; {guide} lists every field")
WRONG_TYPE = IssueKind("WRONG_TYPE", ERROR, "a field holds the wrong kind of value", "give the field the type {guide} names")
INVALID_VALUE = IssueKind("INVALID_VALUE", ERROR, "a field's value is outside what the command accepts", "use a value {guide} allows")

COMMAND_ISSUE_KINDS = (
    INVALID_ARGUMENTS,
    UNKNOWN_COMMAND,
    INPUT_NOT_FOUND,
    WRONG_INPUT_FORMAT,
    PDF_PASSWORD_REQUIRED,
    NO_FILE_FOUND,
    INVALID_JSON,
    PERMISSION_DENIED,
    DEPENDENCIES_UNAVAILABLE,
    KOREAN_FONT_UNAVAILABLE,
    BOLD_FONT_UNAVAILABLE,
    MISSING_FIELD,
    UNKNOWN_FIELD,
    WRONG_TYPE,
    INVALID_VALUE,
)


class OfficeArgumentParser(argparse.ArgumentParser):
    def __init__(self, **options):
        options.setdefault("prog", os.environ.get("OFFICE_COMMAND") or None)
        super().__init__(**options)

    def error(self, message):
        raise OfficeFailure(INVALID_ARGUMENTS.issue(f"{self.prog}: {message}", suggestion=f"run {self.prog} --help"))


def guide_reference() -> str:
    command_words = os.environ.get("OFFICE_COMMAND", "").split()[1:]
    return " ".join(["office guide", *command_words])


def run_command(command: Callable[[], Result]) -> int:
    return print_result(command_result(command))


def print_result(result: Result) -> int:
    print(json.dumps(result.to_json(), ensure_ascii=False, indent=2))
    return 1 if result.status == "error" else 0


def command_result(command: Callable[[], Result]) -> Result:
    try:
        return command()
    except OfficeFailure as failure:
        return failure_result(failure.issues)
    except FileNotFoundError as error:
        return failure_result((INPUT_NOT_FOUND.issue(f"{error.filename or error}: no such file or directory", location=error.filename),))
    except PermissionError as error:
        return failure_result((PERMISSION_DENIED.issue(f"{error.filename or error}: permission denied", location=error.filename),))


def failure_result(issues: tuple[Issue, ...]) -> Result:
    if len(issues) == 1:
        return Result(summary=issues[0].message, issues=issues)
    return Result(summary=f"{len(issues)} problems, the first: {issues[0].message}", issues=issues)


def read_json_file(path: str) -> object:
    with open(os.path.expanduser(path), "r", encoding="utf-8") as json_file:
        try:
            return json.load(json_file)
        except json.JSONDecodeError as error:
            raise OfficeFailure(INVALID_JSON.issue(f"{path} is not valid JSON: {error.msg}", location=f"{path}:{error.lineno}:{error.colno}")) from error
