from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import io
from pathlib import Path
import re

import pdfplumber

from create_xlsx import create_workbook
from office_inputs import unlocked_pdf_bytes
from pdf_to_blocks import page_tables


NUMBER = re.compile(r"(?P<open>\()?(?P<sign>[-−])?(?P<currency>[₩$€£¥])?(?P<digits>\d{1,3}(?:,\d{3})+|\d+)(?P<fraction>\.\d+)?(?P<percent>%)?(?P<close>\))?")
DATE = re.compile(r"(?P<year>\d{4})[-./](?P<month>\d{1,2})[-./](?P<day>\d{1,2})\.?")
SHEET_TITLE_LIMIT = 31


@dataclass
class PdfTable:
    title: str
    pages: list[int]
    rows: list[list[str]]

    @property
    def has_header(self) -> bool:
        return len(self.rows) > 1 and is_header(self.rows[0])


@dataclass
class PdfTables:
    tables: list[PdfTable] = field(default_factory=list)
    pages_without_tables: list[int] = field(default_factory=list)
    pages_without_text: list[int] = field(default_factory=list)


def typed_text(text: str) -> tuple[object, str | None]:
    stripped = text.strip()
    number = NUMBER.fullmatch(stripped)
    if number and is_number_shape(number):
        return number_value(number)
    date = DATE.fullmatch(stripped)
    if date:
        return date_value(date, stripped)
    return (text if text else None), None


def is_number_shape(match) -> bool:
    if bool(match["open"]) != bool(match["close"]):
        return False
    digits = match["digits"]
    return "," in digits or digits == "0" or not digits.startswith("0")


def number_value(match) -> tuple[float | int, str]:
    digits = match["digits"].replace(",", "")
    fraction = match["fraction"] or ""
    value = float(digits + fraction) if fraction else int(digits)
    if match["open"] or match["sign"]:
        value = -value
    decimals = "." + "0" * (len(fraction) - 1) if fraction else ""
    if match["percent"]:
        return value / 100, f"0{decimals}%"
    if match["currency"] is not None:
        return value, f'"{match["currency"]}"#,##0{decimals}'
    if "," in match["digits"]:
        return value, f"#,##0{decimals}"
    return value, None


def date_value(match, text: str) -> tuple[object, str | None]:
    try:
        return datetime.date(int(match["year"]), int(match["month"]), int(match["day"])), "yyyy-mm-dd"
    except ValueError:
        return text, None


def is_header(row: list[str]) -> bool:
    return all(cell.strip() and isinstance(typed_text(cell)[0], str) for cell in row)


def continues(previous: PdfTable, rows: list[list[str]]) -> bool:
    return previous.has_header and len(rows[0]) == len(previous.rows[0]) and rows[0] == previous.rows[0]


def read_pdf_tables(path: Path, password: str | None) -> PdfTables:
    found = PdfTables()
    with pdfplumber.open(io.BytesIO(unlocked_pdf_bytes(str(path), password))) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            tables = page_tables(page)
            if not tables:
                (found.pages_without_text if not page.extract_words() else found.pages_without_tables).append(number)
            for position, table in enumerate(tables, start=1):
                add_table(found, table.rows, number, position, len(tables))
    return found


def add_table(found: PdfTables, rows: list[list[str]], page: int, position: int, page_table_count: int) -> None:
    previous = found.tables[-1] if found.tables else None
    if position == 1 and previous is not None and previous.pages[-1] == page - 1 and continues(previous, rows):
        previous.rows.extend(rows[1:])
        previous.pages.append(page)
        return
    title = f"Page {page}" if page_table_count == 1 else f"Page {page} Table {position}"
    found.tables.append(PdfTable(title[:SHEET_TITLE_LIMIT], [page], [list(row) for row in rows]))


def sheet_specification(table: PdfTable) -> tuple[dict, dict]:
    width = max(len(row) for row in table.rows)
    typed_rows, formats = [], {}
    for row_index, row in enumerate(table.rows):
        cells = []
        for column_index in range(width):
            text = row[column_index] if column_index < len(row) else ""
            value, number_format = (text or None, None) if table.has_header and row_index == 0 else typed_text(text)
            cells.append(value)
            if number_format:
                formats[(row_index + 1, column_index + 1)] = number_format
        typed_rows.append(cells)
    specification = {"title": table.title, "rows": typed_rows}
    if not table.has_header:
        specification.update({"freezePanes": "", "autoFilter": False})
    return specification, formats


def write_pdf_workbook(tables: list[PdfTable], output_path: Path, title: str) -> None:
    specifications = [sheet_specification(table) for table in tables]
    workbook = create_workbook({"title": title, "sheets": [specification for specification, _ in specifications]})
    for worksheet, (_, formats) in zip(workbook.worksheets, specifications):
        for (row, column), number_format in formats.items():
            worksheet.cell(row=row, column=column).number_format = number_format
    workbook.save(output_path)


def table_details(table: PdfTable) -> dict:
    return {"sheet": table.title, "pages": table.pages, "rows": len(table.rows), "columns": max(len(row) for row in table.rows), "header": table.has_header}
