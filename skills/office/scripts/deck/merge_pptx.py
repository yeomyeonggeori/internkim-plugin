#!/usr/bin/env python3
from __future__ import annotations

import copy
import os
import re
import zipfile

from lxml import etree

from core.office_operations import save_atomically
from core.office_inputs import office_file
from core.office_result import OfficeArgumentParser, Result, read_json_file, run_command
from core.office_schema import require_valid
from core.template_merge import MERGE_VALUES, MergeReport, fill_text_nodes, repeated_list_name, write_package
from core.office_outputs import same_kind_output


DRAWING_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/main"
PRESENTATION_NAMESPACE = "http://schemas.openxmlformats.org/presentationml/2006/main"
FILLED_PART_PATTERN = re.compile(r"ppt/(slides/slide|notesSlides/notesSlide)(\d+)\.xml")


def main() -> Result:
    arguments = parse_arguments()
    values = read_json_file(arguments.values_path)
    require_valid(MERGE_VALUES, values, "values")
    template_path = os.path.expanduser(arguments.template_path)
    report = MergeReport(values)
    parts = merged_parts(template_path, report)
    report.require_complete()
    output_path = os.path.expanduser(same_kind_output(arguments.output_path, arguments.template_path))
    save_atomically(lambda path: write_package(template_path, parts, path), output_path)
    return Result(summary=f"filled {report.filled} placeholders into {output_path}", output_path=output_path, issues=report.unused_issues(), details={"placeholders": sorted(report.placeholder_names)})


def merged_parts(template_path: str, report: MergeReport) -> dict[str, bytes]:
    rewritten = {}
    with zipfile.ZipFile(template_path) as archive:
        for name in sorted(archive.namelist(), key=part_order):
            match = FILLED_PART_PATTERN.fullmatch(name)
            if match is None:
                continue
            root = etree.fromstring(archive.read(name))
            location = f"{'notes of ' if 'notes' in match.group(1) else ''}slide {match.group(2)}"
            if fill_part(root, location, report):
                rewritten[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    return rewritten


def part_order(name: str) -> tuple:
    match = FILLED_PART_PATTERN.fullmatch(name)
    return (match.group(1), int(match.group(2))) if match else ("", 0)


def fill_part(root, location: str, report: MergeReport) -> bool:
    repeated = any([repeat_rows(row, location, report) for row in list(root.iter(drawing("tr")))])
    filled = [fill_text_nodes(paragraph_text_nodes(paragraph), report, location) for paragraph in root.iter(drawing("p"))]
    return repeated or any(filled)


def paragraph_text_nodes(paragraph) -> list:
    return list(paragraph.iter(drawing("t")))


def repeat_rows(row, location: str, report: MergeReport) -> bool:
    list_name = repeated_list_name("".join(node.text or "" for node in row.iter(drawing("t"))), report.values)
    if list_name is None:
        return False
    items = report.values[list_name]
    report.mark_used(list_name)
    for index, item in enumerate(items):
        clone = copy.deepcopy(row)
        for paragraph in clone.iter(drawing("p")):
            fill_text_nodes(paragraph_text_nodes(paragraph), report, f"{location} row {list_name}.{index}", {**report.values, list_name: item})
        row.addprevious(clone)
    grow_table_frame(row, len(items) - 1)
    row.getparent().remove(row)
    return True


def grow_table_frame(row, added_rows: int) -> None:
    frame = next(row.iterancestors(f"{{{PRESENTATION_NAMESPACE}}}graphicFrame"), None)
    extent = frame.find(f"{{{PRESENTATION_NAMESPACE}}}xfrm/{drawing('ext')}") if frame is not None else None
    if extent is None:
        return
    extent.set("cy", str(max(0, int(extent.get("cy")) + added_rows * int(row.get("h", "0")))))


def drawing(tag: str) -> str:
    return f"{{{DRAWING_NAMESPACE}}}{tag}"


def parse_arguments():
    parser = OfficeArgumentParser()
    parser.add_argument("template_path", type=office_file("pptx"), help="the .pptx template")
    parser.add_argument("values_path", help="JSON object mapping each placeholder name to its value")
    parser.add_argument("output_path", help="the filled .pptx to write")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
