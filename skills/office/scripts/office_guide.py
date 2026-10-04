from __future__ import annotations

import importlib
from types import ModuleType

from fonts.registry import FAMILIES, face_facts
from core.office_commands import EVERY_KIND, KINDS, VERBS, Kind, Route, Verb, find_kind, find_route, find_verb, kind_routes, route_label, verb_routes
from core.office_help import route_accepts, verb_help_text
from core.office_result import COMMAND_ISSUE_KINDS, UNKNOWN_COMMAND, VALUE_FILL_IN, IssueKind, OfficeFailure
from core.office_schema import Field, Record, Shape, Variant, closest_name, guess_text
from core.office_routing import subject_route
from schemas.schema_definitions import schema_guide_text
from schemas.schema_document import is_schema_reference


USAGE = "usage: office guide [verb] [kind] [operation]"
KIND_ALIASES = {"workbook": "xlsx", "workbook.json": "xlsx"}
ENVELOPE_LINE = (
    "Every command prints one JSON result: {status: ok|warning|error, summary, outputPath, "
    "issues: [{code, severity, message, location, suggestion, fix}], details}. It exits 1 when status is error. "
    "suggestion is always text saying what to do; fix is a list of operations for office apply on the same file that make that change, "
    f"empty when no operation does, and a value in angle brackets such as {VALUE_FILL_IN} is yours to fill in; apply refuses an operation that still holds one. "
    "A null field counts as absent. A cell is text, a number, true/false, or null."
)


def guide_for(arguments: list[str]) -> str:
    if not arguments or arguments[0] in {"-h", "--help", "help"}:
        return index_text()
    verb = find_verb(arguments[0])
    if verb is None and is_schema_reference(arguments[0]):
        return schema_guide_text(arguments[0])
    if verb is None:
        return kind_text(require_kind(arguments[0]))
    if len(arguments) == 1:
        return verb_text(verb)
    if is_schema_reference(arguments[1]):
        return schema_guide_text(arguments[1])
    route = require_route(verb, arguments[1])
    if len(arguments) == 2:
        return route_text(route)
    return operation_text(route, arguments[2])


def require_kind(topic: str) -> Kind:
    kind = find_kind(topic)
    if kind is None:
        reject_unknown_topic(topic, [verb.name for verb in VERBS] + [kind.name for kind in KINDS], "office guide")
    return kind


def require_route(verb: Verb, kind_name: str) -> Route:
    route = find_route(verb.name, KIND_ALIASES.get(kind_name, kind_name)) or subject_route(verb.name, kind_name, None)
    if route is None or route.kind == EVERY_KIND:
        names = [route.kind for route in verb_routes(verb.name) if route.kind != EVERY_KIND]
        reject_unknown_topic(kind_name, names, f"office guide {verb.name}")
    return route


def reject_unknown_topic(written: str, names: list[str], prefix: str):
    raise OfficeFailure(unknown_name_issue(f"{prefix}: no topic {written!r}", written, names, prefix))


def unknown_name_issue(message: str, written: str, names: list[str], prefix: str):
    match = closest_name(written, names)
    suggestion = f"{prefix} {match}" if match else f"one of: {', '.join(names)}" if names else prefix
    return UNKNOWN_COMMAND.issue(f"{message}{guess_text(match)}", written, suggestion)


def index_text() -> str:
    kind_width = max(len(kind.name) for kind in KINDS)
    lines = [USAGE, "office --help lists the verbs and what each takes per kind.", "", "Kinds"]
    lines.extend(f"  {kind.name.ljust(kind_width)}  {kind.label}: {kind.summary}" for kind in KINDS)
    lines.extend(["", ENVELOPE_LINE, f"Any command can report {', '.join(issue.code for issue in COMMAND_ISSUE_KINDS)}."])
    return "\n".join([*lines, "", *font_lines()])


def font_lines() -> list[str]:
    roles = list(dict.fromkeys(family.role for family in FAMILIES))
    width = max(len(role) for role in roles)
    lines = ["Fonts the skill ships and draws every page with (the first of each kind is its default; * a .docx or .pptx cannot carry it)"]
    lines.extend(f"  {role.ljust(width)}  {', '.join(family_label(family) for family in FAMILIES if family.role == role)}" for role in roles)
    return lines


def family_label(family) -> str:
    carried = all(face_facts(family, face).can_embed_in_office for face in family.faces)
    return family.name if carried else f"{family.name}*"


def definitions_for(route: Route) -> ModuleType:
    kind = find_kind(route.kind)
    module = kind.definitions_module if kind is not None else find_verb(route.verb).definitions_module
    return importlib.import_module(module) if module else ModuleType("empty")


def route_inputs(route: Route) -> list[tuple[str, Shape]]:
    return [(label, shape) for verb, kind, label, shape in getattr(definitions_for(route), "GUIDE_INPUTS", ()) if (verb, kind) == (route.verb, route.kind)]


def route_issue_kinds(route: Route) -> tuple[IssueKind, ...]:
    return next((kinds for verb, kind, kinds in getattr(definitions_for(route), "GUIDE_ISSUES", ()) if (verb, kind) == (route.verb, route.kind)), ())


def topic_sections(module: ModuleType, topic: str) -> list[str]:
    lines = []
    for section_topic, title, section_lines in getattr(module, "GUIDE_SECTIONS", ()):
        if section_topic == topic:
            lines.extend(["", title, *section_lines()])
    return lines


def command_line(route: Route) -> str:
    return f"  office {route.verb} {route_accepts(route)}: {route.summary}"


def kind_text(kind: Kind) -> str:
    routes = kind_routes(kind.name)
    lines = [f"{kind.label}: {kind.summary}", "", "Commands (each verb's --help lists its options)", *(command_line(route) for route in routes)]
    listed: list[Variant] = []
    for route in routes:
        for label, shape in route_inputs(route):
            lines.extend(["", *summary_lines(route, label, shape, listed)])
    lines.extend(topic_sections(importlib.import_module(kind.definitions_module), kind.name))
    lines.extend(["", f"Issue codes (office guide <verb> {kind.name} explains a verb's own)"])
    lines.extend(f"  {route.verb}: {', '.join(issue.code for issue in route_issue_kinds(route))}" for route in routes if route_issue_kinds(route))
    return "\n".join(lines)


def verb_text(verb: Verb) -> str:
    whole = find_route(verb.name, EVERY_KIND)
    if whole is not None:
        return "\n".join([verb_help_text(verb, with_kinds=False), *topic_sections(definitions_for(whole), verb.name), *issue_explanations(route_issue_kinds(whole))])
    issue_lines = [f"  {route.kind}: {', '.join(issue.code for issue in route_issue_kinds(route))}" for route in verb_routes(verb.name) if route_issue_kinds(route)]
    heading = f"Issue codes by kind (office guide {verb.name} <kind> explains them)"
    return "\n".join([verb_help_text(verb), *(["", heading, *issue_lines] if issue_lines else [])])


def route_text(route: Route) -> str:
    lines = [command_line(route).strip()]
    described: list[Record | Variant] = []
    for label, shape in route_inputs(route):
        lines.extend(["", *input_lines(route, label, shape, described)])
    kinds = route_issue_kinds(route)
    if kinds:
        lines.extend(["", f"Issues office {route.verb} reports for {route_label(route)}", *issue_lines(kinds)])
    return "\n".join(lines)


def issue_explanations(kinds: tuple[IssueKind, ...]) -> list[str]:
    return ["", "Issues", *issue_lines(kinds)] if kinds else []


def operation_text(route: Route, operation: str) -> str:
    variants = [structure for _, shape in route_inputs(route) for structure in shape.structures() if isinstance(structure, Variant)]
    for variant in variants:
        record = variant.record_named(operation)
        if record is not None:
            return "\n".join([f"office {route.verb} {route_label(route)}, {variant.discriminator} \"{record.name}\": {record.description}", *field_lines(record.fields, "  "), *nested_structure_lines(record)])
    names = [record.name for variant in variants for record in variant.records]
    message = f"office {route.verb} {route_label(route)} has no operation {operation!r}"
    raise OfficeFailure(unknown_name_issue(message, operation, names, f"office guide {route.verb} {route.kind}"))


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


def summary_lines(route: Route, label: str, shape: Shape, listed: list[Variant]) -> list[str]:
    topic = f"office guide {route.verb} {route.kind}"
    variants = [structure for structure in shape.structures() if isinstance(structure, Variant)]
    lines = [f"office {route.verb}, {label}: {shape.label}; {topic} lists every field"]
    for variant in variants:
        if any(existing is variant for existing in listed):
            lines.append(f"  {variant.discriminator}: the {variant.name} list above")
            continue
        listed.append(variant)
        lines.append(f"  {variant.discriminator}: {', '.join(record.name for record in variant.records)}")
    if variants:
        lines.append(f"  {topic} <{variants[0].discriminator}> lists one {variants[0].discriminator}'s fields")
    return lines


def input_lines(route: Route, label: str, shape: Shape, described: list[Record | Variant]) -> list[str]:
    lines = [f"{label}: {shape.label}"]
    for structure in shape.structures():
        if any(existing is structure for existing in described):
            continue
        described.append(structure)
        if isinstance(structure, Variant):
            described.extend(nested for record in structure.records for field in record.fields for nested in field.shape.structures())
            lines.extend(variant_summary_lines(route, structure))
        else:
            lines.extend(structure_lines(structure))
    return lines


def variant_summary_lines(route: Route, variant: Variant) -> list[str]:
    lines = [f"  {variant.name}: {variant.description}; \"{variant.discriminator}\" picks one of"]
    lines.extend(f"    {variant.discriminator} \"{record.name}\": {record.description}" for record in variant.records)
    lines.append(f"  office guide {route.verb} {route.kind} <{variant.discriminator}> lists one {variant.discriminator}'s fields")
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
