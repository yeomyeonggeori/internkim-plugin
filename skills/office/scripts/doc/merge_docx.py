#!/usr/bin/env python3
import os

from docxtpl import DocxTemplate
from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

from doc_definitions import MERGE_VALUES, TEMPLATE_SYNTAX_ERROR, UNRESOLVED_PLACEHOLDER, UNUSED_VALUE
from office_operations import save_atomically
from office_result import Issue, OfficeArgumentParser, OfficeFailure, Result, read_json_file, run_command
from office_schema import require_valid


def main() -> Result:
    arguments = parse_arguments()
    values = read_json_file(arguments.values_path)
    require_valid(MERGE_VALUES, values, "values")
    template = DocxTemplate(os.path.expanduser(arguments.template_path))
    placeholder_names = template_placeholder_names(template)
    require_every_placeholder(placeholder_names, values)
    render(template, values)
    output_path = os.path.expanduser(arguments.output_path)
    save_atomically(template.save, output_path)
    unused = [UNUSED_VALUE.issue(f"values.{name} is not used by the template", f"values.{name}") for name in sorted(set(values) - placeholder_names)]
    return Result(summary=f"merged {len(placeholder_names)} placeholders into {output_path}", output_path=output_path, issues=tuple(unused), details={"placeholders": sorted(placeholder_names)})


def template_placeholder_names(template: DocxTemplate) -> set[str]:
    try:
        return set(template.get_undeclared_template_variables())
    except TemplateSyntaxError as error:
        raise OfficeFailure(syntax_issue(error)) from error


def require_every_placeholder(placeholder_names: set[str], values: dict) -> None:
    missing = sorted(placeholder_names - set(values))
    if missing:
        raise OfficeFailure(*(unresolved_issue(name) for name in missing))


def render(template: DocxTemplate, values: dict) -> None:
    try:
        template.render(values, jinja_env=Environment(undefined=StrictUndefined))
    except UndefinedError as error:
        raise OfficeFailure(UNRESOLVED_PLACEHOLDER.issue(f"the template reads a value the values file does not give: {error.message}", "values")) from error
    except TemplateSyntaxError as error:
        raise OfficeFailure(syntax_issue(error)) from error


def unresolved_issue(name: str) -> Issue:
    return UNRESOLVED_PLACEHOLDER.issue(f"the template uses {{{{ {name} }}}} but the values file has no {name!r}", f"values.{name}")


def syntax_issue(error: TemplateSyntaxError) -> Issue:
    return TEMPLATE_SYNTAX_ERROR.issue(f"template placeholder syntax error: {error.message}", f"template line {error.lineno}")


def parse_arguments():
    parser = OfficeArgumentParser(description="Fill a .docx template's {{ name }} placeholders and {% %} tags from a JSON values file. Refuses to write when a placeholder has no value.")
    parser.add_argument("template_path", help="the .docx template")
    parser.add_argument("values_path", help="JSON object mapping each placeholder name to its value")
    parser.add_argument("output_path", help="the filled .docx to write")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
