from __future__ import annotations

import os
import tempfile

from sheet.formulas.evaluation import BOOLEAN, ERROR, NUMBER, CachedValue, evaluate_workbook


def python_value(value: CachedValue) -> object:
    if value.cell_type == NUMBER:
        number = float(value.text)
        return int(number) if number.is_integer() else number
    if value.cell_type == BOOLEAN:
        return value.text == "1"
    return value.text


def has_formulas(worksheet, bounds: tuple[int, int, int, int]) -> bool:
    min_row, min_column, max_row, max_column = bounds
    return any(cell.data_type == "f" for row in worksheet.iter_rows(min_row=min_row, max_row=max_row, min_col=min_column, max_col=max_column) for cell in row)


def computed_values(workbook, worksheet, bounds: tuple[int, int, int, int]) -> dict:
    if not has_formulas(worksheet, bounds):
        return {}
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "snapshot.xlsx")
        workbook.save(path)
        evaluation = evaluate_workbook(path, writes_dynamic_arrays=True)
    return {coordinate: python_value(value) for (sheet, coordinate), value in evaluation.values.items() if sheet == worksheet.title and value.cell_type != ERROR}


def cell_values(workbook, worksheet, bounds: tuple[int, int, int, int]) -> list[list]:
    computed = computed_values(workbook, worksheet, bounds)
    min_row, min_column, max_row, max_column = bounds
    return [
        [computed.get(cell.coordinate) if cell.data_type == "f" else cell.value for cell in row]
        for row in worksheet.iter_rows(min_row=min_row, max_row=max_row, min_col=min_column, max_col=max_column)
    ]
