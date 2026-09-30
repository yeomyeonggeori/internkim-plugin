from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import math
import os
import tempfile
import warnings

from openpyxl import load_workbook
from openpyxl.utils.datetime import to_excel
from openpyxl.utils.formulas import FORMULAE
from xlcalculator import Evaluator, ModelCompiler
from xlcalculator.xlfunctions import func_xltypes, xlerrors

from formula_references import (
    formula_function_names,
    formula_has_error_operand,
    formula_references,
    join_parts,
    reference_parts,
    referenced_sheet_names,
    rewrite_formula,
)
from sheet_functions import NAME_ERROR_FUNCTION, REFERENCE_ERROR_FUNCTION


NUMBER = "n"
TEXT = "str"
BOOLEAN = "b"
ERROR = "e"
EXACT_INTEGER_LIMIT = 1e15

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
    sheet_names = set(name.casefold() for name in workbook.sheetnames)
    allows_user_functions = os.path.splitext(path)[1].lower() == ".xlsm"
    for cell in cells:
        fixed = fixed_error(cell.formula, sheet_names, allows_user_functions)
        workbook[cell.sheet][cell.coordinate].value = fixed_error_formula(fixed) if fixed else relative_formula(cell.formula)
        if fixed:
            evaluation.values[(cell.sheet, cell.coordinate)] = CachedValue(ERROR, fixed)
    computed = compute_with_evaluator(workbook, [cell for cell in cells if (cell.sheet, cell.coordinate) not in evaluation.values])
    for key, value in computed.items():
        if value is None:
            evaluation.not_evaluated.append(key)
        else:
            evaluation.values[key] = value
    return evaluation


def fixed_error(formula: str, sheet_names: set, allows_user_functions: bool) -> str | None:
    if formula_has_error_operand(formula):
        return "#REF!"
    if any(name.casefold() not in sheet_names for reference in formula_references(formula) for name in referenced_sheet_names(reference)):
        return "#REF!"
    if not allows_user_functions and any(is_unknown_function(name) for name in formula_function_names(formula)):
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
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            evaluator = Evaluator(ModelCompiler().read_and_parse_archive(evaluation_path))
            return {(cell.sheet, cell.coordinate): evaluate_cell(evaluator, cell) for cell in cells}


def evaluate_cell(evaluator: Evaluator, cell: FormulaCell) -> CachedValue | None:
    try:
        return cached_value(evaluator.evaluate(f"{cell.sheet}!{cell.coordinate}"))
    except (RuntimeError, ValueError):
        return None


def cached_value(result) -> CachedValue | None:
    if isinstance(result, xlerrors.ExcelError):
        return CachedValue(ERROR, ERROR_CODES.get(type(result), "#VALUE!"))
    if isinstance(result, func_xltypes.ExcelType):
        return cached_value(result.value)
    if result is func_xltypes.BLANK or isinstance(result, func_xltypes.Blank):
        return CachedValue(NUMBER, "0")
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
