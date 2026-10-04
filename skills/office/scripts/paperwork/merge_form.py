#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from core.office_arguments import route_arguments
from core.office_result import DOCUMENTS_FOLDER, INVALID_VALUE, PERMISSION_DENIED, WRONG_TYPE, Issue, OfficeFailure, Result, read_json_file, run_command
from paperwork.blanks import form_blanks
from paperwork.check_form import amount_issues, with_amount_in_words
from paperwork.company_profile import with_company_profile
from paperwork.contract_docx import write_contract
from paperwork.contract_plan import plan_contract
from paperwork.forms import Form, require_form
from paperwork.paperwork_pdf import render_paperwork_pdf
from paperwork.render_paperwork import generate_docx, load_contract_document, load_document


def main() -> Result:
    arguments = route_arguments("merge", "form")
    form = require_form(arguments.template, "template")
    values = form_values(form, arguments.values)
    output_path = Path(arguments.output).expanduser()
    try:
        issues, details = write_form(form, values, output_path)
    except PermissionError as error:
        raise OfficeFailure(PERMISSION_DENIED.issue(
            f"cannot write to {output_path} (permission denied)",
            location=error.filename,
            suggestion=f"rerun the SAME command with the output changed to {DOCUMENTS_FOLDER}/{output_path.parent.name}/{output_path.name}",
        )) from error
    return Result(summary=f"filled {form.name} into {output_path}", output_path=str(output_path), issues=tuple(issues), details=details)


def form_values(form: Form, values_path: str) -> dict:
    values = read_json_file(values_path)
    if not isinstance(values, dict):
        raise OfficeFailure(WRONG_TYPE.issue("values: expected an object", "values"))
    named = values.get("form", form.name)
    if named != form.name:
        raise OfficeFailure(INVALID_VALUE.issue(f"values.form names {named!r}, and the command fills {form.name}", "values.form", f"fill {named} instead, or make values.form {form.name}"))
    return values | {"form": form.name}


def write_form(form: Form, values: dict, output_path: Path) -> tuple[list[Issue], dict | None]:
    if output_path.suffix.lower() == ".pdf":
        document = with_company_profile(with_amount_in_words(load_document(values)), form.jurisdiction.language)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        issues = [*amount_issues(document), *render_paperwork_pdf(document, form.jurisdiction, output_path)]
        return issues, {"blanks": [blank.to_json() for blank in form_blanks(document)]}
    template = form.contract_template
    if template is None:
        document = load_contract_document(values)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        generate_docx(document, output_path)
        return [], None
    plan, issues = plan_contract(template, values)
    if plan is None:
        raise OfficeFailure(*issues)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_contract(plan, output_path)
    return [*issues, *amount_issues(values)], plan.details


if __name__ == "__main__":
    raise SystemExit(run_command(main))
