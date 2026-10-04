from __future__ import annotations

import json

from schemas.given_values import input_json_schema
from schemas.schema_document import bundled_schema_names, load_schema


def schema_list_lines() -> list[str]:
    lines = []
    for name in bundled_schema_names():
        schema = load_schema(name)
        lines.append(f"  {name}: {schema.title or schema.extra.get('summary', '')} ({schema.kind})")
    return lines


def schema_rule_lines() -> list[str]:
    return [
        "  office guide <schema> prints the given fields: the only values you write",
        "  a value the request and attachments do not give is null; it prints as a blank and details.blanks names it",
        "  the runtime fills the requester, today's date, the company profile, letterhead, seal and document number; merge computes amounts, tax, totals and amounts in words",
        "  merge writes <output>.source.json beside the file; to complete or correct it, change the values and run the same merge to the same output",
    ]


GUIDE_SECTIONS = (
    ("schema", "Schemas (office merge <schema> <values.json> <output>)", schema_list_lines),
    ("schema", "How a schema is filled", schema_rule_lines),
)


def schema_guide_text(name: str) -> str:
    schema = load_schema(name)
    known = ", ".join(f"{label} ({provider})" for label, provider in schema.known.items())
    derived = ", ".join(entry.name for entry in schema.derived)
    lines = [
        f"{schema.name}: {schema.title or schema.extra.get('summary', '')}",
        f"Write the given values as one JSON object and run: office merge {schema.name} <values.json> <output>",
        "A value the request and attachments do not state is null, never a guess: it prints as a blank, and the result's details.blanks names it for the reply.",
    ]
    if known:
        lines.append(f"Filled by the runtime, never written: {known}.")
    if derived:
        lines.append(f"Computed by merge, never written: {derived}.")
    if schema.extra.get("guidance"):
        lines.append(schema.extra["guidance"])
    lines.append("Given fields, as JSON Schema:")
    lines.append(json.dumps(input_json_schema(schema), ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines)
