#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from docxtpl import DocxTemplate

from fonts.docx_embedding import save_document
from office_result import DOCUMENTS_FOLDER, MISSING_FIELD, PERMISSION_DENIED, WRONG_TYPE, OfficeArgumentParser, OfficeFailure, Result, read_json_file, run_command
from template_context import caller_fields, complete_context, non_empty_fields
from template_fields import TEMPLATES_PATH, template_list_fields, template_names


UNKNOWN_VALUE_GUIDANCE = 'fill EVERY field; use "미정" only when the requester truly did not provide the value'


def main() -> Result:
    arguments = parse_arguments()
    context = load_context(arguments.template_name, arguments.context_path)
    output_path = Path(os.path.expanduser(arguments.output_path))
    template = DocxTemplate(str(TEMPLATES_PATH / f"{arguments.template_name}.docx"))
    template.render(context)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_document(template, output_path)
    except PermissionError as error:
        raise OfficeFailure(PERMISSION_DENIED.issue(
            f"cannot write to {output_path} (permission denied)",
            location=error.filename,
            suggestion=f"rerun the SAME command with the output changed to {DOCUMENTS_FOLDER}/{output_path.parent.name}/{output_path.name}",
        )) from error
    return Result(summary=f"filled {arguments.template_name} into {output_path}", output_path=str(output_path))


def context_hint(template_name: str) -> str:
    fields = {field: "<값>" for field in caller_fields(template_name)}
    fields.update({field: ["<항목>"] for field in template_list_fields(template_name)})
    return f"context JSON for {template_name} must contain: {json.dumps(fields, ensure_ascii=False)}"


def load_context(template_name: str, context_path: str) -> dict:
    context = read_json_file(context_path)
    if not isinstance(context, dict):
        raise OfficeFailure(WRONG_TYPE.issue("context: expected an object", "context", suggestion=context_hint(template_name)))
    completed = complete_context(template_name, context)
    problems = missing_value_problems(template_name, completed, context_hint(template_name))
    if problems:
        raise OfficeFailure(*problems)
    return completed


def missing_value_problems(template_name: str, context: dict, hint: str) -> list:
    suggestion = f"{UNKNOWN_VALUE_GUIDANCE}. {hint}"
    missing_values = [
        MISSING_FIELD.issue(f"context.{field}: required field is missing", f"context.{field}", suggestion=suggestion)
        for field in non_empty_fields(template_name)
        if str(context.get(field, "")).strip() == ""
    ]
    missing_lists = [
        MISSING_FIELD.issue(f"context.{field}: must be a non-empty array", f"context.{field}", suggestion=suggestion)
        for field in template_list_fields(template_name)
        if not isinstance(context.get(field), list) or not context[field]
    ]
    return missing_values + missing_lists


def parse_arguments():
    parser = OfficeArgumentParser(description="Fill a bundled standard-form DOCX template with a context JSON; office guide paperwork lists each template's fields.")
    parser.add_argument("template_name", choices=template_names(), help="Template name")
    parser.add_argument("context_path", help="Path to the context JSON file")
    parser.add_argument("output_path", help="Path to the output .docx file")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
