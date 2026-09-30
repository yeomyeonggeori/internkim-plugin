from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import ModuleType

from office_commands import COMMANDS, FORMATS, Format
from office_result import COMMAND_ISSUE_KINDS, IssueKind
from office_schema import Field, Record, Shape, Variant


SCRIPTS_PATH = pathlib.Path(__file__).resolve().parent
ENVELOPE_LINE = (
    "Every command prints one JSON result: {status: ok|warning|error, summary, outputPath, "
    "issues: [{code, severity, message, location, suggestion}], details}. It exits 1 when status is error. "
    "A null field counts as absent. A cell is text, a number, true/false, or null."
)


def guide_text(office_format: Format) -> str:
    definitions = load_definitions(office_format)
    lines = [f"office {office_format.name}: {office_format.summary}", "", *command_lines(office_format.name), "", ENVELOPE_LINE]
    described = []
    for label, shape in definitions.GUIDE_INPUTS:
        lines.extend(["", *input_lines(label, shape, described)])
    for title, section_lines in getattr(definitions, "GUIDE_SECTIONS", ()):
        lines.extend(["", title, *section_lines()])
    for command_name, kinds in definitions.GUIDE_ISSUES:
        lines.extend(["", f"Issues {command_name} reports", *issue_lines(kinds)])
    lines.extend(["", "Issues any command reports", *issue_lines(COMMAND_ISSUE_KINDS)])
    return "\n".join(lines)


def formats_text() -> str:
    width = max(len(office_format.name) for office_format in FORMATS)
    lines = ["usage: office guide <format>", ""]
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


def command_lines(format_name: str) -> list[str]:
    commands = [command for command in COMMANDS if command.format_name == format_name]
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
    if not fields:
        return []
    labels = [field_label(field) for field in fields]
    name_width = max(len(field.name) for field in fields)
    label_width = max(len(label) for label in labels)
    return [
        f"{indent}{field.name.ljust(name_width)}  {label.ljust(label_width)}  {field.description}"
        for field, label in zip(fields, labels)
    ]


def field_label(field: Field) -> str:
    return f"{field.shape.label}, required" if field.required else field.shape.label


def issue_lines(kinds: tuple[IssueKind, ...]) -> list[str]:
    width = max(len(kind.code) for kind in kinds)
    return [f"  {kind.code.ljust(width)}  {kind.severity.ljust(7)}  {kind.meaning}. Fix: {kind.suggestion}" for kind in kinds]
