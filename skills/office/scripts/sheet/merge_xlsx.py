#!/usr/bin/env python3
from __future__ import annotations

import os

from lxml import etree

from formula_cache import cache_formula_values
from office_operations import save_atomically
from office_result import OfficeArgumentParser, Result, read_json_file, run_command
from office_schema import require_valid
from template_merge import MERGE_VALUES, MISSING, MergeReport, fill_text_nodes, whole_placeholder, write_package
from workbook_package import MAIN_NAMESPACE, read_package, worksheet_parts


SHARED_STRINGS_PART = "xl/sharedStrings.xml"
HEADER_FOOTER_TAGS = ("oddHeader", "oddFooter", "evenHeader", "evenFooter", "firstHeader", "firstFooter")
PRESERVE_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def main() -> Result:
    arguments = parse_arguments()
    values = read_json_file(arguments.values_path)
    require_valid(MERGE_VALUES, values, "values")
    template_path = os.path.expanduser(arguments.template_path)
    report = MergeReport(values)
    parts = merged_parts(template_path, report)
    report.require_complete()
    output_path = os.path.expanduser(arguments.output_path)
    issues = save_atomically(lambda path: write_filled_workbook(template_path, parts, path), output_path)
    return Result(summary=f"filled {report.filled} placeholders into {output_path}", output_path=output_path, issues=(*issues, *report.unused_issues()), details={"placeholders": sorted(report.placeholder_names)})


def merged_parts(template_path: str, report: MergeReport) -> dict[str, bytes]:
    package = read_package(template_path)
    sheet_names = worksheet_parts(package)
    shared = package.xml(SHARED_STRINGS_PART) if SHARED_STRINGS_PART in package.entries else None
    sheets = {part: package.xml(part) for part in sheet_names}
    shared_items = list(shared.iterchildren(qualified("si"))) if shared is not None else []
    filled_items: set[int] = set()
    for part, worksheet in sheets.items():
        fill_worksheet(worksheet, sheet_names[part], shared_items, filled_items, report)
    rewritten = {part: serialize(worksheet) for part, worksheet in sheets.items()}
    if filled_items:
        rewritten[SHARED_STRINGS_PART] = serialize(shared)
    return rewritten


def fill_worksheet(worksheet, sheet_name: str, shared_items: list, filled_items: set[int], report: MergeReport) -> None:
    for cell in worksheet.iter(qualified("c")):
        if cell.find(qualified("f")) is not None:
            continue
        fill_cell(cell, f"{sheet_name}!{cell.get('r')}", shared_items, filled_items, report)
    for tag in HEADER_FOOTER_TAGS:
        for element in worksheet.iter(qualified(tag)):
            fill_text_nodes([element], report, f"{sheet_name} {tag}")


def fill_cell(cell, location: str, shared_items: list, filled_items: set[int], report: MergeReport) -> None:
    item = string_item(cell, shared_items)
    if item is None:
        return
    nodes = text_nodes(item)
    if write_typed_value(cell, nodes, location, report):
        return
    index = int(cell.findtext(qualified("v"))) if cell.get("t") == "s" else None
    if index in filled_items:
        return
    if fill_text_nodes(nodes, report, location):
        preserve_spaces(nodes)
        if index is not None:
            filled_items.add(index)


def string_item(cell, shared_items: list):
    if cell.get("t") == "inlineStr":
        return cell.find(qualified("is"))
    if cell.get("t") != "s":
        return None
    index = int(cell.findtext(qualified("v")))
    return shared_items[index] if index < len(shared_items) else None


def text_nodes(item) -> list:
    return [*item.findall(qualified("t")), *item.findall(f"{qualified('r')}/{qualified('t')}")]


def write_typed_value(cell, nodes: list, location: str, report: MergeReport) -> bool:
    path = whole_placeholder("".join(node.text or "" for node in nodes))
    if path is None:
        return False
    value = report.resolve(path, location)
    if value is MISSING or isinstance(value, str) or value is None:
        if value is not MISSING:
            write_inline_text(cell, value or "")
        return True
    for child in list(cell):
        cell.remove(child)
    cell.attrib.pop("t", None)
    if isinstance(value, bool):
        cell.set("t", "b")
    etree.SubElement(cell, qualified("v")).text = str(int(value)) if isinstance(value, bool) else repr(value)
    return True


def write_inline_text(cell, text: str) -> None:
    for child in list(cell):
        cell.remove(child)
    cell.set("t", "inlineStr")
    item = etree.SubElement(cell, qualified("is"))
    node = etree.SubElement(item, qualified("t"))
    node.text = text
    preserve_spaces([node])


def preserve_spaces(nodes: list) -> None:
    for node in nodes:
        node.set(PRESERVE_SPACE, "preserve")


def write_filled_workbook(template_path: str, parts: dict[str, bytes], output_path: str):
    write_package(template_path, parts, output_path)
    return cache_formula_values(output_path)


def qualified(tag: str) -> str:
    return f"{{{MAIN_NAMESPACE}}}{tag}"


def serialize(element) -> bytes:
    return etree.tostring(element, xml_declaration=True, encoding="UTF-8", standalone=True)


def parse_arguments():
    parser = OfficeArgumentParser(description="Fill an .xlsx template's {{ name }} placeholders from a JSON values file; a cell that is one placeholder takes the value's type. Refuses to write when a placeholder has no value.")
    parser.add_argument("template_path", help="the .xlsx template")
    parser.add_argument("values_path", help="JSON object mapping each placeholder name to its value")
    parser.add_argument("output_path", help="the filled .xlsx to write")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
