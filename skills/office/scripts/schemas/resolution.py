from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
import re

from schemas.expression import Scope, evaluate
from schemas.known_values import RuntimeContext
from schemas.schema_document import PROVIDER_TYPES, DocumentSchema
from schemas.typed_values import BLANK, format_value, grouped


TEMPLATE_REFERENCE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)(?::([a-z]+))?\}")


@dataclass
class Instance:
    schema: DocumentSchema
    given: dict
    known: dict
    language: str
    rounded: object = None
    words: object = None
    derived: dict = field(default_factory=dict)
    rows: dict = field(default_factory=dict)
    original: dict = field(default_factory=dict)

    def scope(self, row: dict | None = None) -> Scope:
        return Scope(lambda name: self.value(name, row), self.list_values, self.rounded or (lambda value: value), self.words or (lambda value: grouped(value)))

    def value(self, name: str, row: dict | None = None):
        head, _, rest = name.partition(".")
        if row is not None and head in self.rows_names() and rest in row:
            return row[rest]
        if row is not None and name in row:
            return row[name]
        if name in self.given:
            return self.given[name]
        if name in self.derived:
            return self.derived[name]
        if head in self.known:
            return navigate(self.known[head], rest)
        return None

    def rows_names(self) -> set[str]:
        return {field.name for field in self.schema.fields if field.is_record_list}

    def list_values(self, name: str) -> list | None:
        list_name, _, member = name.partition(".")
        rows = self.rows.get(list_name)
        if rows is None:
            return None
        return [row.get(member) for row in rows] if member else rows

    def type_of(self, name: str, row: dict | None = None) -> tuple[str, str]:
        head, _, rest = name.partition(".")
        list_field = self.schema.field(head)
        if list_field is not None and list_field.is_record_list and rest:
            child = list_field.child(rest)
            if child is not None:
                return child.type, child.unit
            derived = self.schema.derived_named(name)
            return (derived.type, derived.unit) if derived else ("text", "")
        if row is not None:
            for list_field in self.schema.fields:
                child = list_field.child(name) if list_field.is_record_list else None
                if child is not None:
                    return child.type, child.unit
                derived = self.schema.derived_named(f"{list_field.name}.{name}")
                if derived is not None:
                    return derived.type, derived.unit
        given = self.schema.field(name)
        if given is not None:
            return given.type, given.unit
        derived = self.schema.derived_named(name)
        if derived is not None:
            return derived.type, derived.unit
        provider = self.schema.known.get(head, "")
        return PROVIDER_TYPES.get(provider, "text"), ""

    def is_omitted(self, name: str, row: dict | None = None) -> bool:
        if row is not None:
            for list_field in self.schema.fields:
                child = list_field.child(name) if list_field.is_record_list else None
                if child is not None:
                    return child.optional
        given = self.schema.field(name)
        return bool(given and given.optional)


def navigate(value, path: str):
    for part in [part for part in path.split(".") if part]:
        value = value.get(part) if isinstance(value, dict) else None
    return value if value != "" else None


def resolved_known(schema: DocumentSchema, context: RuntimeContext | None, language: str, snapshot: dict) -> dict:
    known = {}
    for name, provider in schema.known.items():
        if snapshot.get(name) not in (None, "", {}):
            known[name] = date.fromisoformat(snapshot[name]) if PROVIDER_TYPES.get(provider) == "date" and snapshot[name] else snapshot[name]
            continue
        known[name] = None if context is None else (context.company(language) if provider == "company" else context.value(provider, language))
    return known


def known_snapshot(instance: Instance) -> dict:
    return {name: value.isoformat() if isinstance(value, date) else value for name, value in instance.known.items()}


def compute_derived(instance: Instance) -> None:
    instance.rows = {field.name: [dict(item) for item in instance.given.get(field.name) or [] if isinstance(item, dict)] for field in instance.schema.fields if field.is_record_list}
    for derived in instance.schema.derived:
        list_name, _, member = derived.name.partition(".")
        if member and list_name in instance.rows:
            for row in instance.rows[list_name]:
                row[member] = evaluate(derived.expression, instance.scope(row))
            continue
        instance.derived[derived.name] = evaluate(derived.expression, instance.scope())


def formatted(instance: Instance, name: str, modifier: str | None, row: dict | None) -> str | None:
    value = instance.value(name, row)
    if value is None:
        return None
    value_type, unit = instance.type_of(name, row)
    if modifier == "number" and isinstance(value, (int, float, Decimal)):
        return grouped(Decimal(str(value)))
    if modifier == "compact" and isinstance(value, date):
        return value.strftime("%Y%m%d")
    if isinstance(value, bool):
        return "O" if value else ""
    if isinstance(value, dict):
        return str(value.get("name", ""))
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item is not None)
    if isinstance(value, date):
        return format_value("date", value, "", instance.language, name)
    if isinstance(value, Decimal) and value_type not in ("amount", "quantity", "percent"):
        return grouped(value)
    return format_value(value_type, value, unit, instance.language, name)


def render_template(instance: Instance, template, row: dict | None = None, whole_blank: str = "") -> str | None:
    if isinstance(template, list):
        return next((text for choice in template if (text := render_template(instance, choice, row, whole_blank)) is not None), None)
    references = TEMPLATE_REFERENCE.findall(template)
    if not references:
        return template
    pieces = {}
    for name, modifier in references:
        text = formatted(instance, name, modifier or None, row)
        if text is None and instance.is_omitted(name, row):
            return None
        pieces[(name, modifier)] = text
    if len(references) == 1 and TEMPLATE_REFERENCE.fullmatch(template) and pieces[references[0]] is None:
        return whole_blank
    return TEMPLATE_REFERENCE.sub(lambda match: pieces[(match.group(1), match.group(2) or "")] or BLANK, template)
