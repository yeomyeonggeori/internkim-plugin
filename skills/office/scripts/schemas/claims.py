from __future__ import annotations

import re

from schemas.schema_document import DocumentSchema, SchemaField

CLAIMED_TYPES = ("text", "person", "organization", "date", "amount", "quantity", "percent", "cell")
SENTENCE_END = re.compile(r"(?<!^\d\.)(?<!^\d\d\.)(?<=[.!?。])\s+", re.MULTILINE)


def written_claims(schema: DocumentSchema, given: dict) -> list[dict]:
    return list(record_claims(schema.fields, given, "", ()))


def record_claims(fields: tuple, record: dict, location: str, names: tuple):
    for field in fields:
        value = record.get(field.name)
        if value is None or field.choices:
            continue
        path = f"{location}.{field.name}" if location else field.name
        yield from field_claims(field, value, record, path, names + human_label(field))


def field_claims(field: SchemaField, value: object, record: dict, path: str, names: tuple):
    if field.is_record_list:
        for index, child in enumerate(listed(value)):
            if isinstance(child, dict):
                yield from record_claims(field.fields, child, f"{path}[{index}]", names + heading_of(child))
    elif field.type == "list" and field.item == "row":
        column_types = [column.get("type", "text") for column in listed(record.get("columns")) if isinstance(column, dict)]
        for row_index, row in enumerate(listed(value)):
            for cell_index, cell in enumerate(listed(row)):
                cell_type = column_types[cell_index] if cell_index < len(column_types) else "text"
                yield from text_claims(cell_type, cell, f"{path}[{row_index}][{cell_index}]", names)
    elif field.type == "list":
        for index, item in enumerate(listed(value)):
            yield from text_claims(field.item, item, f"{path}[{index}]", names)
    elif field.type == "cell":
        yield from text_claims(str(record.get("type") or "text"), value, path, names)
    else:
        yield from text_claims(field.type, value, path, names)


def text_claims(kind: str, value: object, path: str, names: tuple):
    if kind not in CLAIMED_TYPES or value is None or isinstance(value, bool) or not str(value).strip():
        return
    pieces = sentences(value) if isinstance(value, str) else [shown_value(kind, value)]
    place = " > ".join(names) or path.rsplit(".", 1)[-1]
    for index, piece in enumerate(pieces):
        yield {"path": f"{path}#{index}" if len(pieces) > 1 else path, "at": place, "text": piece}


def shown_value(kind: str, value: object) -> str:
    return f"{value}%" if kind == "percent" else str(value)


def sentences(text: str) -> list[str]:
    return [piece for piece in (part.strip() for part in SENTENCE_END.split(text)) if piece]


def listed(value: object) -> list:
    return value if isinstance(value, list) else []


def human_label(field: SchemaField) -> tuple:
    return (field.label,) if field.label != field.name else ()


def heading_of(record: dict) -> tuple:
    heading = record.get("heading")
    return (heading,) if isinstance(heading, str) and heading.strip() else ()
