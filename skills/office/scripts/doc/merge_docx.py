#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import zipfile

from docx.oxml.ns import qn
from lxml import etree

from core.office_operations import save_atomically
from core.office_inputs import office_file
from core.office_result import OfficeArgumentParser, OfficeFailure, Result, read_json_file, run_command
from core.office_schema import require_valid
from core.template_merge import MERGE_VALUES, TEMPLATE_SYNTAX_ERROR, MergeReport, TextMarkup, fill_markup_part, write_package
from core.office_outputs import same_kind_output


FILLED_PART_PATTERN = re.compile(r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml")
PART_LOCATIONS = {"document": "body"}
STATEMENT_TAG = re.compile(r"\{%.*?%\}")
WORD_MARKUP = TextMarkup(qn("w:tr"), qn("w:p"), qn("w:t"))
PRESERVE_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def main() -> Result:
    arguments = parse_arguments()
    values = read_json_file(arguments.values_path)
    require_valid(MERGE_VALUES, values, "values")
    output_path = os.path.expanduser(same_kind_output(arguments.output_path, arguments.template_path))
    report = merge_template(os.path.expanduser(arguments.template_path), values, output_path)
    return Result(summary=f"filled {report.filled} placeholders into {output_path}", output_path=output_path, issues=report.unused_issues(), details={"placeholders": sorted(report.placeholder_names)})


def merge_template(template_path: str, values: dict, output_path: str) -> MergeReport:
    report = MergeReport(values)
    parts = merged_parts(template_path, report)
    report.require_complete()
    save_atomically(lambda path: write_package(template_path, parts, path), output_path)
    return report


def merged_parts(template_path: str, report: MergeReport) -> dict[str, bytes]:
    rewritten = {}
    with zipfile.ZipFile(template_path) as archive:
        for name in archive.namelist():
            match = FILLED_PART_PATTERN.fullmatch(name)
            if match is None:
                continue
            location = PART_LOCATIONS.get(match.group(1), match.group(1))
            root = etree.fromstring(archive.read(name))
            refuse_statement_tags(root, location)
            if fill_markup_part(root, WORD_MARKUP, location, report):
                preserve_edge_spaces(root)
                rewritten[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    return rewritten


def refuse_statement_tags(root, location: str) -> None:
    tags = [tag for paragraph in root.iter(qn("w:p")) for tag in STATEMENT_TAG.findall(paragraph_text(paragraph))]
    if tags:
        raise OfficeFailure(*(TEMPLATE_SYNTAX_ERROR.issue(f"the {location} uses {tag}, which merge does not read", location) for tag in dict.fromkeys(tags)))


def paragraph_text(paragraph) -> str:
    return "".join(node.text or "" for node in paragraph.iter(qn("w:t")))


def preserve_edge_spaces(root) -> None:
    for node in root.iter(qn("w:t")):
        if node.text and node.text != node.text.strip():
            node.set(PRESERVE_SPACE, "preserve")


def parse_arguments():
    parser = OfficeArgumentParser()
    parser.add_argument("template_path", type=office_file("docx"), help="the .docx template")
    parser.add_argument("values_path", help="JSON object mapping each placeholder name to its value")
    parser.add_argument("output_path", help="the filled .docx to write")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
