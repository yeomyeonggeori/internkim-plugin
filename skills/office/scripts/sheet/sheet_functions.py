from __future__ import annotations

from xlcalculator.xlfunctions import func_xltypes, xl, xlerrors


REFERENCE_ERROR_FUNCTION = "INTERNKIM_REFERENCE_ERROR"
NAME_ERROR_FUNCTION = "INTERNKIM_NAME_ERROR"


def plain_value(item):
    return item.value if isinstance(item, func_xltypes.ExcelType) else item


def lookup_key(item):
    value = plain_value(item)
    if isinstance(value, str):
        return (1, value.casefold())
    if isinstance(value, bool):
        return (2, value)
    return (0, float(value))


@xl.register()
def IFERROR(value, value_if_error):
    return value_if_error if isinstance(value, xlerrors.ExcelError) else value


@xl.register()
def IFNA(value, value_if_na):
    return value_if_na if isinstance(value, xlerrors.NaExcelError) else value


@xl.register()
def INDEX(array, row_number, column_number=None):
    if isinstance(array, xlerrors.ExcelError):
        return array
    rows = func_xltypes.Array.cast(array).values.tolist()
    row_index = int(plain_value(row_number))
    column_index = int(plain_value(column_number)) if column_number is not None else None
    if column_index is None:
        row_index, column_index = single_dimension_position(rows, row_index)
    if not (1 <= row_index <= len(rows) and 1 <= column_index <= len(rows[0])):
        return xlerrors.RefExcelError("index outside the array")
    return rows[row_index - 1][column_index - 1]


def single_dimension_position(rows, position):
    if len(rows) == 1:
        return 1, position
    return position, 1


@xl.register()
def VLOOKUP(lookup_value, table_array, column_number, range_lookup=True):
    for argument in (lookup_value, table_array, column_number, range_lookup):
        if isinstance(argument, xlerrors.ExcelError):
            return argument
    rows = func_xltypes.Array.cast(table_array).values.tolist()
    column_index = int(plain_value(column_number))
    if not 1 <= column_index <= len(rows[0]):
        return xlerrors.RefExcelError("column number outside the table")
    row = matching_row(rows, lookup_key(lookup_value), bool(plain_value(range_lookup)))
    if row is None:
        return xlerrors.NaExcelError("value not found in the first column")
    return row[column_index - 1]


def matching_row(rows, key, is_approximate):
    if not is_approximate:
        return next((row for row in rows if lookup_key(row[0]) == key), None)
    candidates = [row for row in rows if lookup_key(row[0])[0] == key[0] and lookup_key(row[0]) <= key]
    return candidates[-1] if candidates else None


@xl.register(REFERENCE_ERROR_FUNCTION)
def reference_error():
    return xlerrors.RefExcelError("the formula refers to a sheet or cell that does not exist")


@xl.register(NAME_ERROR_FUNCTION)
def name_error():
    return xlerrors.NameExcelError("the formula names a function Excel does not have")
