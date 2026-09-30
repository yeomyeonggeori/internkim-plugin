from __future__ import annotations

import os
import posixpath
import tempfile
import zipfile

from lxml import etree

from office_result import Issue
from sheet_definitions import FORMULA_NOT_EVALUATED
from workbook_values import NUMBER, CachedValue, Evaluation, evaluate_workbook


MAIN_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
WORKSHEET_RELATIONSHIP = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
LISTED_CELL_LIMIT = 20



def save_workbook_with_values(workbook, path: str) -> list[Issue]:
    workbook.save(path)
    return cache_formula_values(path)


def cache_formula_values(path: str) -> list[Issue]:
    evaluation = evaluate_workbook(path)
    rewrite_archive(path, evaluation)
    return not_evaluated_issues(evaluation)


def not_evaluated_issues(evaluation: Evaluation) -> list[Issue]:
    if not evaluation.not_evaluated:
        return []
    cells = [f"{sheet}!{coordinate}" for sheet, coordinate in sorted(evaluation.not_evaluated)]
    listed = ", ".join(cells[:LISTED_CELL_LIMIT])
    hidden = len(cells) - LISTED_CELL_LIMIT
    suffix = f" and {hidden} more" if hidden > 0 else ""
    return [FORMULA_NOT_EVALUATED.issue(f"{len(cells)} formula cells have no computed value: {listed}{suffix}", cells[0])]


def rewrite_archive(path: str, evaluation: Evaluation) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
        sheet_parts = worksheet_parts(archive)
    directory = os.path.dirname(os.path.abspath(path))
    descriptor, temporary_path = tempfile.mkstemp(prefix=".office-", suffix=".xlsx", dir=directory)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary_path, "w") as rewritten:
            for info, content in entries:
                sheet_name = sheet_parts.get(info.filename)
                rewritten.writestr(info, with_cached_values(content, sheet_name, evaluation) if sheet_name else content)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def worksheet_parts(archive: zipfile.ZipFile) -> dict:
    workbook = etree.fromstring(archive.read("xl/workbook.xml"))
    relationships = etree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        relationship.get("Id"): relationship.get("Target")
        for relationship in relationships.iter(f"{{{PACKAGE_RELATIONSHIP_NAMESPACE}}}Relationship")
        if relationship.get("Type") == WORKSHEET_RELATIONSHIP
    }
    parts = {}
    for sheet in workbook.iter(f"{{{MAIN_NAMESPACE}}}sheet"):
        target = targets.get(sheet.get(f"{{{RELATIONSHIP_NAMESPACE}}}id"))
        if target is not None:
            parts[part_name(target)] = sheet.get("name")
    return parts


def part_name(target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join("xl", target))


def with_cached_values(content: bytes, sheet_name: str, evaluation: Evaluation) -> bytes:
    root = etree.fromstring(content)
    changed = False
    for cell in root.iter(f"{{{MAIN_NAMESPACE}}}c"):
        value = evaluation.values.get((sheet_name, cell.get("r")))
        if value is None or cell.find(f"{{{MAIN_NAMESPACE}}}f") is None:
            continue
        store_value(cell, value)
        changed = True
    if not changed:
        return content
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def store_value(cell, value: CachedValue) -> None:
    for existing in cell.findall(f"{{{MAIN_NAMESPACE}}}v"):
        cell.remove(existing)
    if value.cell_type == NUMBER:
        cell.attrib.pop("t", None)
    else:
        cell.set("t", value.cell_type)
    element = etree.SubElement(cell, f"{{{MAIN_NAMESPACE}}}v")
    element.text = value.text
    formula = cell.find(f"{{{MAIN_NAMESPACE}}}f")
    cell.remove(element)
    formula.addnext(element)
