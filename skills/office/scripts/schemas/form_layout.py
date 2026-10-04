from __future__ import annotations

import re

from schemas.resolution import TEMPLATE_REFERENCE, Instance, render_template
from schemas.typed_values import BLANK


def paperwork_document(instance: Instance) -> dict:
    layout = instance.schema.layout
    document = {"form": instance.schema.name, "title": instance.schema.title, "profile": instance.known.get("company") or {"name": BLANK}}
    if "documentNumber" in layout:
        document["documentNumber"] = render_template(instance, layout["documentNumber"], whole_blank=BLANK) or BLANK
    if layout.get("approvalLine"):
        document["approvalLine"] = list(layout["approvalLine"])
    if "recipient" in layout:
        document["recipient"] = recipient_block(instance, layout["recipient"])
    if "meta" in layout:
        document["meta"] = meta_rows(instance, layout["meta"])
    if "lead" in layout:
        document["lead"] = [line for template in layout["lead"] if (line := render_template(instance, template)) is not None]
    if "items" in layout:
        items = item_table(instance, layout["items"])
        if items is not None:
            document["items"] = items
    if "sections" in layout:
        present = [section for entry in layout["sections"] if (section := section_block(instance, entry)) is not None]
        document["sections"] = [{**section, "title": f"{number}. {section['title']}"} for number, section in enumerate(present, start=1)] if layout.get("numberedSections") else present
    if "notes" in layout:
        document["notes"] = [line for template in layout["notes"] if (line := render_template(instance, template)) is not None]
    if "signature" in layout:
        document["signature"] = signature_block(instance, layout["signature"])
    if "footer" in layout:
        document["footer"] = render_template(instance, layout["footer"]) or ""
    return document


def recipient_block(instance: Instance, layout: dict) -> dict:
    lines = [render_template(instance, template, whole_blank=BLANK) for template in layout.get("lines", [])]
    return {"label": layout.get("label", ""), "lines": [line for line in lines if line is not None]}


def meta_rows(instance: Instance, rows: list) -> list[dict]:
    rendered = [(row["label"], render_template(instance, row["value"], whole_blank=BLANK), value_kind(instance, row["value"], None)) for row in rows]
    return [{"label": label, "value": value, "kind": kind} for label, value, kind in rendered if value is not None]


def value_kind(instance: Instance, template, row: dict | None) -> str:
    if not isinstance(template, str) or re.search(r"\w", TEMPLATE_REFERENCE.sub("", template)):
        return "text"
    kinds = {instance.type_of(name, row)[0] for name, _ in TEMPLATE_REFERENCE.findall(template)}
    return kinds.pop() if len(kinds) == 1 else "text"


def item_table(instance: Instance, layout: dict) -> dict | None:
    rows = instance.rows.get(layout["list"]) or []
    if not rows and layout.get("omitWhenEmpty"):
        return None
    columns = layout["columns"]
    table = {
        "headers": [column["header"] for column in columns],
        "aligns": [column.get("align", "L") for column in columns],
        "kinds": [value_kind(instance, column["value"], rows[0] if rows else {}) for column in columns],
        "rows": [[render_template(instance, column["value"], row) or "" for column in columns] for row in rows],
    }
    untaxed_field = layout.get("untaxed")
    if untaxed_field:
        table["untaxedRows"] = [index for index, row in enumerate(rows) if row.get(untaxed_field)]
    if layout.get("totals"):
        table["totals"] = [{"label": total["label"], "value": render_template(instance, total["value"]) or ""} for total in layout["totals"]]
    return table


def section_block(instance: Instance, entry: dict) -> dict | None:
    if "when" in entry and not instance.given.get(entry["when"]):
        return None
    section = {"title": entry["title"]}
    if "each" in entry:
        rows = instance.rows.get(entry["each"]) or []
        section["bullets"] = [render_template(instance, entry["bullet"], row, whole_blank=BLANK) or BLANK for row in rows]
        return section if rows else None
    for kind in ("bullets", "paragraphs"):
        if kind not in entry:
            continue
        values = instance.given.get(entry[kind])
        field = instance.schema.field(entry[kind])
        if values is None and field is not None and field.optional and entry[kind] not in instance.given:
            return None
        section[kind] = [BLANK] if values is None else [str(value) if value is not None else BLANK for value in values]
        if not section[kind] and entry.get("omitWhenEmpty"):
            return None
    if "text" in entry:
        text = render_template(instance, entry["text"], whole_blank=BLANK)
        if text is None:
            return None
        section["paragraphs"] = [text]
    return section


def signature_block(instance: Instance, layout: dict) -> dict:
    return {
        "date": render_template(instance, layout.get("date", ""), whole_blank=BLANK) or "",
        "line": render_template(instance, layout.get("line", ""), whole_blank=BLANK) or "",
        "stamp": bool(layout.get("stamp")),
    }
