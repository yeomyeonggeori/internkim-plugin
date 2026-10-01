#!/usr/bin/env python3
from __future__ import annotations

import copy
import os
import re
import tempfile
import zipfile

from docx.oxml.ns import qn
from docxtpl import DocxTemplate
from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError
from lxml import etree

from core.office_operations import save_atomically
from core.office_inputs import office_file
from core.office_result import Issue, OfficeArgumentParser, OfficeFailure, Result, read_json_file, run_command
from core.office_schema import require_valid
from core.template_merge import MERGE_VALUES, TEMPLATE_SYNTAX_ERROR, UNRESOLVED_PLACEHOLDER, UNUSED_VALUE, index_list_placeholders, list_outside_row_issues, repeated_list_name, write_package
from core.office_outputs import same_kind_output


FILLED_PART_PATTERN = re.compile(r"word/(document|header\d*|footer\d*)\.xml")


def main() -> Result:
    arguments = parse_arguments()
    values = read_json_file(arguments.values_path)
    require_valid(MERGE_VALUES, values, "values")
    output_path = os.path.expanduser(same_kind_output(arguments.output_path, arguments.template_path))
    with tempfile.TemporaryDirectory() as directory:
        expanded_path = os.path.join(directory, "template.docx")
        expand_list_rows(os.path.expanduser(arguments.template_path), values, expanded_path)
        template = DocxTemplate(expanded_path)
        placeholder_names = template_placeholder_names(template)
        require_every_placeholder(placeholder_names, values)
        render(template, values)
        save_atomically(template.save, output_path)
    unused = [UNUSED_VALUE.issue(f"values.{name} is not used by the template", f"values.{name}") for name in sorted(set(values) - placeholder_names)]
    return Result(summary=f"merged {len(placeholder_names)} placeholders into {output_path}", output_path=output_path, issues=tuple(unused), details={"placeholders": sorted(placeholder_names)})


def expand_list_rows(template_path: str, values: dict, expanded_path: str) -> None:
    parts = {}
    issues = []
    with zipfile.ZipFile(template_path) as archive:
        for name in archive.namelist():
            if not FILLED_PART_PATTERN.fullmatch(name):
                continue
            root = etree.fromstring(archive.read(name))
            repeated = [repeat_list_row(row, values) for row in list(root.iter(qn("w:tr")))]
            issues.extend(issue for paragraph in root.iter(qn("w:p")) for issue in list_outside_row_issues(paragraph_text(paragraph), values, name))
            if any(repeated):
                parts[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    if issues:
        raise OfficeFailure(*issues)
    write_package(template_path, parts, expanded_path)


def repeat_list_row(row, values: dict) -> bool:
    list_name = repeated_list_name(paragraph_text(row), values)
    if list_name is None:
        return False
    for index in range(len(values[list_name])):
        clone = copy.deepcopy(row)
        for paragraph in clone.iter(qn("w:p")):
            index_list_placeholders(list(paragraph.iter(qn("w:t"))), list_name, index)
        row.addprevious(clone)
    row.getparent().remove(row)
    return True


def paragraph_text(element) -> str:
    return "".join(node.text or "" for node in element.iter(qn("w:t")))


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
    parser = OfficeArgumentParser()
    parser.add_argument("template_path", type=office_file("docx"), help="the .docx template")
    parser.add_argument("values_path", help="JSON object mapping each placeholder name to its value")
    parser.add_argument("output_path", help="the filled .docx to write")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
