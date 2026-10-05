from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.office_commands import command_text
from core.office_routing import positional_arguments


Rewrite = Callable[[list[str]], list[str]]
RENAMED_FLAGS = {
    "--slides": "--pages",
    "--cols": "--columns",
    "--max-rows": "--limit",
    "--min-pages": "--minimum-pages",
    "--max-pages": "--maximum-pages",
    "--required-font-substring": "--required-font",
}


@dataclass(frozen=True)
class Retired:
    words: tuple[str, str]
    rewrite: Rewrite

    @property
    def name(self) -> str:
        return " ".join(self.words)


def renamed(arguments: list[str]) -> list[str]:
    return [renamed_flag(argument) for argument in arguments]


def renamed_flag(argument: str) -> str:
    name, separator, value = argument.partition("=")
    return RENAMED_FLAGS.get(name, name) + separator + value


def flag_value(arguments: list[str], name: str) -> str | None:
    for index, argument in enumerate(arguments):
        if argument == name and index + 1 < len(arguments):
            return arguments[index + 1]
        if argument.startswith(f"{name}="):
            return argument.split("=", 1)[1]
    return None


def without_flags(arguments: list[str], names: tuple[str, ...]) -> list[str]:
    kept = []
    skip = False
    for argument in arguments:
        if skip:
            skip = False
            continue
        if argument in names:
            skip = True
            continue
        if argument.split("=", 1)[0] in names:
            continue
        kept.append(argument)
    return kept


def options(arguments: list[str]) -> list[str]:
    positionals = set(positional_arguments(arguments))
    return [argument for argument in arguments if argument not in positionals]


def same(verb: str) -> Rewrite:
    return lambda arguments: [verb, *renamed(arguments)]


def from_spec(source_placeholder: str) -> Rewrite:
    def rewrite(arguments: list[str]) -> list[str]:
        positionals = positional_arguments(arguments)
        output = positionals[0] if positionals else "<output>"
        return ["create", output, flag_value(arguments, "--spec") or source_placeholder]

    return rewrite


def edited_with(operation_file: str) -> Rewrite:
    def rewrite(arguments: list[str]) -> list[str]:
        positionals = positional_arguments(arguments)
        return ["apply", positionals[0] if positionals else "<file>", operation_file]

    return rewrite


def exported(arguments: list[str]) -> list[str]:
    positionals = positional_arguments(arguments)
    source = positionals[0] if positionals else "<source>.md"
    output = flag_value(arguments, "--output") or str(Path(source).with_suffix(".docx"))
    return ["create", output, source, *options(without_flags(arguments, ("--output",)))]


def built(arguments: list[str]) -> list[str]:
    requested = (flag_value(arguments, "--format") or "pdf").split(",")[0].strip()
    extension = "pptx" if requested == "all" else requested
    name = flag_value(arguments, "--name") or Path.cwd().name
    source = flag_value(arguments, "--source") or "."
    return ["create", f"build/{name}.{extension}", source, *without_flags(arguments, ("--format", "--name", "--source"))]


def checked_deck(arguments: list[str]) -> list[str]:
    positionals = positional_arguments(arguments)
    return ["check", *([] if positionals else ["."]), *renamed(arguments)]


def fetched_image(arguments: list[str]) -> list[str]:
    output = flag_value(arguments, "--output") or flag_value(arguments, "-o")
    return ["image", *without_flags(arguments, ("--output", "-o")), *([output] if output else [])]


def filled_form(arguments: list[str]) -> list[str]:
    positionals = positional_arguments(arguments)
    name = positionals[0] if positionals else "<form>"
    template = name if "/" in name else f"kr/{name}"
    return ["merge", template, *positionals[1:]]


def rendered_form(arguments: list[str]) -> list[str]:
    return ["merge", "<jurisdiction>/<form>", *positional_arguments(arguments)]


RETIRED_COMMANDS = (
    Retired(("doc", "export"), exported),
    Retired(("doc", "create"), from_spec("<content>.md")),
    Retired(("doc", "edit"), edited_with("<operations.json>")),
    Retired(("doc", "read"), same("read")),
    Retired(("doc", "apply"), same("apply")),
    Retired(("doc", "merge"), same("merge")),
    Retired(("doc", "render"), same("render")),
    Retired(("doc", "check"), same("check")),
    Retired(("doc", "validate"), same("check")),
    Retired(("pdf", "create"), from_spec("<spec>.json")),
    Retired(("pdf", "edit"), edited_with("<operations.json>")),
    Retired(("pdf", "read"), same("read")),
    Retired(("pdf", "render"), same("render")),
    Retired(("pdf", "validate"), same("check")),
    Retired(("sheet", "create"), from_spec("<rows>.csv")),
    Retired(("sheet", "edit"), edited_with("<operations.json>")),
    Retired(("sheet", "read"), same("read")),
    Retired(("sheet", "apply"), same("apply")),
    Retired(("sheet", "check"), same("check")),
    Retired(("sheet", "merge"), same("merge")),
    Retired(("sheet", "render"), same("render")),
    Retired(("sheet", "validate"), same("check")),
    Retired(("deck", "check"), checked_deck),
    Retired(("deck", "build"), built),
    Retired(("deck", "read"), same("read")),
    Retired(("deck", "apply"), same("apply")),
    Retired(("deck", "merge"), same("merge")),
    Retired(("deck", "restore"), same("convert")),
    Retired(("deck", "image"), fetched_image),
    Retired(("paperwork", "render"), rendered_form),
    Retired(("paperwork", "fill"), filled_form),
    Retired(("paperwork", "check"), same("check")),
)
RETIRED_FORMATS = tuple(dict.fromkeys(retired.words[0] for retired in RETIRED_COMMANDS))


def find_retired(words: list[str]) -> Retired | None:
    return next((retired for retired in RETIRED_COMMANDS if tuple(words[:2]) == retired.words), None)


def replacement_command(retired: Retired, arguments: list[str]) -> str:
    return command_text(["office", *retired.rewrite(arguments)])
