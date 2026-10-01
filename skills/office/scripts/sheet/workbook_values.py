from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
import tempfile

from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.worksheet.formula import ArrayFormula

from sheet.dynamic_arrays import dynamic_array_cell_metadata, mark_array_formula
from sheet.excel_functions import is_dynamic_array_formula
from sheet.formula_dependencies import DependencyReader, cell_position, propagate
from sheet.formula_references import is_bare_name, join_parts, quote_sheet_name, reference_parts, rewrite_formula
from sheet.ironcalc_compatibility import constant_names, is_divergent_criteria, needs_criteria_probe, prepare, with_constant_names
from core.excel_limits import MAXIMUM_ROW
from core.office_inputs import holds_macros
from sheet.workbook_access import open_workbook
from sheet.workbook_package import main_tag, read_package, relationships_part, worksheet_parts, write_package


NUMBER = "n"
TEXT = "str"
BOOLEAN = "b"
ERROR = "e"
EXACT_INTEGER_LIMIT = 1e15
EXCEL_ERROR_CODES = frozenset((
    "#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#N/A", "#GETTING_DATA", "#SPILL!", "#CALC!",
    "#FIELD!", "#BLOCKED!", "#UNKNOWN!", "#CONNECT!", "#BUSY!",
))
PROBE_SHEET = "InternKimProbe"
CIRCULAR_ERROR = "#CIRC!"
IMPLICIT_INTERSECTION = "=@"


@dataclass(frozen=True)
class CachedValue:
    cell_type: str
    text: str

    @property
    def is_error(self) -> bool:
        return self.cell_type == ERROR


@dataclass
class ArrayResult:
    reference: str
    is_dynamic: bool
    cells: dict = field(default_factory=dict)


@dataclass
class Evaluation:
    values: dict = field(default_factory=dict)
    not_evaluated: list = field(default_factory=list)
    circular: list = field(default_factory=list)
    arrays: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FormulaCell:
    sheet: str
    coordinate: str
    formula: str
    array_reference: str | None

    @property
    def key(self) -> tuple[str, str]:
        return self.sheet, self.coordinate


@dataclass
class EvaluationPlan:
    preparations: dict = field(default_factory=dict)
    roots: set = field(default_factory=set)
    dynamic: set = field(default_factory=set)
    arrays: dict = field(default_factory=dict)


def formula_cells(workbook) -> list[FormulaCell]:
    cells = []
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.data_type != "f":
                    continue
                if isinstance(cell.value, ArrayFormula):
                    cells.append(FormulaCell(worksheet.title, cell.coordinate, cell.value.text or "=", cell.value.ref))
                elif isinstance(cell.value, str):
                    cells.append(FormulaCell(worksheet.title, cell.coordinate, cell.value, None))
    return cells


def dynamic_cells_in_file(path: str) -> set:
    package = read_package(path)
    marked = set()
    for part, sheet in worksheet_parts(package).items():
        root = package.xml(part)
        marked.update((sheet, cell.get("r")) for cell in root.iter(main_tag("c")) if cell.get("cm") and cell.find(main_tag("f")) is not None)
    return marked


def evaluate_workbook(path: str, writes_dynamic_arrays: bool = False) -> Evaluation:
    workbook = open_workbook(path)
    cells = formula_cells(workbook)
    evaluation = Evaluation()
    if not cells:
        return evaluation
    marked = set() if writes_dynamic_arrays else dynamic_cells_in_file(path)
    plan = plan_evaluation(workbook, cells, marked, writes_dynamic_arrays, holds_macros(path))
    for cell in cells:
        fixed_error = plan.preparations[cell.key].fixed_error
        if fixed_error:
            evaluation.values[cell.key] = CachedValue(ERROR, fixed_error)
    with tempfile.TemporaryDirectory() as directory:
        evaluation_path = os.path.join(directory, "evaluation.xlsx")
        workbook.save(evaluation_path)
        prepare_evaluation_package(evaluation_path, plan.dynamic)
        computed = compute_with_ironcalc(evaluation_path, cells, plan, directory)
    if computed is None:
        evaluation.not_evaluated = sorted(cell.key for cell in cells if cell.key not in evaluation.values)
        return evaluation
    values, arrays, probe_roots, circular = computed
    roots = plan.roots | probe_roots | {key for key, value in values.items() if value is None}
    unevaluated = propagate(roots, {cell.key: cell.formula for cell in cells}, DependencyReader(workbook))
    for key, value in values.items():
        if key not in unevaluated and key not in evaluation.values:
            evaluation.values[key] = value
    evaluation.arrays = {key: array for key, array in arrays.items() if key not in unevaluated}
    evaluation.circular = sorted(circular)
    evaluation.not_evaluated = sorted(key for key in unevaluated if key not in evaluation.values and key not in circular)
    return evaluation


def plan_evaluation(workbook, cells: list[FormulaCell], marked: set, writes_dynamic_arrays: bool, allows_user_functions: bool) -> EvaluationPlan:
    plan = EvaluationPlan()
    constants = {title: constant_names(workbook, title) for title in workbook.sheetnames}
    for cell in cells:
        preparation = prepare(with_constant_names(cell.formula, constants[cell.sheet]), allows_user_functions)
        plan.preparations[cell.key] = preparation
        if not preparation.is_computable:
            plan.roots.add(cell.key)
        worksheet_cell = workbook[cell.sheet][cell.coordinate]
        if is_dynamic_array_formula(cell.formula) and not preparation.fixed_error:
            if not writes_dynamic_arrays and cell.key not in marked:
                plan.roots.add(cell.key)
            if cell.array_reference is not None:
                clear_array_area(workbook[cell.sheet], cell.array_reference, cell.coordinate)
            plan.dynamic.add(cell.key)
            worksheet_cell.value = preparation.formula
        elif cell.array_reference is not None:
            plan.arrays[cell.key] = cell.array_reference
            worksheet_cell.value = ArrayFormula(cell.array_reference, preparation.formula)
        else:
            worksheet_cell.value = preparation.formula
    return plan


def clear_array_area(worksheet, reference: str, anchor: str) -> None:
    min_column, min_row, max_column, max_row = range_boundaries(reference)
    for row in worksheet.iter_rows(min_row=min_row, max_row=max_row, min_col=min_column, max_col=max_column):
        for spilled in row:
            if spilled.coordinate != anchor:
                spilled.value = None


def prepare_evaluation_package(path: str, dynamic: set) -> None:
    package = read_package(path)
    cell_metadata = dynamic_array_cell_metadata(package) if dynamic else None
    for part, sheet in worksheet_parts(package).items():
        without_comment_relationships(package, part)
        root = package.xml(part)
        for cell in root.iter(main_tag("c")):
            if len(cell) == 0:
                # IronCalc 0.8.3 reads a typed cell without a value, such as openpyxl's styled <c t="n"/>, as 0 or ""
                cell.attrib.pop("t", None)
            elif (sheet, cell.get("r")) in dynamic and cell.find(main_tag("f")) is not None:
                mark_array_formula(cell, cell.get("r"), cell_metadata)
        package.set_xml(part, root)
    write_package(package, path)


def without_comment_relationships(package, part: str) -> None:
    # IronCalc 0.8.3 resolves a comments target as relative even when it is absolute, as openpyxl writes it
    # (xlsx/src/import/worksheets.rs load_sheet_rels), and then fails to load; notes never affect values
    rels_part = relationships_part(part)
    if rels_part not in package.entries:
        return
    root = package.xml(rels_part)
    comments = [element for element in root if (element.get("Type") or "").endswith("/comments")]
    for element in comments:
        root.remove(element)
    if comments:
        package.set_xml(rels_part, root)


def compute_with_ironcalc(path: str, cells: list[FormulaCell], plan: EvaluationPlan, directory: str):
    model = loaded_model(path)
    if model is None:
        return None
    sheet_indexes = {properties["name"]: index for index, properties in enumerate(model.get_worksheets_properties())}
    computed_cells = [cell for cell in cells if not plan.preparations[cell.key].fixed_error]
    intersection_roots = repair_implicit_intersections(model, computed_cells, sheet_indexes)
    values = {cell.key: computed_value(model, sheet_indexes[cell.sheet], *cell_position(cell.coordinate)) for cell in computed_cells}
    circular = {cell.key for cell in computed_cells if model.get_cell_value(sheet_indexes[cell.sheet], *cell_position(cell.coordinate)) == CIRCULAR_ERROR}
    arrays = read_arrays(model, sheet_indexes, plan, directory)
    return values, arrays, criteria_roots(model, cells, plan) | intersection_roots, circular


def repair_implicit_intersections(model, cells: list[FormulaCell], sheet_indexes: dict) -> set:
    # IronCalc 0.8.3 puts @ in front of a legacy formula whose result is a reference and answers #VALUE! for it,
    # even when the reference is one cell; such a cell is recomputed through INDEX, and one whose reference
    # spans several cells is left unevaluated
    broken = [(cell, sheet_indexes[cell.sheet], *cell_position(cell.coordinate)) for cell in cells]
    broken = [(cell, sheet, row, column) for cell, sheet, row, column in broken if model.get_cell_content(sheet, row, column).startswith(IMPLICIT_INTERSECTION) and model.get_cell_value(sheet, row, column) == "#VALUE!"]
    if not broken:
        return set()
    for position, (_, sheet, row, column) in enumerate(broken):
        expression = model.get_cell_content(sheet, row, column)[len(IMPLICIT_INTERSECTION):]
        model.set_user_input(sheet, MAXIMUM_ROW - position, column, f"=ROWS({expression})*COLUMNS({expression})")
    model.evaluate()
    roots = set()
    for position, (cell, sheet, row, column) in enumerate(broken):
        size = model.get_cell_value(sheet, MAXIMUM_ROW - position, column)
        expression = model.get_cell_content(sheet, row, column)[len(IMPLICIT_INTERSECTION):]
        model.clear_cell_contents(sheet, MAXIMUM_ROW - position, column)
        if size == 1:
            model.set_user_input(sheet, row, column, f"=INDEX({expression},1,1)")
        else:
            roots.add(cell.key)
    model.evaluate()
    return roots


def loaded_model(path: str):
    import ironcalc

    try:
        model = ironcalc.load_from_xlsx(path, "en", "UTC")
        model.evaluate()
        return model
    except ironcalc.WorkbookError:
        return None
    except BaseException as error:
        if type(error).__name__ != "PanicException":
            raise
        return None


def computed_value(model, sheet_index: int, row: int, column: int) -> CachedValue | None:
    from ironcalc import CellType

    value = model.get_cell_value(sheet_index, row, column)
    kind = model.get_cell_type(sheet_index, row, column)
    if kind == CellType.ErrorValue:
        return CachedValue(ERROR, value) if value in EXCEL_ERROR_CODES else None
    if kind == CellType.Text:
        return CachedValue(TEXT, value)
    if kind == CellType.LogicalValue:
        return CachedValue(BOOLEAN, "1" if value else "0")
    if kind == CellType.Number:
        return number_value(float(value or 0))
    return None


def number_value(number: float) -> CachedValue:
    if math.isnan(number) or math.isinf(number):
        return CachedValue(ERROR, "#NUM!")
    if number.is_integer() and abs(number) < EXACT_INTEGER_LIMIT:
        return CachedValue(NUMBER, str(int(number)))
    return CachedValue(NUMBER, repr(number))


def read_arrays(model, sheet_indexes: dict, plan: EvaluationPlan, directory: str) -> dict:
    references = dict(plan.arrays)
    if plan.dynamic:
        references.update(spill_references(model, plan.dynamic, directory))
    arrays = {}
    for key, reference in references.items():
        array = ArrayResult(reference, key in plan.dynamic)
        min_column, min_row, max_column, max_row = range_boundaries(reference)
        for row in range(min_row, max_row + 1):
            for column in range(min_column, max_column + 1):
                coordinate = f"{get_column_letter(column)}{row}"
                if coordinate != key[1]:
                    array.cells[coordinate] = computed_value(model, sheet_indexes[key[0]], row, column)
        arrays[key] = array
    return arrays


def spill_references(model, dynamic: set, directory: str) -> dict:
    saved_path = os.path.join(directory, "spilled.xlsx")
    model.save_to_xlsx(saved_path)
    package = read_package(saved_path)
    references = {}
    for part, sheet in worksheet_parts(package).items():
        for cell in package.xml(part).iter(main_tag("c")):
            formula = cell.find(main_tag("f"))
            if (sheet, cell.get("r")) in dynamic and formula is not None:
                references[(sheet, cell.get("r"))] = formula.get("ref") or cell.get("r")
    return {key: references.get(key, key[1]) for key in dynamic}


def criteria_roots(model, cells: list[FormulaCell], plan: EvaluationPlan) -> set:
    probes = [
        (cell.key, pair)
        for cell in cells
        for pair in plan.preparations[cell.key].criteria
        if cell.key not in plan.roots and needs_criteria_probe(pair)
    ]
    if not probes:
        return set()
    model.add_sheet(PROBE_SHEET)
    probe_index = len(model.get_worksheets_properties()) - 1
    for position, (key, pair) in enumerate(probes):
        criteria_range = qualified(pair.range_text, key[0])
        criteria = qualified(pair.criteria_text, key[0])
        model.set_user_input(probe_index, position + 1, 1, f'=ROWS({criteria_range})*COLUMNS({criteria_range})-COUNTIF({criteria_range},"*")')
        model.set_user_input(probe_index, position + 1, 2, f"={criteria}")
        model.set_user_input(probe_index, position + 1, 3, f"=IFERROR(ROWS({criteria})*COLUMNS({criteria}),COUNTA({criteria}))")
    model.evaluate()
    return {key for position, (key, _) in enumerate(probes) if criteria_diverges(model, probe_index, position + 1)}


def criteria_diverges(model, probe_index: int, row: int) -> bool:
    cells_without_text = model.get_cell_value(probe_index, row, 1)
    criteria = model.get_cell_value(probe_index, row, 2)
    criteria_cells = model.get_cell_value(probe_index, row, 3)
    if not isinstance(cells_without_text, (int, float)) or criteria_cells != 1:
        return True
    return cells_without_text > 0 and is_divergent_criteria(criteria)


def qualified(expression: str, host_sheet: str) -> str:
    return rewrite_formula("=" + expression, lambda reference: qualified_reference(reference, host_sheet))[1:]


def qualified_reference(reference: str, host_sheet: str) -> str:
    if is_bare_name(reference) or "[" in reference:
        return reference
    parts = reference_parts(reference)
    if parts is None or parts[0].prefix is not None:
        return reference
    return join_parts(quote_sheet_name(host_sheet), reference)
