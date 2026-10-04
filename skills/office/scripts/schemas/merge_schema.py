#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.office_arguments import route_arguments
from core.office_result import WRONG_OUTPUT_FORMAT, OfficeFailure, Result, read_json_file, run_command
from paperwork.jurisdictions import find_jurisdiction
from schemas.blank_paths import blanked
from schemas.claims import written_claims
from schemas.given_values import blank_fields, empty_optional_fields, normalized_values, validated_values
from schemas.known_values import load_runtime_context
from schemas.resolution import Instance, compute_derived, known_snapshot, resolved_known
from schemas.schema_document import DocumentSchema, load_schema
from core.source_snapshot import read_source, write_source


OUTPUTS_BY_KIND = {"form": (".pdf",), "document": (".docx", ".pdf", ".html"), "docx-form": (".docx",), "xlsx-form": (".xlsx",)}


def main() -> Result:
    arguments = route_arguments("merge", "schema")
    schema = load_schema(arguments.template)
    written = given_values_of(schema, read_json_file(arguments.values))
    values = validated_values(schema, blanked(written, arguments.blank))
    output_path = Path(arguments.output).expanduser()
    require_output_kind(schema, output_path)
    instance = schema_instance(schema, values, output_path)
    issues, drawn_blanks = render(instance, output_path)
    blanks = given_blanks(schema, values) + drawn_blanks + unknown_known_values(instance)
    blanks += left_blank(schema, written, arguments.blank, blanks)
    source_path = write_source(output_path, schema_source(instance, blanks))
    details = {"blanks": blanks, "emptyOptional": empty_optional_fields(schema.fields, values), "source": str(source_path)}
    return Result(summary=summary(schema, output_path, blanks), output_path=str(output_path), issues=tuple(issues), details=details)


def given_values_of(schema: DocumentSchema, document: object) -> object:
    if isinstance(document, dict) and document.get("schema") == schema.name and isinstance(document.get("given"), dict):
        return document["given"]
    return document


def left_blank(schema: DocumentSchema, written: dict, paths: list[str], listed: list[dict]) -> list[dict]:
    places = {claim["path"]: claim["at"] for claim in written_claims(schema, written)}
    fields = {blank.get("field") for blank in listed}
    return [{"field": path, "label": places.get(path, path)} for path in dict.fromkeys(paths) if path not in fields]


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


def previous_snapshot(output_path: Path, schema: DocumentSchema) -> dict:
    source = read_source(output_path)
    return source.get("known") or {} if source.get("schema") == schema.name else {}


def schema_source(instance: Instance, blanks: list[dict]) -> dict:
    return {"schema": instance.schema.name, "given": instance.original, "known": known_snapshot(instance), "blanks": blanks,
            "claims": written_claims(instance.schema, instance.original)}


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

    document = paperwork_document(instance)
    profile = document.pop("profile")
    document = load_document(document) | {"profile": profile}
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
