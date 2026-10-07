from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import errno
import json
import logging
import os
from typing import Callable

from core.source_snapshot import keep_provenance


ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class IssueKind:
    code: str
    severity: str
    meaning: str
    suggestion: str
    suggestion_applies_fix: bool = False

    def issue(self, message: str, location: str | None = None, suggestion: str | None = None, fix: tuple[dict, ...] | list[dict] = ()) -> "Issue":
        if suggestion is None and self.suggestion_applies_fix and not fix:
            raise TypeError(f"{self.code}: the default suggestion says to apply fix, so an issue without fix needs a suggestion of its own")
        return Issue(self, message, location, self.default_suggestion() if suggestion is None else suggestion, tuple(fix))

    def default_suggestion(self) -> str:
        return self.suggestion.replace("{guide}", guide_reference())


@dataclass(frozen=True)
class Issue:
    kind: IssueKind
    message: str
    location: str | None
    suggestion: str
    fix: tuple[dict, ...] = ()

    def __post_init__(self):
        if not isinstance(self.suggestion, str):
            raise TypeError(f"{self.kind.code}: a suggestion is text, not {type(self.suggestion).__name__}; operations go in fix")
        if not all(isinstance(operation, dict) and isinstance(operation.get("op"), str) for operation in self.fix):
            raise TypeError(f"{self.kind.code}: fix holds operations, each an object with an op")

    def to_json(self) -> dict:
        return {
            "code": self.kind.code,
            "severity": self.kind.severity,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion,
            "fix": list(self.fix),
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


class OfficeFailure(Exception):
    def __init__(self, *issues: Issue):
        super().__init__("; ".join(issue.message for issue in issues))
        self.issues = issues


DOCUMENTS_FOLDER = "~/documents"
SETUP_COMMAND = "office setup"
SETUP_SUGGESTION = f"run {SETUP_COMMAND} once; it needs uv, bun or node 18, and network access, and InternKim's host install runs it"

VALUE_FILL_IN = "<value>"
LABEL_FILL_IN = "<label>"
SERIES_NAME_FILL_IN = "<series name>"
NUMBER_FILL_IN = "<number>"
FILL_INS = (VALUE_FILL_IN, LABEL_FILL_IN, SERIES_NAME_FILL_IN, NUMBER_FILL_IN)

INVALID_ARGUMENTS = IssueKind("INVALID_ARGUMENTS", ERROR, "the command line does not match the command's arguments", "run the command with --help and pass the arguments it lists")
UNKNOWN_COMMAND = IssueKind("UNKNOWN_COMMAND", ERROR, "no office command has this format and verb", "run office --help for the command list")
INPUT_NOT_FOUND = IssueKind("INPUT_NOT_FOUND", ERROR, "an input file or directory does not exist", "check the path, or write the file first")
WRONG_INPUT_FORMAT = IssueKind("WRONG_INPUT_FORMAT", ERROR, "the input file is not the kind this command reads", "run the office command that reads this kind of file; office --help lists them")
FILE_DAMAGED = IssueKind("FILE_DAMAGED", ERROR, "the file is the right kind but its structure is broken, as when a download or copy stopped early, so it cannot be read", "ask the user to send the complete file again; no office command can read this one")
PDF_PASSWORD_REQUIRED = IssueKind("PDF_PASSWORD_REQUIRED", ERROR, "the PDF needs a password to open", "ask the user for the password and rerun with --password <password>; never guess one")
INVALID_JSON = IssueKind("INVALID_JSON", ERROR, "an input file is not valid JSON", "fix the JSON syntax at the reported line and column")
PERMISSION_DENIED = IssueKind("PERMISSION_DENIED", ERROR, "the command may not read or write this path", f"write the output under {DOCUMENTS_FOLDER} instead")
PATH_UNUSABLE = IssueKind("PATH_UNUSABLE", ERROR, "a path cannot be written or read as given: it names a folder where a file belongs, runs through a file as if it were a folder, is too long, or lies on a read-only disk", f"pass a file path inside a writable folder, such as {DOCUMENTS_FOLDER}/<name>")
WRONG_OUTPUT_FORMAT = IssueKind("WRONG_OUTPUT_FORMAT", ERROR, "the output path's extension names a format this command does not write", "name the output with the extension the message names")
DEPENDENCIES_UNAVAILABLE = IssueKind("DEPENDENCIES_UNAVAILABLE", ERROR, "a piece office setup prepares, such as the Python environment or the OCR engine, is missing, so nothing ran", SETUP_SUGGESTION)
SETUP_FAILED = IssueKind("SETUP_FAILED", ERROR, "office setup could not prepare a piece the skill needs", "fix what the message names, such as putting uv or bun on PATH or allowing network access, then rerun office setup")
BOLD_FONT_UNAVAILABLE = IssueKind("BOLD_FONT_UNAVAILABLE", WARNING, "no bold face was found beside the font file passed as the font path, so headings render without bold", "put the Bold file beside it, named like the regular one with Bold, or leave the font path out to use a bundled family")
MISSING_FIELD = IssueKind("MISSING_FIELD", ERROR, "a required field is absent or empty", "add the field; {guide} lists every field")
UNKNOWN_FIELD = IssueKind("UNKNOWN_FIELD", ERROR, "a field is not part of this structure", "remove the field or correct its spelling; {guide} lists every field")
WRONG_TYPE = IssueKind("WRONG_TYPE", ERROR, "a field holds the wrong kind of value", "give the field the type {guide} names")
INVALID_VALUE = IssueKind("INVALID_VALUE", ERROR, "a field's value is outside what the command accepts", "use a value {guide} allows")
LIBRARY_WARNING = IssueKind("LIBRARY_WARNING", WARNING, "a library the command uses reported a problem it worked around, such as a PDF whose cross-reference table points at the wrong place", "compare the result with the input; if part of it is missing, ask the user for the complete file")

COMMAND_ISSUE_KINDS = (
    INVALID_ARGUMENTS,
    UNKNOWN_COMMAND,
    INPUT_NOT_FOUND,
    WRONG_INPUT_FORMAT,
    PDF_PASSWORD_REQUIRED,
    FILE_DAMAGED,
    INVALID_JSON,
    PERMISSION_DENIED,
    PATH_UNUSABLE,
    WRONG_OUTPUT_FORMAT,
    DEPENDENCIES_UNAVAILABLE,
    SETUP_FAILED,
    BOLD_FONT_UNAVAILABLE,
    MISSING_FIELD,
    UNKNOWN_FIELD,
    WRONG_TYPE,
    INVALID_VALUE,
    LIBRARY_WARNING,
)


class OfficeArgumentParser(argparse.ArgumentParser):
    def __init__(self, **options):
        options.setdefault("prog", os.environ.get("OFFICE_COMMAND") or None)
        super().__init__(**options)

    def error(self, message):
        raise OfficeFailure(INVALID_ARGUMENTS.issue(f"{self.prog}: {message}", suggestion=f"run {self.prog} --help"))

    def parse_args(self, args=None, namespace=None):
        parsed, unrecognized = self.parse_known_args(args, namespace)
        if unrecognized:
            self.reject_unrecognized(unrecognized)
        return parsed

    def reject_unrecognized(self, unrecognized: list[str]):
        flag, meant = self.closest_flag(unrecognized)
        suggestion = f"did you mean {meant}? rerun with {meant}" if meant else f"run {self.prog} --help"
        raise OfficeFailure(INVALID_ARGUMENTS.issue(f"{self.prog}: unrecognized arguments: {' '.join(unrecognized)}", flag, suggestion))

    def closest_flag(self, unrecognized: list[str]) -> tuple[str | None, str | None]:
        from core.office_schema import closest_name

        flags = [option for option in self._option_string_actions if option.startswith("--")]
        for written in unrecognized:
            if not written.startswith("--"):
                continue
            meant = closest_name(written.split("=", 1)[0], flags)
            if meant:
                return written, meant
        return None, None


def guide_reference() -> str:
    return " ".join(["office guide", *os.environ.get("OFFICE_ROUTE", "").split()])


def run_command(command: Callable[[], Result]) -> int:
    return print_result(command_result(command))


def print_result(result: Result) -> int:
    print(json.dumps(result.to_json(), ensure_ascii=False, indent=2))
    return 1 if result.status == "error" else 0


class LibraryWarnings(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages_by_library: dict[str, list[str]] = {}

    def emit(self, record: logging.LogRecord) -> None:
        messages = self.messages_by_library.setdefault(record.name.split(".")[0], [])
        if record.getMessage() not in messages:
            messages.append(record.getMessage())

    def issues(self) -> tuple[Issue, ...]:
        return tuple(LIBRARY_WARNING.issue(f"{library} reported: {'; '.join(messages)}") for library, messages in self.messages_by_library.items())


def command_result(command: Callable[[], Result]) -> Result:
    library_warnings = LibraryWarnings()
    root_logger = logging.getLogger()
    root_logger.addHandler(library_warnings)
    logging.captureWarnings(True)
    try:
        result = attempted_result(command)
    finally:
        root_logger.removeHandler(library_warnings)
    if result.status == "error":
        return result
    keep_provenance(result.output_path)
    from delivery.finish import finished

    return finished(replace(result, issues=result.issues + library_warnings.issues()))


def resolved_from(path: object) -> str:
    if not isinstance(path, str) or os.path.isabs(os.path.expanduser(path)):
        return ""
    return f" (looked for {os.path.abspath(os.path.expanduser(path))}, relative to the working directory {os.getcwd()})"


def attempted_result(command: Callable[[], Result]) -> Result:
    try:
        return command()
    except OfficeFailure as failure:
        return failure_result(failure.issues)
    except FileNotFoundError as error:
        return failure_result((INPUT_NOT_FOUND.issue(f"{error.filename or error}: no such file or directory{resolved_from(error.filename)}", location=error.filename),))
    except PermissionError as error:
        return failure_result((PERMISSION_DENIED.issue(f"{error.filename or error}: permission denied", location=error.filename),))
    except OSError as error:
        return failure_result((path_unusable_issue(error),))


PATH_PROBLEMS = {
    errno.EISDIR: ("is a folder, not a file", "name a file inside that folder, such as {path}/<name>"),
    errno.ENOTDIR: ("runs through a file as if it were a folder", "pick a folder that exists as a folder, such as " + DOCUMENTS_FOLDER),
    errno.EEXIST: ("is a file where a folder is needed", "pick a folder that exists as a folder, such as " + DOCUMENTS_FOLDER),
    errno.ENAMETOOLONG: ("is longer than the file system allows", "shorten the file name"),
    errno.EROFS: ("lies on a read-only disk", f"write the output under {DOCUMENTS_FOLDER} instead"),
}


def path_unusable_issue(error: OSError) -> Issue:
    path = error.filename or ""
    problem, suggestion = PATH_PROBLEMS.get(error.errno, (error.strerror or type(error).__name__, None))
    return PATH_UNUSABLE.issue(f"{path or 'a path'}: {problem}", location=path or None, suggestion=suggestion.format(path=path.rstrip("/")) if suggestion else None)


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
