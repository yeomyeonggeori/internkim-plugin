from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re

from core.office_result import INVALID_VALUE, OfficeFailure
from core.office_schema import closest_name
from core.skill_paths import ASSETS_PATH
from schemas.expression import parse_expression


SCHEMAS_PATH = ASSETS_PATH / "schemas"
SCHEMA_SUFFIX = ".schema.json"
FIELD_TYPES = ("text", "person", "organization", "date", "amount", "quantity", "percent", "boolean", "list", "cell", "row")
SCALAR_ITEM_TYPES = ("text", "person", "organization", "date", "amount", "quantity", "percent")
PROVIDERS = ("requester", "requesterEmail", "today", "document.number", "company")
PROVIDER_TYPES = {"today": "date"}
TEMPLATE_NAME = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)(?::[a-z]+)?\}")


@dataclass(frozen=True)
class SchemaField:
    name: str
    type: str
    label: str
    optional: bool = False
    unit: str = ""
    description: str = ""
    item: str = ""
    fields: tuple = ()
    choices: tuple = ()

    @property
    def is_record_list(self) -> bool:
        return self.type == "list" and bool(self.fields)

    def child(self, name: str) -> "SchemaField | None":
        return next((child for child in self.fields if child.name == name), None)


@dataclass(frozen=True)
class Derived:
    name: str
    type: str
    expression: object
    text: str
    unit: str = ""


@dataclass(frozen=True)
class DocumentSchema:
    name: str
    kind: str
    language: str
    jurisdiction: str
    title: str
    fields: tuple
    known: dict
    derived: tuple
    layout: dict
    path: Path | None = None
    template: str = ""
    extra: dict = field(default_factory=dict)

    def field(self, name: str) -> SchemaField | None:
        return next((field for field in self.fields if field.name == name), None)

    def derived_named(self, name: str) -> Derived | None:
        return next((derived for derived in self.derived if derived.name == name), None)


def schema_field(document: dict, location: str) -> SchemaField:
    field_type = document.get("type", "text")
    if field_type not in FIELD_TYPES:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.type: {field_type!r} is not one of {', '.join(FIELD_TYPES)}", f"{location}.type"))
    children = tuple(schema_field(child, f"{location}.fields[{index}]") for index, child in enumerate(document.get("fields") or ()))
    return SchemaField(
        name=document["name"],
        type=field_type,
        label=document.get("label", document["name"]),
        optional=bool(document.get("optional")),
        unit=document.get("unit", ""),
        description=document.get("description", ""),
        item=document.get("item", "text" if field_type == "list" and not children else ""),
        fields=children,
        choices=tuple(document.get("choices") or ()),
    )


def derived_entry(document: dict, location: str) -> Derived:
    return Derived(document["name"], document.get("type", "amount"), parse_expression(document["expression"], f"{location}.expression"), document["expression"], document.get("unit", ""))


FORM_KINDS = ("docx-form", "xlsx-form")


def typed_form_document(document: dict) -> dict:
    fields, known, derived, placements = [], dict(document.get("known") or {}), list(document.get("derived") or []), {}
    for entry in document.get("fields") or []:
        placements[entry["name"]] = {"at": entry.get("at", {}), "fields": {child["name"]: child.get("at", {}) for child in entry.get("fields") or []}}
        if entry.get("type") in ("handwritten", "ignore"):
            continue
        if entry.get("known"):
            known[entry["name"]] = entry["known"]
            continue
        if entry.get("expression"):
            derived.append({"name": entry["name"], "type": entry.get("type", "amount"), "unit": entry.get("unit", ""), "expression": entry["expression"]})
            continue
        children = []
        for child in entry.get("fields") or []:
            if child.get("expression"):
                derived.insert(0, {"name": f"{entry['name']}.{child['name']}", "type": child.get("type", "amount"), "unit": child.get("unit", ""), "expression": child["expression"]})
            elif child.get("type") not in ("handwritten", "ignore"):
                children.append(child)
        fields.append({**entry, "fields": children} if entry.get("type") == "list" else entry)
    return {**document, "fields": fields, "known": known, "derived": derived, "placements": placements}


def schema_from_document(document: dict, path: Path | None) -> DocumentSchema:
    if document.get("kind") in FORM_KINDS:
        document = typed_form_document(document)
    known = document.get("known") or {}
    unknown_providers = [provider for provider in known.values() if provider.split(".")[0] not in {name.split(".")[0] for name in PROVIDERS}]
    if unknown_providers:
        raise OfficeFailure(INVALID_VALUE.issue(f"schema known: {', '.join(unknown_providers)} is not one of {', '.join(PROVIDERS)}", "known"))
    return DocumentSchema(
        name=document["name"],
        kind=document.get("kind", "form"),
        language=document.get("language", "en"),
        jurisdiction=document.get("jurisdiction", ""),
        title=document.get("title", ""),
        fields=tuple(schema_field(entry, f"fields[{index}]") for index, entry in enumerate(document.get("fields") or ())),
        known=dict(known),
        derived=tuple(derived_entry(entry, f"derived[{index}]") for index, entry in enumerate(document.get("derived") or ())),
        layout=document.get("layout") or {},
        path=path,
        extra={key: value for key, value in document.items() if key not in {"name", "kind", "language", "jurisdiction", "title", "fields", "known", "derived", "layout", "template"}},
        template=document.get("template", ""),
    )


LAYOUT_FIELD_KEYS = ("list", "each", "bullets", "paragraphs", "when", "field")
KINDS_PLACING_BY_CELL = FORM_KINDS
KINDS_DRAWING_THE_COMPANY = ("form",)


def placed_names(layout: object) -> set[str]:
    if isinstance(layout, str):
        return {match.group(1).split(".")[0] for match in TEMPLATE_NAME.finditer(layout)}
    if isinstance(layout, list):
        return set().union(*(placed_names(item) for item in layout)) if layout else set()
    if not isinstance(layout, dict):
        return set()
    names = {value for key, value in layout.items() if key in LAYOUT_FIELD_KEYS and isinstance(value, str)}
    return names.union(*(placed_names(value) for value in layout.values()))


def require_placed_fields(schema: DocumentSchema) -> None:
    if schema.kind in KINDS_PLACING_BY_CELL:
        return
    placed = placed_names(schema.layout)
    drawn_anyway = {name for name, provider in schema.known.items() if provider == "company" and schema.kind in KINDS_DRAWING_THE_COMPANY}
    reported = [field.name for field in schema.fields if not field.optional] + list(schema.known)
    unplaced = [name for name in reported if name not in placed | drawn_anyway]
    if unplaced:
        raise OfficeFailure(INVALID_VALUE.issue(f"schema {schema.name}: the layout never places {', '.join(unplaced)}, so a blank there would be reported and not drawn", "layout", "place each required given field and each known field in the layout, mark a setting such as language optional, or remove the field"))


def bundled_schema_path(name: str) -> Path:
    return SCHEMAS_PATH / f"{name}{SCHEMA_SUFFIX}"


def bundled_schema_names() -> list[str]:
    return sorted(str(path.relative_to(SCHEMAS_PATH))[: -len(SCHEMA_SUFFIX)] for path in SCHEMAS_PATH.rglob(f"*{SCHEMA_SUFFIX}"))


def is_schema_reference(subject: str) -> bool:
    return subject.endswith(SCHEMA_SUFFIX) or bundled_schema_path(subject).is_file()


def load_schema(reference: str) -> DocumentSchema:
    path = Path(reference).expanduser() if reference.endswith(SCHEMA_SUFFIX) else bundled_schema_path(reference)
    if not path.is_file():
        meant = closest_name(reference, bundled_schema_names())
        raise OfficeFailure(INVALID_VALUE.issue(f"{reference!r} is not a bundled schema or a .schema.json file", reference, f"use {meant}" if meant else f"one of: {', '.join(bundled_schema_names())}"))
    schema = schema_from_document(json.loads(path.read_text(encoding="utf-8")), path)
    require_placed_fields(schema)
    return schema
