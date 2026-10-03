#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from core.office_arguments import route_arguments
from core.office_result import WRONG_OUTPUT_FORMAT, OfficeFailure, Result, read_json_file, run_command
from paperwork.jurisdictions import find_jurisdiction
from schemas.given_values import blank_fields, normalized_values, validated_values
from schemas.known_values import load_runtime_context
from schemas.resolution import Instance, compute_derived, known_snapshot, resolved_known
from schemas.schema_document import DocumentSchema, load_schema


SOURCE_SUFFIX = ".source.json"
OUTPUTS_BY_KIND = {"form": (".pdf",), "document": (".docx", ".pdf", ".html"), "docx-form": (".docx",), "xlsx-form": (".xlsx",)}


def main() -> Result:
    arguments = route_arguments("merge", "schema")
    schema = load_schema(arguments.template)
    values = validated_values(schema, read_json_file(arguments.values))
    output_path = Path(arguments.output).expanduser()
    require_output_kind(schema, output_path)
    instance = schema_instance(schema, values, output_path)
    issues, drawn_blanks = render(instance, output_path)
    blanks = given_blanks(schema, values) + drawn_blanks + unknown_known_values(instance)
    source_path = write_source(output_path, instance)
    return Result(summary=summary(schema, output_path, blanks), output_path=str(output_path), issues=tuple(issues), details={"blanks": blanks, "source": str(source_path)})


def require_output_kind(schema: DocumentSchema, output_path: Path) -> None:
    accepted = OUTPUTS_BY_KIND.get(schema.kind, (".pdf",))
    if output_path.suffix.lower() not in accepted:
        raise OfficeFailure(WRONG_OUTPUT_FORMAT.issue(f"{schema.name} writes {', '.join(accepted)}, not {output_path.suffix or 'a file without an extension'}", str(output_path), f"name the output {output_path.stem}{accepted[0]}"))


def schema_instance(schema: DocumentSchema, values: dict, output_path: Path) -> Instance:
    language = values.get("language") if schema.field("language") and values.get("language") else schema.language
    jurisdiction = find_jurisdiction(schema.jurisdiction) if schema.jurisdiction else None
    known = resolved_known(schema, load_runtime_context(), language, previous_snapshot(output_path, schema))
    instance = Instance(schema, normalized_values(schema.fields, values), known, language, rounded_by(jurisdiction), words_by(jurisdiction))
    instance.original = values
    compute_derived(instance)
    return instance


def rounded_by(jurisdiction):
    return jurisdiction.money.rounded if jurisdiction else (lambda value: value)


def words_by(jurisdiction):
    if jurisdiction is None or jurisdiction.amount_in_words is None:
        return lambda value: f"{value:,}"
    return lambda value: jurisdiction.amount_in_words.line(int(value))


def source_path_of(output_path: Path) -> Path:
    return output_path.with_name(output_path.name + SOURCE_SUFFIX)


def previous_snapshot(output_path: Path, schema: DocumentSchema) -> dict:
    path = source_path_of(output_path)
    if not path.is_file():
        return {}
    source = json.loads(path.read_text(encoding="utf-8"))
    return source.get("known") or {} if source.get("schema") == schema.name else {}


def write_source(output_path: Path, instance: Instance) -> Path:
    path = source_path_of(output_path)
    source = {"schema": instance.schema.name, "given": instance.original, "known": known_snapshot(instance)}
    path.write_text(json.dumps(source, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def render(instance: Instance, output_path: Path) -> tuple[list, list]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if instance.schema.kind == "form":
        return render_form(instance, output_path), []
    if instance.schema.kind == "docx-form":
        from schemas.fill_company_form import fill_docx_form
        return fill_docx_form(instance, output_path), []
    if instance.schema.kind == "xlsx-form":
        from schemas.fill_company_form import fill_xlsx_form
        return fill_xlsx_form(instance, output_path), []
    return render_document(instance, output_path)


def render_form(instance: Instance, output_path: Path) -> list:
    from paperwork.paperwork_pdf import render_paperwork_pdf
    from paperwork.render_paperwork import load_document
    from schemas.form_layout import paperwork_document

    document = load_document(paperwork_document(instance))
    return list(render_paperwork_pdf(document, find_jurisdiction(instance.schema.jurisdiction), output_path))


def render_document(instance: Instance, output_path: Path) -> tuple[list, list]:
    from doc.blocks.charts import require_valid_charts
    from doc.blocks.docx import DEFAULT_DOCUMENT_FONT
    from doc.blocks.markdown import parse_markdown
    from doc.export_document import WRITERS
    from fonts.registry import BODY_SIZE_POINTS
    from schemas.document_layout import MarkdownDocument

    markdown = MarkdownDocument(instance).render()
    blocks = parse_markdown(markdown.text())
    require_valid_charts(blocks, output_path.name)
    options = SimpleNamespace(font=DEFAULT_DOCUMENT_FONT, font_size=BODY_SIZE_POINTS, font_path="")
    issues = WRITERS[output_path.suffix.lower().lstrip(".")](blocks, output_path, output_path.parent, options)
    return list(issues), markdown.blanks


def given_blanks(schema: DocumentSchema, values: dict) -> list[dict]:
    if schema.kind != "document":
        return blank_fields(schema.fields, values)
    return blank_fields(tuple(field for field in schema.fields if field.type != "list"), values)


def unknown_known_values(instance: Instance) -> list[dict]:
    return [{"field": name, "label": f"{name} ({provider})"} for name, provider in instance.schema.known.items() if instance.known.get(name) in (None, "", {})]


def summary(schema: DocumentSchema, output_path: Path, blanks: list[dict]) -> str:
    if not blanks:
        return f"filled {schema.name} into {output_path}; no blank fields"
    labels = ", ".join(blank["label"] for blank in blanks)
    return f"filled {schema.name} into {output_path}; {len(blanks)} blank fields for the person to fill by hand or send: {labels}"


if __name__ == "__main__":
    raise SystemExit(run_command(main))
