from __future__ import annotations

import json
from pathlib import Path

from doc.merge_docx import merge_template
from fonts.docx_embedding import embed_named_fonts
from core.office_result import MISSING_FIELD, OfficeFailure
from paperwork.template_context import caller_fields, complete_context, list_fields, merge_values, non_empty_fields
from paperwork.template_fields import TEMPLATES_PATH


UNKNOWN_VALUE_GUIDANCE = 'fill EVERY field; use "미정" (to be decided) only when the requester truly did not provide the value'


def fill_template(template_name: str, context: dict, output_path: Path) -> None:
    completed = load_context(template_name, context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merge_template(str(TEMPLATES_PATH / f"{template_name}.docx"), merge_values(template_name, completed), str(output_path))
    embed_named_fonts(output_path)


def context_hint(template_name: str) -> str:
    fields = {field: "<value>" for field in caller_fields(template_name)}
    fields.update({field: ["<item>"] for field in list_fields(template_name)})
    return f"the values of kr/{template_name} must contain: {json.dumps(fields, ensure_ascii=False)}"


def load_context(template_name: str, context: dict) -> dict:
    completed = complete_context(template_name, context)
    problems = missing_value_problems(template_name, completed, context_hint(template_name))
    if problems:
        raise OfficeFailure(*problems)
    return completed


def missing_value_problems(template_name: str, context: dict, hint: str) -> list:
    suggestion = f"{UNKNOWN_VALUE_GUIDANCE}. {hint}"
    missing_values = [
        MISSING_FIELD.issue(f"values.{field}: required field is missing", f"values.{field}", suggestion=suggestion)
        for field in non_empty_fields(template_name)
        if str(context.get(field, "")).strip() == ""
    ]
    missing_lists = [
        MISSING_FIELD.issue(f"values.{field}: must be a non-empty array", f"values.{field}", suggestion=suggestion)
        for field in list_fields(template_name)
        if not isinstance(context.get(field), list) or not context[field]
    ]
    return missing_values + missing_lists

