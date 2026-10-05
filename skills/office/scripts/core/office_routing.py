from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from core.office_commands import (
    EVERY_KIND,
    FLAGS_BY_NAME,
    KINDS,
    Route,
    Verb,
    find_conversion,
    find_route,
    normalized_extension,
    route_label,
    verb_routes,
)
from core.office_inputs import DAMAGED_PACKAGE, DOCX, LEGACY_OFFICE, OTHER, PDF, PPTX, XLSB, XLSX, detected_kind, redirect_suggestion
from core.office_result import FILE_DAMAGED, INVALID_ARGUMENTS, WRONG_INPUT_FORMAT, OfficeFailure
from core.office_schema import closest_name, guess_text
from schemas.schema_document import is_schema_reference


DESIGN_FILE_NAME = "DESIGN.md"
OUTLINE_FILE_NAME = "outline.json"
FORM_NAME = re.compile(r"[a-z]+/[a-z0-9]+(?:-[a-z0-9]+)*")
SNIFFED_KINDS = {kind.name for kind in (DOCX, XLSX, PPTX, PDF)}
SPEC_OUTPUT_KINDS = ("docx", "xlsx", "pdf")


@dataclass(frozen=True)
class Call:
    verb: Verb
    route: Route
    module: str
    needs_packages: bool


def positional_arguments(arguments: list[str]) -> list[str]:
    positionals = []
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token.startswith("-") and token != "-":
            flag = FLAGS_BY_NAME.get(token.split("=", 1)[0])
            if flag is not None and flag.takes_value and "=" not in token:
                index += 1
        else:
            positionals.append(token)
        index += 1
    return positionals


def resolve_call(verb: Verb, arguments: list[str]) -> Call:
    positionals = dict(zip(verb.positionals, positional_arguments(arguments)))
    if verb.subject is None:
        return whole_verb_call(verb)
    missing = [positional for positional in verb.positionals if positional not in positionals]
    if missing:
        raise OfficeFailure(INVALID_ARGUMENTS.issue(f"office {verb.name} needs its <{missing[0]}>", suggestion=f"office {verb.usage}"))
    if verb.name == "convert":
        return conversion_call(verb, positionals)
    route = subject_route(verb.name, positionals[verb.subject], positionals.get("output"))
    if route is None:
        raise OfficeFailure(unrouted_issue(verb, positionals[verb.subject]))
    return Call(verb, route, route.module, route.needs_packages)


def whole_verb_call(verb: Verb) -> Call:
    route = find_route(verb.name, EVERY_KIND)
    return Call(verb, route, route.module, route.needs_packages)


def conversion_call(verb: Verb, positionals: dict[str, str]) -> Call:
    route = find_route(verb.name, EVERY_KIND)
    output = positionals.get("output", "")
    conversion = find_conversion(normalized_extension(Path(positionals["input"]).suffix), normalized_extension(Path(output).suffix))
    if conversion is None:
        return Call(verb, route, route.module, route.needs_packages)
    return Call(verb, route, conversion.module, conversion.needs_packages)


def subject_route(verb_name: str, subject: str, output: str | None) -> Route | None:
    path = Path(subject).expanduser()
    sniffed = sniffed_kind(path)
    if sniffed is not None:
        route = find_route(verb_name, sniffed)
        return route if route is not None and route.reads_its_kind else None
    kind = named_kind(verb_name, subject, output)
    return find_route(verb_name, kind) if kind else None


def named_kind(verb_name: str, subject: str, output: str | None) -> str | None:
    path = Path(subject).expanduser()
    if verb_name == "merge" and is_schema_reference(subject):
        return "schema"
    if verb_name == "merge" and FORM_NAME.fullmatch(subject) and not path.exists():
        return "form"
    if path.is_dir() or (verb_name == "check" and path.name in (DESIGN_FILE_NAME, OUTLINE_FILE_NAME)):
        return "slides"
    extension = path.suffix.lower()
    if extension == ".json":
        return json_kind(verb_name, output)
    return next((kind.name for kind in KINDS if extension in kind.extensions and kind.name != "form"), None)


def sniffed_kind(path: Path) -> str | None:
    if not path.is_file() or path.stat().st_size == 0:
        return None
    kind = detected_kind(str(path)).name
    return kind if kind in SNIFFED_KINDS else None


def json_kind(verb_name: str, output: str | None) -> str | None:
    if verb_name == "check":
        return "form"
    if verb_name != "create" or output is None:
        return None
    output_extension = Path(output).suffix.lower()
    return next((kind.name for kind in KINDS if kind.name in SPEC_OUTPUT_KINDS and output_extension in kind.extensions), None)


def unrouted_issue(verb: Verb, subject: str):
    accepted = ", ".join(dict.fromkeys(route_label(route) for route in verb_routes(verb.name)))
    path = Path(subject).expanduser()
    if not path.is_file() or path.stat().st_size == 0:
        return absent_subject_issue(verb, subject, accepted)
    actual = detected_kind(str(path))
    if actual == DAMAGED_PACKAGE:
        return FILE_DAMAGED.issue(f"{subject} is {actual.description}", subject)
    described = f"its content is {OTHER.description}" if actual == OTHER else f"it is {actual.description}"
    message = f"office {verb.name} has nothing to do with {subject}: {described}"
    if actual in (LEGACY_OFFICE, XLSB):
        return WRONG_INPUT_FORMAT.issue(message, subject, redirect_suggestion(subject, actual))
    if verb.name == "create" and sniffed_kind(path):
        return WRONG_INPUT_FORMAT.issue(message, subject, f"{subject} already exists as a file to read, or to turn into another format: office read {subject}, or office convert {subject} <output>")
    return WRONG_INPUT_FORMAT.issue(message, subject, f"office {verb.name} takes {accepted}")


def absent_subject_issue(verb: Verb, subject: str, accepted: str):
    message = f"office {verb.name} has nothing to do with {subject}"
    routes = {route.kind: route for route in verb_routes(verb.name)}
    meant = None if Path(subject).suffix else closest_name(subject, list(routes))
    if meant is None:
        return WRONG_INPUT_FORMAT.issue(message, subject, f"office {verb.name} takes {accepted}")
    guess = "" if meant == subject else guess_text(meant)
    return WRONG_INPUT_FORMAT.issue(f"{message}{guess}", subject, f"office {verb.name} takes the file itself, and its extension picks the kind: office {verb.name} {subject_placeholder(routes[meant])}")


def subject_placeholder(route: Route) -> str:
    label = route_label(route)
    return f"<file>{label}" if label.startswith(".") else label
