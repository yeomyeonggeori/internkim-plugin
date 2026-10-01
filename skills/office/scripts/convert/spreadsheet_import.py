from __future__ import annotations

from dataclasses import dataclass, field
import datetime
from pathlib import Path
import zipfile

from lxml import etree
from openpyxl import Workbook
from python_calamine import CalamineWorkbook
import xlrd

from convert_definitions import CONVERSION_APPROXIMATED
from formula_cache import cache_formula_values
from office_result import Issue
from excel_limits import fitting_sheet_name


OPEN_DOCUMENT_NAMESPACES = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
NUMERIC_VALUE_TYPES = ("float", "percentage", "currency")
PACKAGE_RELATIONSHIP_NAMESPACE = "{http://schemas.openxmlformats.org/package/2006/relationships}"
BUNDLE_SHEET_RECORD = 0x009C
MERGE_CELL_RECORD = 0x00B0


@dataclass
class SheetData:
    name: str
    cells: dict[tuple[int, int], object] = field(default_factory=dict)
    merges: list[tuple[int, int, int, int]] = field(default_factory=list)
    formulas: int = 0


def legacy_workbook_to_xlsx(input_path: Path, output_path: Path) -> list[Issue]:
    sheets = SPREADSHEET_READERS[input_path.suffix.lower()](input_path)
    write_workbook(sheets, output_path)
    issues = list(cache_formula_values(str(output_path)))
    formulas = sum(sheet.formulas for sheet in sheets)
    carried = "values, dates and merged cells" + (f"; {formulas} formulas were kept as their computed values" if formulas else "")
    issues.append(CONVERSION_APPROXIMATED.issue(f"carried {carried}; fonts, colors, borders, column widths and charts were not carried", input_path.name))
    return issues


def read_xls(input_path: Path) -> list[SheetData]:
    book = xlrd.open_workbook(str(input_path))
    return [xls_sheet(book, book.sheet_by_index(index)) for index in range(book.nsheets)]


def xls_sheet(book, sheet) -> SheetData:
    data = SheetData(sheet.name)
    for row in range(sheet.nrows):
        for column in range(sheet.ncols):
            value = xls_value(book, sheet.cell(row, column))
            if value is not None:
                data.cells[(row + 1, column + 1)] = value
    data.merges = [(top + 1, left + 1, bottom, right) for top, bottom, left, right in sheet.merged_cells]
    return data


def xls_value(book, cell) -> object:
    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK, xlrd.XL_CELL_ERROR):
        return None
    if cell.ctype == xlrd.XL_CELL_DATE:
        moment = xlrd.xldate.xldate_as_datetime(cell.value, book.datemode)
        return moment.date() if moment.time() == datetime.time() else moment
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    if cell.ctype == xlrd.XL_CELL_NUMBER and float(cell.value).is_integer():
        return int(cell.value)
    return cell.value


def read_ods(input_path: Path) -> list[SheetData]:
    with zipfile.ZipFile(input_path) as archive:
        content = etree.fromstring(archive.read("content.xml"))
    return [ods_sheet(table) for table in content.iterfind(".//table:table", OPEN_DOCUMENT_NAMESPACES)]


def ods_sheet(table) -> SheetData:
    data = SheetData(table.get(open_document("table", "name")))
    row_number = 1
    for row in table.iterfind(".//table:table-row", OPEN_DOCUMENT_NAMESPACES):
        repeat = int(row.get(open_document("table", "number-rows-repeated"), "1"))
        cells = ods_row_cells(row, data)
        if not cells:
            row_number += repeat
            continue
        for offset in range(repeat):
            for column, value in cells.items():
                data.cells[(row_number + offset, column)] = value
        row_number += repeat
        ods_row_merges(row, row_number - repeat, data)
    return data


def ods_row_cells(row, data: SheetData) -> dict[int, object]:
    cells, column = {}, 1
    for cell in row:
        repeat = int(cell.get(open_document("table", "number-columns-repeated"), "1"))
        value = ods_value(cell)
        if value is not None:
            data.formulas += repeat if cell.get(open_document("table", "formula")) else 0
            cells.update({column + offset: value for offset in range(repeat)})
        column += repeat
    return cells


def ods_row_merges(row, row_number: int, data: SheetData) -> None:
    column = 1
    for cell in row:
        rows = int(cell.get(open_document("table", "number-rows-spanned"), "1"))
        columns = int(cell.get(open_document("table", "number-columns-spanned"), "1"))
        if rows > 1 or columns > 1:
            data.merges.append((row_number, column, row_number + rows - 1, column + columns - 1))
        column += int(cell.get(open_document("table", "number-columns-repeated"), "1"))


def ods_value(cell) -> object:
    value_type = cell.get(open_document("office", "value-type"))
    if value_type in NUMERIC_VALUE_TYPES:
        number = float(cell.get(open_document("office", "value")))
        return int(number) if number.is_integer() else number
    if value_type == "date":
        return ods_date(cell.get(open_document("office", "date-value")))
    if value_type == "boolean":
        return cell.get(open_document("office", "boolean-value")) == "true"
    text = "\n".join("".join(paragraph.itertext()) for paragraph in cell.iterfind("text:p", OPEN_DOCUMENT_NAMESPACES))
    return text or None


def ods_date(text: str) -> datetime.date | datetime.datetime:
    moment = datetime.datetime.fromisoformat(text)
    return moment.date() if "T" not in text else moment


def read_xlsb(input_path: Path) -> list[SheetData]:
    book = CalamineWorkbook.from_path(str(input_path))
    merges = xlsb_merges(input_path)
    return [xlsb_sheet(name, book.get_sheet_by_name(name).to_python(skip_empty_area=False), merges.get(name, [])) for name in book.sheet_names]


def xlsb_sheet(name: str, rows: list[list], merges: list) -> SheetData:
    data = SheetData(name, merges=merges)
    for row_index, row in enumerate(rows, start=1):
        for column_index, value in enumerate(row, start=1):
            if value != "" and value is not None:
                data.cells[(row_index, column_index)] = int(value) if isinstance(value, float) and value.is_integer() else value
    return data


def xlsb_records(data: bytes):
    position = 0
    while position < len(data):
        kind, position = variable_integer(data, position, 2)
        size, position = variable_integer(data, position, 4)
        yield kind, data[position:position + size]
        position += size


def variable_integer(data: bytes, position: int, limit: int) -> tuple[int, int]:
    value = 0
    for shift in range(limit):
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << (7 * shift)
        if not byte & 0x80:
            break
    return value, position


def wide_text(payload: bytes, offset: int) -> tuple[str, int]:
    length = int.from_bytes(payload[offset:offset + 4], "little")
    end = offset + 4 + 2 * length
    return payload[offset + 4:end].decode("utf-16-le"), end


def xlsb_sheet_parts(archive: zipfile.ZipFile) -> dict[str, str]:
    relationships = etree.fromstring(archive.read("xl/_rels/workbook.bin.rels"))
    targets = {element.get("Id"): element.get("Target") for element in relationships.iter(f"{PACKAGE_RELATIONSHIP_NAMESPACE}Relationship")}
    parts = {}
    for kind, payload in xlsb_records(archive.read("xl/workbook.bin")):
        if kind == BUNDLE_SHEET_RECORD:
            identifier, end = wide_text(payload, 8)
            name, _ = wide_text(payload, end)
            parts[name] = "xl/" + targets.get(identifier, "").lstrip("/").removeprefix("xl/")
    return parts


def xlsb_merges(input_path: Path) -> dict[str, list[tuple[int, int, int, int]]]:
    with zipfile.ZipFile(input_path) as archive:
        names = set(archive.namelist())
        merges = {}
        for name, part in xlsb_sheet_parts(archive).items():
            if part not in names:
                continue
            records = [payload for kind, payload in xlsb_records(archive.read(part)) if kind == MERGE_CELL_RECORD]
            merges[name] = [merge_bounds(payload) for payload in records]
    return merges


def merge_bounds(payload: bytes) -> tuple[int, int, int, int]:
    first_row, last_row, first_column, last_column = (int.from_bytes(payload[offset:offset + 4], "little") for offset in (0, 4, 8, 12))
    return first_row + 1, first_column + 1, last_row + 1, last_column + 1


def write_workbook(sheets: list[SheetData], output_path: Path) -> None:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet in sheets:
        worksheet = workbook.create_sheet(fitting_sheet_name(sheet.name))
        for (row, column), value in sheet.cells.items():
            cell = worksheet.cell(row=row, column=column, value=value)
            if isinstance(value, str) and value.startswith("="):
                cell.data_type = "s"
            if isinstance(value, (datetime.date, datetime.datetime)):
                cell.number_format = "yyyy-mm-dd" if not isinstance(value, datetime.datetime) else "yyyy-mm-dd hh:mm"
        for top, left, bottom, right in sheet.merges:
            worksheet.merge_cells(start_row=top, start_column=left, end_row=bottom, end_column=right)
    workbook.save(output_path)


def open_document(prefix: str, name: str) -> str:
    return f"{{{OPEN_DOCUMENT_NAMESPACES[prefix]}}}{name}"


SPREADSHEET_READERS = {".xls": read_xls, ".ods": read_ods, ".xlsb": read_xlsb}
