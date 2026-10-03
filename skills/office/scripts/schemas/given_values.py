from __future__ import annotations

import json

from core.office_result import INVALID_VALUE, UNKNOWN_FIELD, WRONG_TYPE, Issue, OfficeFailure
from core.office_schema import closest_name
from schemas.schema_document import DocumentSchema, SchemaField
from schemas.typed_values import DATE_SHAPES, NUMBER_TYPES, format_date, parse_number


TEXT_TYPES = ("text", "person", "organization")
BLOCK_FIELD = "blocks"


def json_type(field: SchemaField) -> dict:
    if field.type in NUMBER_TYPES:
        return {"type": ["number", "null"]}
    if field.type == "boolean":
        return {"type": ["boolean", "null"]}
    if field.type == "list":
        return {"type": ["array", "null"], "items": item_json_schema(field)}
    if field.type == "cell":
        return {"type": ["string", "number", "null"]}
    if field.type == "row":
        return {"type": "array", "items": {"type": ["string", "number", "null"]}}
    schema = {"type": ["string", "null"]}
    if field.choices:
        schema["enum"] = [*field.choices, None]
    return schema


def described(field: SchemaField, schema: dict) -> dict:
    words = [field.label] if field.label != field.name else []
    if field.type == "date":
        words.append("YYYY-MM-DD")
    if field.unit and field.type in NUMBER_TYPES:
        words.append(f"in {field.unit}")
    if field.description:
        words.append(field.description)
    return {**schema, "description": "; ".join(words)} if words else schema


def item_json_schema(field: SchemaField) -> dict:
    if not field.fields:
        return json_type(SchemaField(name="item", type=field.item or "text", label="item"))
    return record_json_schema(field.fields)


def record_json_schema(fields: tuple) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [field.name for field in fields if not field.optional],
        "properties": {field.name: described(field, json_type(field)) for field in fields},
    }


def input_json_schema(schema: DocumentSchema) -> dict:
    return record_json_schema(schema.fields)


def input_schema_text(schema: DocumentSchema) -> str:
    return json.dumps(input_json_schema(schema), ensure_ascii=False, separators=(",", ":"))


def runtime_names(schema: DocumentSchema) -> list[str]:
    return [*schema.known, *(derived.name for derived in schema.derived if "." not in derived.name)]


def validated_values(schema: DocumentSchema, values: object) -> dict:
    if not isinstance(values, dict):
        raise OfficeFailure(WRONG_TYPE.issue("values: expected an object holding the given fields", "values"))
    issues = record_issues(schema.fields, values, "values", runtime_names(schema))
    if issues:
        raise OfficeFailure(*issues)
    return values


def record_issues(fields: tuple, values: dict, location: str, runtime_owned: list[str]) -> list[Issue]:
    names = [field.name for field in fields]
    issues = [unknown_field_issue(name, names, runtime_owned, f"{location}.{name}") for name in values if name not in names]
    for field in fields:
        issues.extend(value_issues(field, values.get(field.name), f"{location}.{field.name}"))
    return issues


def unknown_field_issue(name: str, names: list[str], runtime_owned: list[str], location: str) -> Issue:
    owned = name if name in runtime_owned else closest_name(name, runtime_owned)
    if owned is not None and closest_name(name, names) is None:
        return UNKNOWN_FIELD.issue(f"{location}: {owned!r} is filled by the runtime or computed, not given", location, f"delete {name!r}; merge writes it")
    meant = closest_name(name, names)
    return UNKNOWN_FIELD.issue(f"{location}: no given field {name!r}; the fields are {', '.join(names)}", location, f"rename it to {meant!r}" if meant else f"delete {name!r}; the document has no place for it")


def value_issues(field: SchemaField, value: object, location: str) -> list[Issue]:
    if value is None:
        return []
    if field.type == "list":
        return list_issues(field, value, location)
    if field.type == "boolean":
        return [] if isinstance(value, bool) else [WRONG_TYPE.issue(f"{location}: expected true or false, got {value!r}", location)]
    if field.type in ("cell", "row"):
        return cell_issues(field.type, value, location)
    return scalar_issues(field.type, field.choices, value, location)


def scalar_issues(value_type: str, choices: tuple, value: object, location: str) -> list[Issue]:
    try:
        if value_type in NUMBER_TYPES:
            parse_number(value, location)
        elif value_type == "date":
            format_date(value, "en", location)
        elif not isinstance(value, str):
            return [WRONG_TYPE.issue(f"{location}: expected text, got {json.dumps(value)}", location)]
    except OfficeFailure as failure:
        return list(failure.issues)
    if choices and value not in choices:
        return [INVALID_VALUE.issue(f"{location}: {value!r} is not one of {', '.join(choices)}", location)]
    return []


def list_issues(field: SchemaField, value: object, location: str) -> list[Issue]:
    if not isinstance(value, list):
        return [WRONG_TYPE.issue(f"{location}: expected a list, got {json.dumps(value, ensure_ascii=False)[:60]}", location)]
    issues = []
    for index, item in enumerate(value):
        item_location = f"{location}[{index}]"
        if not field.fields and field.item in ("cell", "row"):
            issues.extend(cell_issues(field.item, item, item_location))
        elif not field.fields:
            issues.extend([] if item is None else scalar_issues(field.item, (), item, item_location))
        elif not isinstance(item, dict):
            issues.append(WRONG_TYPE.issue(f"{item_location}: expected an object with {', '.join(child.name for child in field.fields)}", item_location))
        else:
            issues.extend(record_issues(field.fields, item, item_location, []))
    return issues


def blank_fields(schema_fields: tuple, values: dict, location: str = "") -> list[dict]:
    blanks = []
    for field in schema_fields:
        value = values.get(field.name)
        path = f"{location}.{field.name}" if location else field.name
        if value is None and not field.optional:
            blanks.append({"field": path, "label": field.label})
        elif field.is_record_list and isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    blanks.extend(blank_fields(field.fields, item, f"{path}[{index}]"))
    return blanks


DATE_HINT = DATE_SHAPES


def cell_issues(kind: str, value: object, location: str) -> list[Issue]:
    if kind == "row":
        if not isinstance(value, list):
            return [WRONG_TYPE.issue(f"{location}: expected a row, a list of cells", location)]
        return [issue for index, cell in enumerate(value) for issue in cell_issues("cell", cell, f"{location}[{index}]")]
    if value is None or isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return []
    return [WRONG_TYPE.issue(f"{location}: expected text, a number or null, got {json.dumps(value, ensure_ascii=False)[:60]}", location)]


def normalized_values(fields: tuple, values: dict) -> dict:
    normalized = dict(values)
    for field in fields:
        value = values.get(field.name)
        if value is None:
            continue
        if field.type in NUMBER_TYPES:
            normalized[field.name] = parse_number(value, field.name)
        elif field.is_record_list:
            normalized[field.name] = [normalized_values(field.fields, item) if isinstance(item, dict) else item for item in value]
        elif field.type == "list" and field.item in NUMBER_TYPES:
            normalized[field.name] = [None if item is None else parse_number(item, field.name) for item in value]
    return normalized
