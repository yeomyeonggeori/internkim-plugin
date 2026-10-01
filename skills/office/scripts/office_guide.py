from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import ModuleType

from office_commands import COMMANDS, FORMATS, Format
from office_result import COMMAND_ISSUE_KINDS, UNKNOWN_COMMAND, IssueKind, OfficeFailure
from office_schema import Field, Record, Shape, Variant, closest_name


SCRIPTS_PATH = pathlib.Path(__file__).resolve().parent
USAGE = "usage: office guide <format> [verb [operation]]"
ENVELOPE_LINE = (
    "Every command prints one JSON result: {status: ok|warning|error, summary, outputPath, "
    "issues: [{code, severity, message, location, suggestion}], details}. It exits 1 when status is error. "
    "A null field counts as absent. A cell is text, a number, true/false, or null."
)


def guide_text(office_format: Format, verb: str | None = None, operation: str | None = None) -> str:
    definitions = load_definitions(office_format)
    if operation is not None:
        return operation_text(office_format, definitions, verb, operation)
    if verb is not None:
        return verb_text(office_format, definitions, verb)
    return index_text(office_format, definitions)


def index_text(office_format: Format, definitions: ModuleType) -> str:
    lines = [f"office {office_format.name}: {office_format.summary}", "", *command_lines(office_format.name), "", ENVELOPE_LINE]
    for label, shape in definitions.GUIDE_INPUTS:
        lines.extend(["", *summary_lines(label, shape)])
    for title, section_lines in getattr(definitions, "GUIDE_SECTIONS", ()):
        lines.extend(["", title, *section_lines()])
    for issue_command, kinds in definitions.GUIDE_ISSUES:
        lines.extend(["", f"Issues {issue_command} reports", *issue_lines(kinds)])
    lines.extend(["", "Issues any command reports", *issue_lines(COMMAND_ISSUE_KINDS)])
    return "\n".join(lines)


def verb_text(office_format: Format, definitions: ModuleType, verb: str) -> str:
    command_name = f"{office_format.name} {verb}"
    lines = [*command_lines(office_format.name, command_name)]
    described: list[Record | Variant] = []
    for label, shape in verb_inputs(definitions, command_name):
        lines.extend(["", *input_lines(label, shape, described)])
    for issue_command, kinds in definitions.GUIDE_ISSUES:
        if issue_command == command_name:
            lines.extend(["", f"Issues {issue_command} reports", *issue_lines(kinds)])
    return "\n".join(lines)


def operation_text(office_format: Format, definitions: ModuleType, verb: str, operation: str) -> str:
    command_name = f"{office_format.name} {verb}"
    variants = [structure for _, shape in verb_inputs(definitions, command_name) for structure in shape.structures() if isinstance(structure, Variant)]
    for variant in variants:
        record = variant.record_named(operation)
        if record is not None:
            return "\n".join([f"office {command_name}, {variant.discriminator} \"{record.name}\": {record.description}", *field_lines(record.fields, "  "), *nested_structure_lines(record)])
    names = [record.name for variant in variants for record in variant.records]
    match = closest_name(operation, names)
    suggestion = f"office guide {command_name} {match}" if match else f"one of: {', '.join(names)}" if names else f"office guide {command_name}"
    raise OfficeFailure(UNKNOWN_COMMAND.issue(f"office {command_name} has no operation {operation!r}", operation, suggestion))


def nested_structure_lines(record: Record) -> list[str]:
    described: list[Record | Variant] = [record]
    lines = []
    for field in record.fields:
        for structure in field.shape.structures():
            if any(existing is structure for existing in described):
                continue
            described.append(structure)
            lines.extend(structure_lines(structure))
    return lines


def verb_inputs(definitions: ModuleType, command_name: str) -> list[tuple[str, Shape]]:
    return [(label, shape) for label, shape in definitions.GUIDE_INPUTS if label.startswith(command_name)]


def summary_lines(label: str, shape: Shape) -> list[str]:
    command_name = " ".join(label.split()[:2])
    variants = [structure for structure in shape.structures() if isinstance(structure, Variant)]
    lines = [f"{label}: {shape.label}; office guide {command_name} lists every field"]
    for variant in variants:
        lines.append(f"  {variant.discriminator}: {', '.join(record.name for record in variant.records)}")
    if variants:
        lines.append(f"  office guide {command_name} <{variants[0].discriminator}> lists one {variants[0].discriminator}'s fields")
    return lines


def guide_verbs(office_format: Format) -> list[str]:
    return [command.verb for command in COMMANDS if command.format_name == office_format.name]


def formats_text() -> str:
    width = max(len(office_format.name) for office_format in FORMATS)
    lines = [USAGE, ""]
    lines.extend(f"  {office_format.name.ljust(width)}  {office_format.summary}" for office_format in FORMATS)
    return "\n".join(lines)


def load_definitions(office_format: Format) -> ModuleType:
    script_path = SCRIPTS_PATH / office_format.definitions_script
    sys.path.insert(0, str(script_path.parent))
    module_name = f"{office_format.name}_guide_definitions"
    specification = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


def command_lines(format_name: str, command_name: str | None = None) -> list[str]:
    commands = [command for command in COMMANDS if command.format_name == format_name and command_name in (None, command.name)]
    width = max(len(command.name) for command in commands)
    lines = ["Commands (each one's --help lists its arguments)"]
    lines.extend(f"  office {command.name.ljust(width)}  {command.summary}" for command in commands)
    return lines


def input_lines(label: str, shape: Shape, described: list[Record | Variant]) -> list[str]:
    lines = [f"{label}: {shape.label}"]
    for structure in shape.structures():
        if any(existing is structure for existing in described):
            continue
        described.append(structure)
        lines.extend(structure_lines(structure))
    return lines


def structure_lines(structure: Record | Variant) -> list[str]:
    if isinstance(structure, Variant):
        return variant_lines(structure)
    other_fields = "; other fields are kept" if structure.keeps_other_fields else ""
    return [f"  {structure.name}: {structure.description}{other_fields}", *field_lines(structure.fields, "    ")]


def variant_lines(variant: Variant) -> list[str]:
    lines = [f"  {variant.name}: {variant.description}; \"{variant.discriminator}\" picks one of"]
    for record in variant.records:
        lines.append(f"    {variant.discriminator} \"{record.name}\": {record.description}")
        lines.extend(field_lines(record.fields, "      "))
    return lines


def field_lines(fields: tuple[Field, ...], indent: str) -> list[str]:
    return [f"{indent}{field.name} ({field_label(field)}): {field.description}" for field in fields]


def field_label(field: Field) -> str:
    return f"{field.shape.label}, required" if field.required else field.shape.label


def issue_lines(kinds: tuple[IssueKind, ...]) -> list[str]:
    return [f"  {kind.code} ({kind.severity}): {kind.meaning}. Fix: {kind.default_suggestion()}" for kind in kinds]
