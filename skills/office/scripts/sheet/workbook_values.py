from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import datetime
import logging
import math
import os
import tempfile
import warnings

from openpyxl import load_workbook
from openpyxl.utils.datetime import to_excel
from openpyxl.utils.formulas import FORMULAE
from xlcalculator import Evaluator, ModelCompiler
from xlcalculator.parser import FormulaParser
from xlcalculator.xltypes import XLFormula
from xlcalculator.xlfunctions import func_xltypes, xlerrors

from formula_references import (
    formula_function_names,
    formula_has_error_operand,
    formula_references,
    join_parts,
    reference_parts,
    referenced_names,
    referenced_sheet_names,
    rewrite_formula,
)
from sheet_functions import NAME_ERROR_FUNCTION, REFERENCE_ERROR_FUNCTION, SUPPORTED_FUNCTIONS, UNCOMPUTABLE_FUNCTION


NUMBER = "n"
TEXT = "str"
BOOLEAN = "b"
ERROR = "e"
EXACT_INTEGER_LIMIT = 1e15
EVALUATOR_FAILURES = (RuntimeError, ValueError, KeyError, IndexError, AttributeError, TypeError, AssertionError)

ERROR_CODES = {
    xlerrors.DivZeroExcelError: "#DIV/0!",
    xlerrors.ValueExcelError: "#VALUE!",
    xlerrors.RefExcelError: "#REF!",
    xlerrors.NameExcelError: "#NAME?",
    xlerrors.NumExcelError: "#NUM!",
    xlerrors.NaExcelError: "#N/A",
    xlerrors.NullExcelError: "#NULL!",
}


@dataclass(frozen=True)
class CachedValue:
    cell_type: str
    text: str

    @property
    def is_error(self) -> bool:
        return self.cell_type == ERROR


@dataclass
class Evaluation:
    values: dict = field(default_factory=dict)
    not_evaluated: list = field(default_factory=list)


@dataclass(frozen=True)
class FormulaCell:
    sheet: str
    coordinate: str
    formula: str


def formula_cells(workbook) -> list[FormulaCell]:
    return [
        FormulaCell(worksheet.title, cell.coordinate, cell.value)
        for worksheet in workbook.worksheets
        for row in worksheet.iter_rows()
        for cell in row
        if cell.data_type == "f" and isinstance(cell.value, str)
    ]


def array_formula_coordinates(workbook) -> list[tuple[str, str]]:
    return [
        (worksheet.title, cell.coordinate)
        for worksheet in workbook.worksheets
        for row in worksheet.iter_rows()
        for cell in row
        if cell.data_type == "f" and not isinstance(cell.value, str)
    ]


def evaluate_workbook(path: str) -> Evaluation:
    workbook = load_workbook(path)
    cells = formula_cells(workbook)
    evaluation = Evaluation(not_evaluated=array_formula_coordinates(workbook))
    scope = FormulaScope(
        sheet_names={name.casefold() for name in workbook.sheetnames},
        defined_names=defined_name_set(workbook),
        allows_user_functions=os.path.splitext(path)[1].lower() == ".xlsm",
    )
    for cell in cells:
        fixed = fixed_error(cell.formula, scope)
        workbook[cell.sheet][cell.coordinate].value = evaluation_formula(cell, fixed)
        if fixed:
            evaluation.values[(cell.sheet, cell.coordinate)] = CachedValue(ERROR, fixed)
    computed = compute_with_evaluator(workbook, [cell for cell in cells if (cell.sheet, cell.coordinate) not in evaluation.values])
    for key, value in computed.items():
        if value is None:
            evaluation.not_evaluated.append(key)
        else:
            evaluation.values[key] = value
    return evaluation


def evaluation_formula(cell: FormulaCell, fixed: str | None) -> str:
    if fixed:
        return fixed_error_formula(fixed)
    relative = relative_formula(cell.formula)
    return relative if is_computable(cell, relative) else f"={UNCOMPUTABLE_FUNCTION}()"


def is_computable(cell: FormulaCell, relative: str) -> bool:
    if any(name.removeprefix("_XLFN.") not in SUPPORTED_FUNCTIONS for name in formula_function_names(cell.formula)):
        return False
    return evaluator_can_parse(relative, cell.sheet)


def evaluator_can_parse(formula: str, sheet_name: str) -> bool:
    try:
        XLFormula(formula, sheet_name)
        FormulaParser().parse(formula, {})
    except EVALUATOR_FAILURES:
        return False
    return True


@dataclass(frozen=True)
class FormulaScope:
    sheet_names: set
    defined_names: set
    allows_user_functions: bool


def defined_name_set(workbook) -> set:
    names = {name.casefold() for name in workbook.defined_names}
    for worksheet in workbook.worksheets:
        names.update(name.casefold() for name in worksheet.defined_names)
    return names


def fixed_error(formula: str, scope: FormulaScope) -> str | None:
    if formula_has_error_operand(formula):
        return "#REF!"
    if any(name.casefold() not in scope.sheet_names for reference in formula_references(formula) for name in referenced_sheet_names(reference)):
        return "#REF!"
    if any(name.casefold() not in scope.defined_names for name in referenced_names(formula)):
        return "#NAME?"
    if not scope.allows_user_functions and any(is_unknown_function(name) for name in formula_function_names(formula)):
        return "#NAME?"
    return None


def is_unknown_function(name: str) -> bool:
    return name not in FORMULAE and not name.startswith("_XL")


def fixed_error_formula(code: str) -> str:
    function_name = REFERENCE_ERROR_FUNCTION if code == "#REF!" else NAME_ERROR_FUNCTION
    return f"={function_name}()"


def relative_formula(formula: str) -> str:
    return rewrite_formula(formula, without_absolute_markers)


def without_absolute_markers(reference: str) -> str:
    parts = reference_parts(reference)
    if parts is None:
        return reference
    return ":".join(join_parts(part.prefix, part.rest.replace("$", "")) for part in parts)


def compute_with_evaluator(workbook, cells: list[FormulaCell]) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        evaluation_path = os.path.join(directory, "evaluation.xlsx")
        workbook.save(evaluation_path)
        with quiet_evaluator_output():
            evaluator = build_evaluator(evaluation_path)
            return {(cell.sheet, cell.coordinate): evaluate_cell(evaluator, cell) if evaluator else None for cell in cells}


def build_evaluator(path: str) -> Evaluator | None:
    try:
        model = ModelCompiler().read_and_parse_archive(path)
    except EVALUATOR_FAILURES:
        return None
    for model_cell in model.cells.values():
        if model_cell.formula is None and model_cell.value == "":
            model_cell.value = None
    return Evaluator(model)


@contextmanager
def quiet_evaluator_output():
    logging.disable(logging.WARNING)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yield
    finally:
        logging.disable(logging.NOTSET)


def evaluate_cell(evaluator: Evaluator, cell: FormulaCell) -> CachedValue | None:
    try:
        return cached_value(evaluator.evaluate(f"{cell.sheet}!{cell.coordinate}"))
    except EVALUATOR_FAILURES:
        return None


def cached_value(result) -> CachedValue | None:
    if isinstance(result, xlerrors.ExcelError):
        return CachedValue(ERROR, ERROR_CODES.get(type(result), "#VALUE!"))
    if isinstance(result, func_xltypes.Blank):
        return CachedValue(NUMBER, "0")
    if isinstance(result, func_xltypes.DateTime):
        return number_value(float(result))
    if isinstance(result, func_xltypes.ExcelType):
        return cached_value(result.value)
    if isinstance(result, bool):
        return CachedValue(BOOLEAN, "1" if result else "0")
    if isinstance(result, (int, float)):
        return number_value(float(result))
    if isinstance(result, str):
        return CachedValue(TEXT, result)
    if isinstance(result, (datetime.datetime, datetime.date)):
        return number_value(float(to_excel(result)))
    return None


def number_value(number: float) -> CachedValue:
    if math.isnan(number) or math.isinf(number):
        return CachedValue(ERROR, "#NUM!")
    if number.is_integer() and abs(number) < EXACT_INTEGER_LIMIT:
        return CachedValue(NUMBER, str(int(number)))
    return CachedValue(NUMBER, repr(number))
