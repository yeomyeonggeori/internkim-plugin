from __future__ import annotations

import io
import zipfile

from pptx_package import xml_document
from pptx_text import text_content
from excel_limits import DEFAULT_SHEET_NAME, column_letter




def cell_reference(column: int, row: int, absolute: bool = False) -> str:
    marker = "$" if absolute else ""
    return f"{marker}{column_letter(column + 1)}{marker}{row + 1}"


def chart_workbook_bytes(labels: list[str], series: list[dict]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", workbook_content_types_xml())
        archive.writestr("_rels/.rels", workbook_package_relationships_xml())
        archive.writestr("xl/workbook.xml", workbook_xml())
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_relationships_xml())
        archive.writestr("xl/worksheets/sheet1.xml", worksheet_xml(labels, series))
    return buffer.getvalue()


def worksheet_xml(labels: list[str], series: list[dict]) -> str:
    header = [text_cell(0, 0, "")] + [text_cell(index + 1, 0, entry["name"]) for index, entry in enumerate(series)]
    rows = [row_xml(0, header)]
    for row, label in enumerate(labels, start=1):
        cells = [text_cell(0, row, label)] + [number_cell(index + 1, row, entry["values"][row - 1]) for index, entry in enumerate(series)]
        rows.append(row_xml(row, cells))
    return xml_document(
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(rows)}</sheetData></worksheet>"
    )


def row_xml(row: int, cells: list[str]) -> str:
    return f'<row r="{row + 1}">{"".join(cells)}</row>'


def text_cell(column: int, row: int, text: str) -> str:
    if not text:
        return ""
    return f'<c r="{cell_reference(column, row)}" t="inlineStr"><is><t>{text_content(text)}</t></is></c>'


def number_cell(column: int, row: int, value: float) -> str:
    return f'<c r="{cell_reference(column, row)}"><v>{number_text(value)}</v></c>'


def number_text(value: float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else repr(number)


def workbook_content_types_xml() -> str:
    return xml_document(
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )


def workbook_package_relationships_xml() -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def workbook_xml() -> str:
    return xml_document(
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{DEFAULT_SHEET_NAME}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )


def workbook_relationships_xml() -> str:
    return xml_document(
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
