from __future__ import annotations

from openpyxl.worksheet.formula import ArrayFormula

from dynamic_arrays import cell_element, dynamic_array_cell_metadata, mark_array_formula
from excel_functions import is_dynamic_array_formula
from office_result import Issue
from sheet_definitions import CIRCULAR_REFERENCE, FORMULA_NOT_EVALUATED
from workbook_package import Package, main_tag, read_package, worksheet_parts, write_package
from workbook_values import NUMBER, CachedValue, Evaluation, clear_array_area, evaluate_workbook


LISTED_CELL_LIMIT = 20


def save_workbook_with_values(workbook, path: str) -> list[Issue]:
    restore_dynamic_arrays(workbook)
    workbook.save(path)
    return cache_formula_values(path)


def restore_dynamic_arrays(workbook) -> None:
    for worksheet in workbook.worksheets:
        for cell in list(worksheet._cells.values()):
            if isinstance(cell.value, ArrayFormula) and is_dynamic_array_formula(cell.value.text or ""):
                clear_previous_spill(worksheet, cell)


def clear_previous_spill(worksheet, cell) -> None:
    formula = cell.value.text
    clear_array_area(worksheet, cell.value.ref, cell.coordinate)
    cell.value = formula


def cache_formula_values(path: str) -> list[Issue]:
    evaluation = evaluate_workbook(path, writes_dynamic_arrays=True)
    package = read_package(path)
    store_values(package, evaluation)
    write_package(package, path)
    return evaluation_issues(evaluation)


def evaluation_issues(evaluation: Evaluation) -> list[Issue]:
    issues = []
    if evaluation.circular:
        cells = cell_labels(evaluation.circular)
        issues.append(CIRCULAR_REFERENCE.issue(f"{len(cells)} formula cells read their own value: {listed(cells)}", cells[0]))
    if evaluation.not_evaluated:
        cells = cell_labels(evaluation.not_evaluated)
        issues.append(FORMULA_NOT_EVALUATED.issue(f"{len(cells)} formula cells have no computed value: {listed(cells)}", cells[0]))
    return issues


def cell_labels(keys: list) -> list[str]:
    return [f"{sheet}!{coordinate}" for sheet, coordinate in sorted(keys)]


def listed(cells: list[str]) -> str:
    hidden = len(cells) - LISTED_CELL_LIMIT
    return ", ".join(cells[:LISTED_CELL_LIMIT]) + (f" and {hidden} more" if hidden > 0 else "")


def store_values(package: Package, evaluation: Evaluation) -> None:
    dynamic = any(array.is_dynamic for array in evaluation.arrays.values())
    cell_metadata = dynamic_array_cell_metadata(package) if dynamic else None
    for part, sheet_name in worksheet_parts(package).items():
        root = package.xml(part)
        if store_sheet_values(root, sheet_name, evaluation, cell_metadata):
            package.set_xml(part, root)


def store_sheet_values(root, sheet_name: str, evaluation: Evaluation, cell_metadata: str | None) -> bool:
    changed = False
    for cell in list(root.iter(main_tag("c"))):
        key = (sheet_name, cell.get("r"))
        value = evaluation.values.get(key)
        if value is None or cell.find(main_tag("f")) is None:
            continue
        store_value(cell, value)
        array = evaluation.arrays.get(key)
        if array is not None:
            mark_array_formula(cell, array.reference, cell_metadata if array.is_dynamic else None)
            store_array_cells(root, array)
        changed = True
    return changed


def store_array_cells(root, array) -> None:
    for coordinate, value in array.cells.items():
        cell = cell_element(root, coordinate)
        for child in list(cell):
            cell.remove(child)
        cell.attrib.pop("t", None)
        if value is not None:
            store_value(cell, value)


def store_value(cell, value: CachedValue) -> None:
    for existing in cell.findall(main_tag("v")):
        cell.remove(existing)
    if value.cell_type == NUMBER:
        cell.attrib.pop("t", None)
    else:
        cell.set("t", value.cell_type)
    element = cell.makeelement(main_tag("v"), {})
    element.text = value.text
    formula = cell.find(main_tag("f"))
    if formula is None:
        cell.append(element)
    else:
        formula.addnext(element)
